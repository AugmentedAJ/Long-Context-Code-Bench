"""Pipeline orchestration: sample → edit → judge."""

import json
import hashlib
import platform
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

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
        dataset_version: Dataset version (e.g., 'v0', 'v1')

    Returns:
        Path to dataset JSON file
    """
    # Get the package directory
    import long_context_bench
    package_dir = Path(long_context_bench.__file__).parent.parent

    # Map dataset versions to their corresponding files
    if dataset_version == "v1":
        dataset_path = package_dir / "data" / "elasticsearch_prs_100_v1.json"
    else:
        # Default to v0 dataset
        dataset_path = package_dir / "data" / "elasticsearch_prs_50.json"

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


def _run_single_agent(
    runner: str,
    model: str,
    agent_binary: Optional[str],
    samples: List[Any],
    output_dir: Path,
    timeout: int,
    disable_retrieval: bool,
    disable_shell: bool,
    enable_mcp_codebase_qa: bool,
    run_id: str,
    cache_dir: Path,
    force: bool,
    test_label: Optional[str],
    judge_model: Optional[str],
    dataset_version: str,
    stream_output: bool = False,
    mcp_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a single agent configuration on all samples.

    This function is designed to be run in parallel with other agents.
    Each agent writes to its own isolated directory structure.

    Args:
        runner: Agent runner name
        model: Model name
        agent_binary: Optional agent binary path
        samples: List of samples to process
        output_dir: Output root directory
        timeout: Timeout in seconds
        disable_retrieval: Disable retrieval
        disable_shell: Disable shell
        enable_mcp_codebase_qa: Enable MCP codebase QA
        run_id: Run ID
        cache_dir: Cache directory
        force: Force re-run
        test_label: Test label
        judge_model: Optional judge model
        dataset_version: Dataset version

    Returns:
        Dict with agent results including edits, judges, and summary
    """
    edits = []
    judges = []

    # Create agent-specific output directories
    edits_dir = output_dir / "edits"
    judges_dir = output_dir / "judges"

    console.print(f"\n[bold magenta]Running agent: {runner} with model {model}[/bold magenta]")

    for sample in samples:
        try:
            # Edit stage
            console.print(f"\n[bold cyan]═══ Edit Stage ({runner}/{model}) ═══[/bold cyan]")
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
                force=force,
                test_label=test_label,
                stream_output=stream_output,
                mcp_config_path=mcp_config_path,
            )
            edits.append(edit)

            # Judge stage (optional)
            if judge_model:
                console.print(f"\n[bold cyan]═══ Judge Stage ({runner}/{model}) ═══[/bold cyan]")
                judge = judge_edit(
                    sample=sample,
                    edit=edit,
                    judge_model=judge_model,
                    output_dir=judges_dir,
                    judge_run_id=run_id,
                    cache_dir=cache_dir,
                    force=force,
                    test_label=test_label,
                )
                judges.append(judge)
            else:
                console.print(f"\n[yellow]Skipping judge stage (no judge model provided)[/yellow]")

        except Exception as e:
            import traceback
            console.print(f"[red]✗ Pipeline failed for {sample.pr_url} ({runner}/{model}): {e}[/red]")
            console.print(f"[red]{traceback.format_exc()}[/red]")

    return {
        "runner": runner,
        "model": model,
        "edits": edits,
        "judges": judges,
    }


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
    judge_model: Optional[str],
    test_label: Optional[str],
    github_token: Optional[str],
    disable_retrieval: bool,
    disable_shell: bool,
    enable_mcp_codebase_qa: bool,
    pr_numbers: Optional[str],
    pr_indices: Optional[str],
    cache_dir: Path,
    force: bool = False,
    stream_output: bool = False,
    mcp_config_path: Optional[str] = None,
    agent_configs: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Run complete pipeline: sample → edit → judge.

    Args:
        runner: Runner name (used if agent_configs is None)
        model: Model name (used if agent_configs is None)
        agent_binary: Optional agent binary path (used if agent_configs is None)
        output_dir: Output root directory
        dataset_version: Dataset version
        timeout: Timeout in seconds
        concurrency: Max concurrent tasks
        total_shards: Total number of shards
        shard_index: Current shard index
        judge_model: Optional judge model
        test_label: Optional label for grouping runs for comparison
        github_token: Optional GitHub token
        disable_retrieval: Disable retrieval
        disable_shell: Disable shell
        enable_mcp_codebase_qa: Enable MCP codebase QA
        pr_numbers: Comma-separated PR numbers to run
        pr_indices: Comma-separated PR indices to run
        cache_dir: Directory for caching cloned repositories
        force: If True, re-run all stages even if outputs already exist
        mcp_config_path: Optional path to MCP configuration file
        agent_configs: Optional list of agent configurations for parallel execution.
            Each config is a dict with keys: runner, model, agent_binary (optional).
            If provided, runner/model/agent_binary args are ignored.
    """
    run_id = str(uuid.uuid4())[:8]

    # Determine agent configurations
    if agent_configs is None:
        # Single agent mode (backward compatible)
        agent_configs = [{
            "runner": runner,
            "model": model,
            "agent_binary": agent_binary,
        }]

    console.print(f"[bold]Starting pipeline run {run_id}[/bold]")
    console.print(f"  Dataset: {dataset_version}")
    console.print(f"  Shard: {shard_index + 1}/{total_shards}")
    console.print(f"  Agents: {len(agent_configs)}")
    for i, cfg in enumerate(agent_configs, 1):
        console.print(f"    {i}. {cfg['runner']} / {cfg['model']}")
    if test_label:
        console.print(f"  Test label: {test_label}")

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

    # Sample stage (shared across all agents)
    samples = []
    console.print(f"\n[bold cyan]═══ Sample Stage (shared) ═══[/bold cyan]")

    # Check for pre-synthesized samples in data/samples first
    import long_context_bench
    package_dir = Path(long_context_bench.__file__).parent.parent
    builtin_samples_dir = package_dir / "data" / "samples"

    for pr_url in filtered_urls:
        try:
            from long_context_bench.stages.sample import parse_pr_url, get_pr_id
            owner, repo, pr_number = parse_pr_url(pr_url)
            pr_id = get_pr_id(owner, repo, pr_number)

            # First, try to load from built-in pre-synthesized samples
            builtin_sample_file = builtin_samples_dir / dataset_version / pr_id / "sample.json"
            if builtin_sample_file.exists():
                console.print(f"[green]✓ Loading pre-synthesized sample: {pr_id}[/green]")
                with open(builtin_sample_file) as f:
                    sample_data = json.load(f)
                    from long_context_bench.models import Sample
                    sample = Sample(**sample_data)
                    samples.append(sample)
                continue

            # Fall back to sampling (will check output/samples or re-sample from GitHub)
            sample = sample_pr(pr_url, samples_dir, dataset_version, github_token, cache_dir, force=force)
            if sample:
                samples.append(sample)
        except Exception as e:
            import traceback
            console.print(f"[red]✗ Sample failed for {pr_url}: {e}[/red]")
            console.print(f"[red]{traceback.format_exc()}[/red]")

    if not samples:
        console.print("[yellow]No samples to process[/yellow]")
        return

    console.print(f"[bold green]Loaded {len(samples)} samples[/bold green]")

    # Run agents in parallel
    all_agent_results = []

    if len(agent_configs) == 1:
        # Single agent - no parallelization needed
        cfg = agent_configs[0]
        result = _run_single_agent(
            runner=cfg["runner"],
            model=cfg["model"],
            agent_binary=cfg.get("agent_binary"),
            samples=samples,
            output_dir=output_dir,
            timeout=timeout,
            disable_retrieval=disable_retrieval,
            disable_shell=disable_shell,
            enable_mcp_codebase_qa=enable_mcp_codebase_qa,
            run_id=run_id,
            cache_dir=cache_dir,
            force=force,
            test_label=test_label,
            judge_model=judge_model,
            dataset_version=dataset_version,
            stream_output=stream_output,
            mcp_config_path=mcp_config_path,
        )
        all_agent_results.append(result)
    else:
        # Multiple agents - run in parallel
        console.print(f"\n[bold magenta]Running {len(agent_configs)} agents in parallel[/bold magenta]")

        with ThreadPoolExecutor(max_workers=len(agent_configs)) as executor:
            futures = {}
            for cfg in agent_configs:
                future = executor.submit(
                    _run_single_agent,
                    runner=cfg["runner"],
                    model=cfg["model"],
                    agent_binary=cfg.get("agent_binary"),
                    samples=samples,
                    output_dir=output_dir,
                    timeout=timeout,
                    disable_retrieval=disable_retrieval,
                    disable_shell=disable_shell,
                    enable_mcp_codebase_qa=enable_mcp_codebase_qa,
                    run_id=run_id,
                    cache_dir=cache_dir,
                    force=force,
                    test_label=test_label,
                    judge_model=judge_model,
                    dataset_version=dataset_version,
                    stream_output=stream_output,
                    mcp_config_path=mcp_config_path,
                )
                futures[future] = f"{cfg['runner']}/{cfg['model']}"

            # Wait for all agents to complete
            for future in as_completed(futures):
                agent_name = futures[future]
                try:
                    result = future.result()
                    all_agent_results.append(result)
                    console.print(f"[bold green]✓ Agent {agent_name} completed[/bold green]")
                except Exception as e:
                    import traceback
                    console.print(f"[red]✗ Agent {agent_name} failed: {e}[/red]")
                    console.print(f"[red]{traceback.format_exc()}[/red]")

    # Collect all edits and judges from all agents
    edits = []
    judges = []
    for result in all_agent_results:
        edits.extend(result["edits"])
        judges.extend(result["judges"])

    # Generate summary for each agent
    console.print(f"\n[bold cyan]═══ Generating Summaries ═══[/bold cyan]")

    from long_context_bench.stats import compute_aggregate_summary
    import pandas as pd

    all_summaries = []

    for result in all_agent_results:
        agent_runner = result["runner"]
        agent_model = result["model"]
        agent_edits = result["edits"]
        agent_judges = result["judges"]

        # Create run manifest for this agent
        manifest = RunManifest(
            dataset_version=dataset_version,
            harness_version=__version__,
            runner=agent_runner,
            runner_version=None,  # TODO: Get from adapter
            model=agent_model,
            judge_mode="llm" if judge_model else None,
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
            test_label=test_label,
        )

        manifest_file = summaries_dir / f"run_manifest_{agent_runner}_{agent_model}.json"
        with open(manifest_file, "w") as f:
            f.write(manifest.model_dump_json(indent=2))

        # Compute aggregate statistics for this agent
        summary = compute_aggregate_summary(
            run_id=run_id,
            samples=samples,
            edits=agent_edits,
            judges=agent_judges,
            test_label=test_label,
            runner=agent_runner,
            model=agent_model,
        )

        summary_file = summaries_dir / f"summary_{agent_runner}_{agent_model}.json"
        with open(summary_file, "w") as f:
            f.write(summary.model_dump_json(indent=2))

        all_summaries.append(summary)

        console.print(f"  {agent_runner}/{agent_model}: {summary.success_rate:.1%} success, {summary.mean_aggregate:.2f} mean score")

    # Write combined CSV
    df = pd.DataFrame([s.model_dump() for s in all_summaries])
    csv_file = summaries_dir / "summary.csv"
    df.to_csv(csv_file, index=False)

    # For each agent, also create a separate run directory with summary.json
    # so it shows up in the web dashboard
    for summary in all_summaries:
        agent_run_dir = summaries_dir.parent / f"{run_id}_{summary.runner}_{summary.model}"
        agent_run_dir.mkdir(parents=True, exist_ok=True)

        agent_summary_file = agent_run_dir / "summary.json"
        with open(agent_summary_file, "w") as f:
            f.write(summary.model_dump_json(indent=2))

    # Update web app
    from long_context_bench.stats import update_web_app
    update_web_app(output_dir)

    console.print(f"\n[bold green]Pipeline complete![/bold green]")
    console.print(f"  Run ID: {run_id}")
    console.print(f"  Samples: {len(samples)}")
    console.print(f"  Agents: {len(all_agent_results)}")
    console.print(f"\nResults saved to: {summaries_dir}")

