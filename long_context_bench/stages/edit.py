"""Edit stage: Run agent on samples and capture diffs."""

import json
import platform
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
import os

import git
from rich.console import Console

from long_context_bench import __version__
from long_context_bench.models import Sample, Edit, EditRunManifest
from long_context_bench.runners import get_runner_adapter

console = Console()


def load_sample(sample_path: Path) -> Sample:
    """Load sample from JSON file.
    
    Args:
        sample_path: Path to sample.json
        
    Returns:
        Sample object
    """
    with open(sample_path) as f:
        data = json.load(f)
    return Sample(**data)


def materialize_workspace(
    sample: Sample,
    workspace_path: Path,
    cache_dir: Optional[Path] = None
) -> git.Repo:
    """Materialize a clean workspace at the base commit.

    Per R-3.7: Create workspace at base commit with read/write permissions.

    Args:
        sample: Sample object
        workspace_path: Path to workspace directory
        cache_dir: Optional cache directory for repositories

    Returns:
        Git repository object
    """
    if cache_dir:
        # Extract repo name from URL
        repo_name = sample.repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        owner = sample.repo_url.rstrip("/").split("/")[-2]
        cache_path = cache_dir / f"{owner}_{repo_name}"

        if cache_path.exists():
            console.print(f"  Copying from cache to workspace...")
            import shutil
            shutil.copytree(cache_path, workspace_path, symlinks=True)
            repo = git.Repo(workspace_path)
            # Fetch to ensure we have the commit
            try:
                repo.git.fetch("origin", sample.base_commit)
            except Exception as e:
                console.print(f"  [yellow]Warning: Failed to fetch commit: {e}[/yellow]")
        else:
            console.print(f"  Cloning repository to workspace...")
            repo = git.Repo.clone_from(sample.repo_url, workspace_path)
    else:
        console.print(f"  Cloning repository to workspace...")
        repo = git.Repo.clone_from(sample.repo_url, workspace_path)

    console.print(f"  Checking out base commit {sample.base_commit[:8]}...")
    repo.git.checkout(sample.base_commit, detach=True)

    return repo


def capture_diff(repo: git.Repo, base_commit: str) -> str:
    """Capture unified diff from workspace.
    
    Per R-3.9: Produce unified diff against base commit.
    
    Args:
        repo: Git repository
        base_commit: Base commit hash
        
    Returns:
        Unified diff string
    """
    try:
        diff = repo.git.diff(base_commit, unified=True)
        return diff
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to capture diff: {e}[/yellow]")
        return ""


def run_edit_on_sample(
    sample: Sample,
    runner: str,
    model: str,
    agent_binary: Optional[str],
    output_dir: Path,
    timeout: int,
    disable_retrieval: bool,
    disable_shell: bool,
    enable_mcp_codebase_qa: bool,
    run_id: str,
    cache_dir: Optional[Path] = None,
) -> Edit:
    """Run edit stage on a single sample.

    Args:
        sample: Sample object
        runner: Runner name
        model: Model name
        agent_binary: Optional agent binary path
        output_dir: Output directory
        timeout: Timeout in seconds
        disable_retrieval: Disable retrieval
        disable_shell: Disable shell
        enable_mcp_codebase_qa: Enable MCP codebase QA
        run_id: Run ID
        cache_dir: Optional cache directory for repositories

    Returns:
        Edit object
    """
    pr_id = f"{sample.repo_url.split('/')[-2]}_{sample.repo_url.split('/')[-1].replace('.git', '')}_pr{sample.pr_number}"
    
    console.print(f"[cyan]Running edit on {pr_id}...[/cyan]")
    
    # Create output directory
    edit_dir = output_dir / runner / model / run_id / pr_id
    edit_dir.mkdir(parents=True, exist_ok=True)
    
    logs_path = edit_dir / "logs.jsonl"
    
    # Create runner adapter
    adapter = get_runner_adapter(
        runner,
        model=model,
        agent_binary=agent_binary,
        timeout=timeout,
        disable_retrieval=disable_retrieval,
        disable_shell=disable_shell,
        enable_mcp_codebase_qa=enable_mcp_codebase_qa,
    )
    
    # Materialize workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace_path = Path(tmpdir) / "workspace"

        try:
            repo = materialize_workspace(sample, workspace_path, cache_dir)
            
            # Run agent
            console.print(f"  Running agent...")
            result = adapter.run(
                workspace_path=workspace_path,
                task_instructions=sample.task_instructions,
                logs_path=logs_path,
                env=os.environ.copy(),
            )
            
            # Capture diff
            console.print(f"  Capturing diff...")
            patch_unified = capture_diff(repo, sample.base_commit)

            # Save patch to separate file
            patch_file = edit_dir / "edit.patch"
            with open(patch_file, "w") as f:
                f.write(patch_unified)

            # Create edit artifact
            edit = Edit(
                repo_url=sample.repo_url,
                pr_number=sample.pr_number,
                base_commit=sample.base_commit,
                runner=runner,
                model=model,
                timeout_s=timeout,
                status=result.status,
                elapsed_ms=result.elapsed_ms,
                patch_unified=patch_unified,
                logs_path=str(logs_path.relative_to(output_dir)),
                errors=result.errors,
                edit_run_id=run_id,
            )

            # Write edit.json
            edit_file = edit_dir / "edit.json"
            with open(edit_file, "w") as f:
                f.write(edit.model_dump_json(indent=2))

            # Also write a version without the patch for easier reading
            edit_summary_file = edit_dir / "edit_summary.json"
            edit_dict = edit.model_dump()
            edit_dict["patch_file"] = "edit.patch"
            edit_dict.pop("patch_unified")  # Remove the inline patch
            with open(edit_summary_file, "w") as f:
                import json
                json.dump(edit_dict, f, indent=2)
            
            console.print(f"[green]✓ Edit completed for {pr_id} (status: {result.status})[/green]")
            return edit
            
        except Exception as e:
            console.print(f"[red]✗ Edit failed for {pr_id}: {e}[/red]")

            # Create error edit artifact
            edit = Edit(
                repo_url=sample.repo_url,
                pr_number=sample.pr_number,
                base_commit=sample.base_commit,
                runner=runner,
                model=model,
                timeout_s=timeout,
                status="error",
                elapsed_ms=0,
                patch_unified="",
                logs_path=str(logs_path.relative_to(output_dir)) if logs_path.exists() else "",
                errors=[str(e)],
                edit_run_id=run_id,
            )

            # Create empty patch file for consistency
            patch_file = edit_dir / "edit.patch"
            with open(patch_file, "w") as f:
                f.write("")

            edit_file = edit_dir / "edit.json"
            with open(edit_file, "w") as f:
                f.write(edit.model_dump_json(indent=2))

            # Also write summary version
            edit_summary_file = edit_dir / "edit_summary.json"
            edit_dict = edit.model_dump()
            edit_dict["patch_file"] = "edit.patch"
            edit_dict.pop("patch_unified")
            with open(edit_summary_file, "w") as f:
                import json
                json.dump(edit_dict, f, indent=2)

            return edit


def run_edit_stage(
    sample_path: Path,
    runner: str,
    model: str,
    agent_binary: Optional[str],
    output_dir: Path,
    timeout: int,
    concurrency: int,
    disable_retrieval: bool,
    disable_shell: bool,
    enable_mcp_codebase_qa: bool,
    dataset_version: str = "v0",
    cache_dir: Optional[Path] = None,
) -> str:
    """Run the edit stage.

    Args:
        sample_path: Path to sample.json or directory of samples
        runner: Runner name
        model: Model name
        agent_binary: Optional agent binary path
        output_dir: Output directory
        timeout: Timeout in seconds
        concurrency: Max concurrent tasks
        disable_retrieval: Disable retrieval
        disable_shell: Disable shell
        enable_mcp_codebase_qa: Enable MCP codebase QA
        dataset_version: Dataset version
        cache_dir: Optional cache directory for repositories

    Returns:
        Edit run ID
    """
    import uuid

    output_dir.mkdir(parents=True, exist_ok=True)
    edit_run_id = str(uuid.uuid4())[:8]

    console.print(f"[bold]Starting edit run {edit_run_id}[/bold]")
    console.print(f"  Runner: {runner}")
    console.print(f"  Model: {model}")

    # Load samples
    samples = []
    if sample_path.is_file():
        samples = [load_sample(sample_path)]
    elif sample_path.is_dir():
        for sample_file in sample_path.rglob("sample.json"):
            samples.append(load_sample(sample_file))

    console.print(f"[bold]Running edit stage on {len(samples)} samples...[/bold]")

    # Create manifest
    manifest = EditRunManifest(
        dataset_version=dataset_version,
        harness_version=__version__,
        runner=runner,
        runner_version=None,  # TODO: Get from adapter
        model=model,
        os=platform.system(),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        timeout_s=timeout,
        concurrency=concurrency,
        total_shards=1,
        shard_index=0,
        flags={
            "disable_retrieval": disable_retrieval,
            "disable_shell": disable_shell,
            "enable_mcp_codebase_qa": enable_mcp_codebase_qa,
        },
        timestamp=datetime.utcnow().isoformat(),
        edit_run_id=edit_run_id,
    )

    # Save manifest in the runner/model/run_id directory
    manifest_dir = output_dir / runner / model / edit_run_id
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = manifest_dir / "edit_run_manifest.json"
    with open(manifest_file, "w") as f:
        f.write(manifest.model_dump_json(indent=2))

    # For now, run sequentially (concurrency support can be added later)
    for sample in samples:
        run_edit_on_sample(
            sample=sample,
            runner=runner,
            model=model,
            agent_binary=agent_binary,
            output_dir=output_dir,
            timeout=timeout,
            disable_retrieval=disable_retrieval,
            disable_shell=disable_shell,
            enable_mcp_codebase_qa=enable_mcp_codebase_qa,
            run_id=edit_run_id,
            cache_dir=cache_dir,
        )

    console.print(f"\n[bold green]Edit run {edit_run_id} complete![/bold green]")
    console.print(f"Results saved to: {manifest_dir}")

    return edit_run_id
    
    console.print(f"\n[bold]Edit stage complete[/bold]")

