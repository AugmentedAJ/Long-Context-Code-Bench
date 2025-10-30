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
from long_context_bench.models import Sample, Edit, EditRunManifest, RunManifest
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

    IMPORTANT: Do NOT expose full git history to the agent. We initialize a fresh
    repo and fetch only the base commit by SHA (shallow, no tags, no remote).

    Args:
        sample: Sample object
        workspace_path: Path to workspace directory
        cache_dir: Optional cache directory for repositories (unused for workspace materialization)

    Returns:
        Git repository object rooted at base commit with minimal history
    """
    # Ensure workspace directory exists and is empty
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Initialize an empty repo and fetch only the base commit by SHA directly
    # from the remote URL (avoids creating a persistent remote like 'origin').
    try:
        repo = git.Repo.init(workspace_path)
        console.print(f"  Fetching base commit (shallow)...")
        # Equivalent to: git fetch --no-tags --depth=1 <url> <sha>
        repo.git.fetch("--no-tags", "--depth=1", sample.repo_url, sample.base_commit)
    except Exception as e:
        # Fallback: do a shallow clone then fetch the specific commit
        console.print(f"  [yellow]Shallow fetch by SHA failed, falling back to shallow clone: {e}[/yellow]")
        import shutil
        # Clean up any partial init
        try:
            if workspace_path.exists():
                shutil.rmtree(workspace_path)
        except Exception:
            pass
        console.print(f"  Cloning repository (shallow)...")
        repo = git.Repo.clone_from(sample.repo_url, workspace_path)
        # Try to reduce history exposure as much as possible
        try:
            repo.git.fetch("--no-tags", "--depth=1", "origin", sample.base_commit)
        except Exception as e2:
            console.print(f"  [yellow]Warning: Shallow fetch after clone failed: {e2}[/yellow]")

    console.print(f"  Checking out base commit {sample.base_commit[:8]} (detached)...")
    repo.git.checkout(sample.base_commit, detach=True)

    # Do not leave a persistent remote to avoid additional history fetches by agents
    # (we didn't create one above when fetching by URL). If a remote exists (from
    # fallback clone), remove it.
    try:
        if any(r.name == "origin" for r in repo.remotes):
            repo.delete_remote("origin")
    except Exception:
        # Non-fatal if remote removal fails
        pass

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
    force: bool = False,
    test_label: Optional[str] = None,
    use_synthesized: bool = False,
    stream_output: bool = False,
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
        force: If True, re-run even if edit_summary.json already exists
        test_label: Optional test label for grouping runs
        use_synthesized: If True, use synthesized task instructions instead of template-based
        stream_output: If True, stream agent output to console in real-time

    Returns:
        Edit object
    """
    pr_id = f"{sample.repo_url.split('/')[-2]}_{sample.repo_url.split('/')[-1].replace('.git', '')}_pr{sample.pr_number}"

    # Create output directory
    edit_dir = output_dir / runner / model / run_id / pr_id
    edit_dir.mkdir(parents=True, exist_ok=True)

    # Check if edit already exists (current run)
    edit_summary_file = edit_dir / "edit_summary.json"

    if edit_summary_file.exists() and not force:
        console.print(f"[yellow]⊙ Skipping {pr_id} (already edited in this run)[/yellow]")
        # Load and return existing edit
        with open(edit_summary_file) as f:
            edit_data = json.load(f)
            # Load patch from separate file
            patch_file = edit_dir / "edit.patch"
            if patch_file.exists():
                with open(patch_file) as pf:
                    edit_data["patch_unified"] = pf.read()
            else:
                edit_data["patch_unified"] = ""
            return Edit(**edit_data)

    # If test_label is provided, check if this PR was already edited in any run with the same test_label
    if test_label and not force:
        # Check in staged mode (edit_run_manifest.json in runner/model/run_id/)
        runner_model_dir = output_dir / runner / model
        if runner_model_dir.exists():
            for other_run_dir in runner_model_dir.iterdir():
                if not other_run_dir.is_dir() or other_run_dir.name == run_id:
                    continue

                # Check if this run has the same test_label
                manifest_file = other_run_dir / "edit_run_manifest.json"
                if manifest_file.exists():
                    with open(manifest_file) as f:
                        manifest = EditRunManifest(**json.load(f))
                        if manifest.test_label == test_label:
                            # Check if this PR was edited in that run
                            other_edit_file = other_run_dir / pr_id / "edit_summary.json"
                            if other_edit_file.exists():
                                console.print(f"[yellow]⊙ Skipping {pr_id} (already edited in run {other_run_dir.name} with test label '{test_label}')[/yellow]")
                                # Load and return existing edit
                                with open(other_edit_file) as f:
                                    edit_data = json.load(f)
                                    # Load patch from separate file
                                    patch_file = other_run_dir / pr_id / "edit.patch"
                                    if patch_file.exists():
                                        with open(patch_file) as pf:
                                            edit_data["patch_unified"] = pf.read()
                                    else:
                                        edit_data["patch_unified"] = ""
                                    return Edit(**edit_data)

        # Check in pipeline mode (run_manifest.json in summaries/run_id/)
        summaries_dir = output_dir.parent / "summaries"
        if summaries_dir.exists():
            for other_run_dir in summaries_dir.iterdir():
                if not other_run_dir.is_dir() or other_run_dir.name == run_id:
                    continue

                # Check if this run has the same test_label
                manifest_file = other_run_dir / "run_manifest.json"
                if manifest_file.exists():
                    with open(manifest_file) as f:
                        manifest = RunManifest(**json.load(f))
                        if manifest.test_label == test_label and manifest.runner == runner and manifest.model == model:
                            # Check if this PR was edited in that run
                            other_edit_file = output_dir / runner / model / other_run_dir.name / pr_id / "edit_summary.json"
                            if other_edit_file.exists():
                                console.print(f"[yellow]⊙ Skipping {pr_id} (already edited in run {other_run_dir.name} with test label '{test_label}')[/yellow]")
                                # Load and return existing edit
                                with open(other_edit_file) as f:
                                    edit_data = json.load(f)
                                    # Load patch from separate file
                                    patch_file = output_dir / runner / model / other_run_dir.name / pr_id / "edit.patch"
                                    if patch_file.exists():
                                        with open(patch_file) as pf:
                                            edit_data["patch_unified"] = pf.read()
                                    else:
                                        edit_data["patch_unified"] = ""
                                    return Edit(**edit_data)

    console.print(f"[cyan]Running edit on {pr_id}...[/cyan]")
    
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
        stream_output=stream_output,
    )
    
    # Materialize workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace_path = Path(tmpdir) / "workspace"

        try:
            repo = materialize_workspace(sample, workspace_path, cache_dir)

            # Hide .git from the agent to prevent history inspection
            import shutil
            git_dir = workspace_path / ".git"
            hidden_git_dir = Path(tmpdir) / ".git_hidden"
            git_was_hidden = False
            if git_dir.exists():
                try:
                    shutil.move(str(git_dir), str(hidden_git_dir))
                    console.print("  .git hidden from agent during execution")
                    git_was_hidden = True
                except Exception as e:
                    console.print(f"  [yellow]Warning: Failed to hide .git: {e}[/yellow]")

            # Choose which task instructions to use
            if use_synthesized and sample.synthesized_task_instructions:
                task_instructions = sample.synthesized_task_instructions
                console.print(f"  Using synthesized task instructions")
            elif use_synthesized and not sample.synthesized_task_instructions:
                console.print(f"  [yellow]Warning: --use-synthesized specified but no synthesized instructions available, using template-based[/yellow]")
                task_instructions = sample.task_instructions
            else:
                task_instructions = sample.task_instructions

            # Run agent
            console.print(f"  Running agent...")
            result = adapter.run(
                workspace_path=workspace_path,
                task_instructions=task_instructions,
                logs_path=logs_path,
                env=os.environ.copy(),
            )

            # Restore .git after agent run (only if it was hidden)
            if git_was_hidden and hidden_git_dir.exists() and not git_dir.exists():
                try:
                    shutil.move(str(hidden_git_dir), str(git_dir))
                    console.print("  .git restored after agent execution")
                    # Reopen repo after restoring .git
                    repo = git.Repo(workspace_path)
                except Exception as e:
                    console.print(f"  [yellow]Warning: Failed to restore .git: {e}[/yellow]")

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
                test_label=test_label,
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
                test_label=test_label,
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
    test_label: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    force: bool = False,
    use_synthesized: bool = False,
    stream_output: bool = False,
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
        test_label: Optional label for grouping runs for comparison
        cache_dir: Optional cache directory for repositories
        force: If True, re-run even if edit_summary.json already exists
        use_synthesized: If True, use synthesized task instructions instead of template-based
        stream_output: If True, stream agent output to console in real-time

    Returns:
        Edit run ID
    """
    import uuid

    output_dir.mkdir(parents=True, exist_ok=True)
    edit_run_id = str(uuid.uuid4())[:8]

    console.print(f"[bold]Starting edit run {edit_run_id}[/bold]")
    console.print(f"  Runner: {runner}")
    console.print(f"  Model: {model}")
    if test_label:
        console.print(f"  Test label: {test_label}")

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
        test_label=test_label,
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
            force=force,
            test_label=test_label,
            use_synthesized=use_synthesized,
            stream_output=stream_output,
        )

    console.print(f"\n[bold green]Edit run {edit_run_id} complete![/bold green]")
    console.print(f"Results saved to: {manifest_dir}")

    return edit_run_id
    
    console.print(f"\n[bold]Edit stage complete[/bold]")

