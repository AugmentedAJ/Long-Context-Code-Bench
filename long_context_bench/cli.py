"""CLI entry point for long-context-bench."""

import click
from pathlib import Path
from typing import Optional

from long_context_bench import __version__


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """Long-Context-Bench: Benchmark for evaluating long-context code editing capabilities."""
    pass


@main.command()
@click.argument("input_path", type=str)
@click.option("--output-dir", type=click.Path(), default="output/samples", help="Output directory for samples")
@click.option("--dataset-version", default="v0", help="Dataset version")
@click.option("--github-token", envvar="GITHUB_GIT_TOKEN", help="GitHub token for API access")
def sample(input_path: str, output_dir: str, dataset_version: str, github_token: Optional[str]) -> None:
    """Sample stage: Extract PR metadata and create sample.json files.
    
    INPUT_PATH can be a PR URL, JSON file with PR URLs, or directory of samples.
    """
    from long_context_bench.stages.sample import run_sample_stage
    
    click.echo(f"Running sample stage on {input_path}")
    run_sample_stage(
        input_path=input_path,
        output_dir=Path(output_dir),
        dataset_version=dataset_version,
        github_token=github_token,
    )
    click.echo("Sample stage completed")


@main.command()
@click.argument("sample_path", type=click.Path(exists=True))
@click.option("--runner", required=True, help="Agent runner name (e.g., auggie, claude-code)")
@click.option("--model", required=True, help="Model name")
@click.option("--agent-binary", type=click.Path(), help="Path to agent binary")
@click.option("--output-dir", type=click.Path(), default="output/edits", help="Output directory for edits")
@click.option("--timeout", type=int, default=1800, help="Timeout in seconds per task")
@click.option("--concurrency", type=int, default=1, help="Max concurrent tasks")
@click.option("--disable-retrieval", is_flag=True, help="Disable retrieval features")
@click.option("--disable-shell", is_flag=True, help="Disable shell access")
@click.option("--enable-mcp-codebase-qa", is_flag=True, help="Enable MCP codebase QA")
@click.option("--dataset-version", default="v0", help="Dataset version")
@click.option("--test-label", help="Optional label for grouping runs for comparison")
@click.option("--cache-dir", type=click.Path(), default=".repo_cache", help="Directory for caching cloned repositories")
def edit(
    sample_path: str,
    runner: str,
    model: str,
    agent_binary: Optional[str],
    output_dir: str,
    timeout: int,
    concurrency: int,
    disable_retrieval: bool,
    disable_shell: bool,
    enable_mcp_codebase_qa: bool,
    dataset_version: str,
    test_label: Optional[str],
    cache_dir: str,
) -> None:
    """Edit stage: Run agent on samples and capture diffs.

    Creates a new edit run with a unique ID. All edits from this run will be
    saved under output/edits/<runner>/<model>/<edit_run_id>/.
    """
    from long_context_bench.stages.edit import run_edit_stage

    click.echo(f"Running edit stage with runner={runner}, model={model}")
    if test_label:
        click.echo(f"Test label: {test_label}")
    edit_run_id = run_edit_stage(
        sample_path=Path(sample_path),
        runner=runner,
        model=model,
        agent_binary=agent_binary,
        output_dir=Path(output_dir),
        timeout=timeout,
        concurrency=concurrency,
        disable_retrieval=disable_retrieval,
        disable_shell=disable_shell,
        enable_mcp_codebase_qa=enable_mcp_codebase_qa,
        dataset_version=dataset_version,
        test_label=test_label,
        cache_dir=Path(cache_dir),
    )
    click.echo(f"Edit stage completed. Edit run ID: {edit_run_id}")


@main.command()
@click.option("--sample-path", type=click.Path(exists=True), help="Path to sample.json (for single file mode)")
@click.option("--edit-path", type=click.Path(exists=True), help="Path to edit.json (for single file mode)")
@click.option("--edit-run-ids", help="Comma-separated list of edit run IDs to evaluate (for batch mode)")
@click.option("--judge-mode", type=click.Choice(["deterministic", "llm"]), default="deterministic", help="Judge mode")
@click.option("--judge-model", help="Judge model (for LLM mode)")
@click.option("--test-label", help="Optional label for grouping runs for comparison")
@click.option("--output-dir", type=click.Path(), default="output/judges", help="Output directory for judgments")
@click.option("--cache-dir", type=click.Path(), default=".repo_cache", help="Directory for caching cloned repositories")
def judge(
    sample_path: Optional[str],
    edit_path: Optional[str],
    edit_run_ids: Optional[str],
    judge_mode: str,
    judge_model: Optional[str],
    test_label: Optional[str],
    output_dir: str,
    cache_dir: str,
) -> None:
    """Judge stage: Score agent edits against ground truth.

    Two modes:
    1. Single file mode: Provide --sample-path and --edit-path
    2. Batch mode: Provide --edit-run-ids to evaluate one or more complete edit runs

    Creates a new judge run with a unique ID. All judgments from this run will be
    saved under output/judges/<judge_mode>/<judge_model>/<judge_run_id>/.
    """
    from long_context_bench.stages.judge import run_judge_stage

    # Parse edit run IDs if provided
    edit_run_id_list = None
    if edit_run_ids:
        edit_run_id_list = [rid.strip() for rid in edit_run_ids.split(",")]

    # Validate inputs
    if not edit_run_id_list and (not sample_path or not edit_path):
        click.echo("Error: Must provide either --edit-run-ids or both --sample-path and --edit-path")
        return

    click.echo(f"Running judge stage with mode={judge_mode}")
    if edit_run_id_list:
        click.echo(f"Evaluating edit runs: {', '.join(edit_run_id_list)}")
    if test_label:
        click.echo(f"Test label: {test_label}")

    judge_run_id = run_judge_stage(
        sample_path=Path(sample_path) if sample_path else None,
        edit_path=Path(edit_path) if edit_path else None,
        judge_mode=judge_mode,
        judge_model=judge_model,
        output_dir=Path(output_dir),
        edit_run_ids=edit_run_id_list,
        test_label=test_label,
        cache_dir=Path(cache_dir),
    )
    click.echo(f"Judge stage completed. Judge run ID: {judge_run_id}")


@main.command()
@click.option("--runner", required=True, help="Agent runner name")
@click.option("--model", required=True, help="Model name")
@click.option("--agent-binary", type=click.Path(), help="Path to agent binary")
@click.option("--output-dir", type=click.Path(), default="output", help="Output root directory")
@click.option("--dataset-version", default="v0", help="Dataset version")
@click.option("--timeout", type=int, default=1800, help="Timeout in seconds per task")
@click.option("--concurrency", type=int, default=1, help="Max concurrent tasks")
@click.option("--total-shards", type=int, default=1, help="Total number of shards")
@click.option("--shard-index", type=int, default=0, help="Current shard index (0-based)")
@click.option("--judge-mode", type=click.Choice(["deterministic", "llm"]), default="deterministic", help="Judge mode")
@click.option("--judge-model", help="Judge model (for LLM mode)")
@click.option("--test-label", help="Optional label for grouping runs for comparison")
@click.option("--github-token", envvar="GITHUB_GIT_TOKEN", help="GitHub token")
@click.option("--disable-retrieval", is_flag=True, help="Disable retrieval features")
@click.option("--disable-shell", is_flag=True, help="Disable shell access")
@click.option("--enable-mcp-codebase-qa", is_flag=True, help="Enable MCP codebase QA")
@click.option("--pr-numbers", help="Comma-separated list of PR numbers to run (e.g., '115001,114998')")
@click.option("--pr-indices", help="Comma-separated list of PR indices to run (0-based, e.g., '0,1,2')")
@click.option("--cache-dir", type=click.Path(), default=".repo_cache", help="Directory for caching cloned repositories")
def pipeline(
    runner: str,
    model: str,
    agent_binary: Optional[str],
    output_dir: str,
    dataset_version: str,
    timeout: int,
    concurrency: int,
    total_shards: int,
    shard_index: int,
    judge_mode: str,
    judge_model: Optional[str],
    test_label: Optional[str],
    github_token: Optional[str],
    disable_retrieval: bool,
    disable_shell: bool,
    enable_mcp_codebase_qa: bool,
    pr_numbers: Optional[str],
    pr_indices: Optional[str],
    cache_dir: str,
) -> None:
    """Run complete pipeline: sample → edit → judge.

    By default, runs on the full v0 dataset (50 Elasticsearch PRs).
    Use --pr-numbers or --pr-indices to run on specific PRs only.
    """
    from long_context_bench.pipeline import run_pipeline

    click.echo(f"Running complete pipeline on dataset {dataset_version}")
    if test_label:
        click.echo(f"Test label: {test_label}")
    run_pipeline(
        runner=runner,
        model=model,
        agent_binary=agent_binary,
        output_dir=Path(output_dir),
        dataset_version=dataset_version,
        timeout=timeout,
        concurrency=concurrency,
        total_shards=total_shards,
        shard_index=shard_index,
        judge_mode=judge_mode,
        judge_model=judge_model,
        test_label=test_label,
        github_token=github_token,
        disable_retrieval=disable_retrieval,
        disable_shell=disable_shell,
        enable_mcp_codebase_qa=enable_mcp_codebase_qa,
        pr_numbers=pr_numbers,
        pr_indices=pr_indices,
        cache_dir=Path(cache_dir),
    )
    click.echo("Pipeline completed")


@main.command()
@click.argument("results_dir", type=click.Path(exists=True))
@click.option("--output-file", type=click.Path(), help="Output file for stats")
def stats(results_dir: str, output_file: Optional[str]) -> None:
    """Generate aggregate statistics from results."""
    from long_context_bench.stats import generate_stats

    click.echo(f"Generating stats from {results_dir}")
    generate_stats(
        results_dir=Path(results_dir),
        output_file=Path(output_file) if output_file else None,
    )
    click.echo("Stats generation completed")


@main.command()
@click.argument("results_dir", type=click.Path(exists=True))
@click.option("--edit-run-id", help="Edit run ID to generate summary for")
@click.option("--judge-run-id", help="Judge run ID to generate summary for")
@click.option("--output-dir", type=click.Path(), help="Output directory for summary files")
def summary(
    results_dir: str,
    edit_run_id: Optional[str],
    judge_run_id: Optional[str],
    output_dir: Optional[str],
) -> None:
    """Generate summary for specific edit/judge runs.

    Use --edit-run-id to filter edits by a specific edit run.
    Use --judge-run-id to filter judges by a specific judge run.
    """
    from long_context_bench.stats import generate_summary_for_runs

    click.echo(f"Generating summary from {results_dir}")
    generate_summary_for_runs(
        results_dir=Path(results_dir),
        edit_run_id=edit_run_id,
        judge_run_id=judge_run_id,
        output_dir=Path(output_dir) if output_dir else None,
    )
    click.echo("Summary generation completed")


@main.command()
@click.argument("results_dir", type=click.Path(exists=True))
@click.argument("test_label")
@click.option("--output-file", type=click.Path(), help="Output file for comparison report (.json or .csv)")
@click.option("--format", type=click.Choice(["comparison", "leaderboard"]), default="comparison",
              help="Output format: comparison (side-by-side) or leaderboard (ranked)")
@click.option("--rank-by", default="mean_aggregate",
              help="Metric to rank by (mean_aggregate, success_rate, tasks_per_hour, etc.)")
def compare(results_dir: str, test_label: str, output_file: Optional[str], format: str, rank_by: str) -> None:
    """Generate comparison or leaderboard for runs with the same test label.

    This command finds all edit and judge runs with the specified test label,
    groups them by runner/model, and generates either a side-by-side comparison
    or a ranked leaderboard.

    Examples:
        # Side-by-side comparison
        long-context-bench compare output/ "sonnet-4.5-comparison" --output-file comparison.csv

        # Leaderboard ranked by aggregate score
        long-context-bench compare output/ "v0-leaderboard" --format leaderboard --output-file leaderboard.csv

        # Leaderboard ranked by success rate
        long-context-bench compare output/ "v0-leaderboard" --format leaderboard --rank-by success_rate
    """
    from long_context_bench.stats import generate_comparison

    click.echo(f"Generating {format} for test label: {test_label}")
    generate_comparison(
        results_dir=Path(results_dir),
        test_label=test_label,
        output_file=Path(output_file) if output_file else None,
        format=format,
        rank_by=rank_by,
    )
    click.echo(f"{format.capitalize()} generation completed")


if __name__ == "__main__":
    main()

