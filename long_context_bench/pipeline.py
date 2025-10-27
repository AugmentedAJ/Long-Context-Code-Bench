"""Pipeline orchestration: sample → edit → judge."""

import json
import hashlib
import platform
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from rich.console import Console

from long_context_bench import __version__
from long_context_bench.models import RunManifest
from long_context_bench.stages.sample import run_sample_stage, sample_pr
from long_context_bench.stages.edit import run_edit_on_sample, load_sample
from long_context_bench.stages.judge import judge_edit

console = Console()


def compute_shard_hash(repo_url: str, pr_number: int) -> int:
    """Compute stable hash for sharding.
    
    Per R-4.8: Partition by stable hashing of (repo_url, pr_number).
    
    Args:
        repo_url: Repository URL
        pr_number: PR number
        
    Returns:
        Hash value
    """
    key = f"{repo_url}:{pr_number}"
    return int(hashlib.md5(key.encode()).hexdigest(), 16)


def should_process_in_shard(
    repo_url: str,
    pr_number: int,
    total_shards: int,
    shard_index: int,
) -> bool:
    """Determine if a PR should be processed in this shard.
    
    Args:
        repo_url: Repository URL
        pr_number: PR number
        total_shards: Total number of shards
        shard_index: Current shard index (0-based)
        
    Returns:
        True if should process in this shard
    """
    if total_shards == 1:
        return True
    
    hash_val = compute_shard_hash(repo_url, pr_number)
    return (hash_val % total_shards) == shard_index


def get_dataset_path(dataset_version: str) -> Path:
    """Get path to built-in dataset file.

    Args:
        dataset_version: Dataset version (e.g., 'v0')

    Returns:
        Path to dataset JSON file
    """
    # Get the package directory
    import long_context_bench
    package_dir = Path(long_context_bench.__file__).parent.parent
    dataset_path = package_dir / "data" / f"elasticsearch_prs_50.json"

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    return dataset_path


def load_pr_urls(dataset_version: str = "v0") -> List[str]:
    """Load PR URLs from built-in dataset.

    Args:
        dataset_version: Dataset version (e.g., 'v0')

    Returns:
        List of PR URLs
    """
    dataset_path = get_dataset_path(dataset_version)
    with open(dataset_path) as f:
        return json.load(f)


def filter_pr_urls(
    pr_urls: List[str],
    pr_numbers: Optional[str] = None,
    pr_indices: Optional[str] = None,
) -> List[str]:
    """Filter PR URLs by numbers or indices.

    Args:
        pr_urls: List of all PR URLs
        pr_numbers: Comma-separated PR numbers (e.g., '115001,114998')
        pr_indices: Comma-separated indices (0-based, e.g., '0,1,2')

    Returns:
        Filtered list of PR URLs
    """
    if pr_numbers:
        # Parse PR numbers
        requested_numbers = set(int(n.strip()) for n in pr_numbers.split(","))
        # Extract PR number from URL and filter
        from long_context_bench.stages.sample import parse_pr_url
        filtered = []
        for url in pr_urls:
            _, _, pr_num = parse_pr_url(url)
            if pr_num in requested_numbers:
                filtered.append(url)
        return filtered

    if pr_indices:
        # Parse indices
        requested_indices = set(int(i.strip()) for i in pr_indices.split(","))
        # Filter by index
        return [pr_urls[i] for i in requested_indices if i < len(pr_urls)]

    # No filter, return all
    return pr_urls


def run_pipeline(
    runner: str,
    model: str,
    agent_binary: Optional[str],
    output_dir: Path,
    dataset_version: str,
    timeout: int,
    concurrency: int,
    total_shards: int,
    shard_index: int,
    judge_mode: str,
    judge_model: Optional[str],
    github_token: Optional[str],
    disable_retrieval: bool,
    disable_shell: bool,
    enable_mcp_codebase_qa: bool,
    pr_numbers: Optional[str],
    pr_indices: Optional[str],
    cache_dir: Path,
) -> None:
    """Run complete pipeline: sample → edit → judge.

    Args:
        runner: Runner name
        model: Model name
        agent_binary: Optional agent binary path
        output_dir: Output root directory
        dataset_version: Dataset version
        timeout: Timeout in seconds
        concurrency: Max concurrent tasks
        total_shards: Total number of shards
        shard_index: Current shard index
        judge_mode: Judge mode
        judge_model: Optional judge model
        github_token: Optional GitHub token
        disable_retrieval: Disable retrieval
        disable_shell: Disable shell
        enable_mcp_codebase_qa: Enable MCP codebase QA
        pr_numbers: Comma-separated PR numbers to run
        pr_indices: Comma-separated PR indices to run
        cache_dir: Directory for caching cloned repositories
    """
    run_id = str(uuid.uuid4())[:8]

    console.print(f"[bold]Starting pipeline run {run_id}[/bold]")
    console.print(f"  Runner: {runner}")
    console.print(f"  Model: {model}")
    console.print(f"  Dataset: {dataset_version}")
    console.print(f"  Shard: {shard_index + 1}/{total_shards}")

    # Create output directories
    samples_dir = output_dir / "samples"
    edits_dir = output_dir / "edits"
    judges_dir = output_dir / "judges"
    summaries_dir = output_dir / "summaries" / run_id
    cache_dir.mkdir(parents=True, exist_ok=True)

    for d in [samples_dir, edits_dir, judges_dir, summaries_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Load PR URLs from built-in dataset
    all_pr_urls = load_pr_urls(dataset_version)
    console.print(f"\n[bold]Loaded {len(all_pr_urls)} PRs from dataset {dataset_version}[/bold]")

    # Filter by PR numbers or indices if specified
    pr_urls = filter_pr_urls(all_pr_urls, pr_numbers, pr_indices)
    if pr_numbers or pr_indices:
        console.print(f"  Filtered to {len(pr_urls)} PRs based on selection")
    
    # Filter by shard
    filtered_urls = []
    for url in pr_urls:
        from long_context_bench.stages.sample import parse_pr_url
        try:
            owner, repo, pr_number = parse_pr_url(url)
            repo_url = f"https://github.com/{owner}/{repo}"
            if should_process_in_shard(repo_url, pr_number, total_shards, shard_index):
                filtered_urls.append(url)
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to parse {url}: {e}[/yellow]")
    
    console.print(f"[bold]Processing {len(filtered_urls)} PRs in this shard[/bold]\n")
    
    # Track results
    samples = []
    edits = []
    judges = []
    
    # Process each PR
    for pr_url in filtered_urls:
        try:
            # Sample stage
            console.print(f"\n[bold cyan]═══ Sample Stage ═══[/bold cyan]")
            sample = sample_pr(pr_url, samples_dir, dataset_version, github_token, cache_dir)
            if not sample:
                continue
            samples.append(sample)

            # Edit stage
            console.print(f"\n[bold cyan]═══ Edit Stage ═══[/bold cyan]")
            edit = run_edit_on_sample(
                sample=sample,
                runner=runner,
                model=model,
                agent_binary=agent_binary,
                output_dir=edits_dir,
                timeout=timeout,
                disable_retrieval=disable_retrieval,
                disable_shell=disable_shell,
                enable_mcp_codebase_qa=enable_mcp_codebase_qa,
                run_id=run_id,
                cache_dir=cache_dir,
            )
            edits.append(edit)
            
            # Judge stage
            console.print(f"\n[bold cyan]═══ Judge Stage ═══[/bold cyan]")
            judge = judge_edit(
                sample=sample,
                edit=edit,
                judge_mode=judge_mode,
                judge_model=judge_model,
                output_dir=judges_dir,
                run_id=run_id,
                cache_dir=cache_dir,
            )
            judges.append(judge)
            
        except Exception as e:
            console.print(f"[red]✗ Pipeline failed for {pr_url}: {e}[/red]")
    
    # Generate summary
    console.print(f"\n[bold cyan]═══ Generating Summary ═══[/bold cyan]")
    
    # Create run manifest
    manifest = RunManifest(
        dataset_version=dataset_version,
        harness_version=__version__,
        runner=runner,
        runner_version=None,  # TODO: Get from adapter
        model=model,
        judge_mode=judge_mode,
        judge_model=judge_model,
        os=platform.system(),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        timeout_s=timeout,
        concurrency=concurrency,
        total_shards=total_shards,
        shard_index=shard_index,
        flags={
            "disable_retrieval": disable_retrieval,
            "disable_shell": disable_shell,
            "enable_mcp_codebase_qa": enable_mcp_codebase_qa,
        },
        timestamp=datetime.utcnow().isoformat(),
        run_id=run_id,
    )
    
    manifest_file = summaries_dir / "run_manifest.json"
    with open(manifest_file, "w") as f:
        f.write(manifest.model_dump_json(indent=2))
    
    # Compute aggregate statistics
    from long_context_bench.stats import compute_aggregate_summary
    
    summary = compute_aggregate_summary(run_id, samples, edits, judges)
    
    summary_file = summaries_dir / "summary.json"
    with open(summary_file, "w") as f:
        f.write(summary.model_dump_json(indent=2))
    
    # Write CSV
    import pandas as pd
    df = pd.DataFrame([summary.model_dump()])
    csv_file = summaries_dir / "summary.csv"
    df.to_csv(csv_file, index=False)
    
    console.print(f"\n[bold green]Pipeline complete![/bold green]")
    console.print(f"  Run ID: {run_id}")
    console.print(f"  Samples: {len(samples)}")
    console.print(f"  Success rate: {summary.success_rate:.1%}")
    console.print(f"  Mean aggregate score: {summary.mean_aggregate:.2f}")
    console.print(f"\nResults saved to: {summaries_dir}")

