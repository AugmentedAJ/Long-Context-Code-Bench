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
) -> None:
    """Edit stage: Run agent on samples and capture diffs."""
    from long_context_bench.stages.edit import run_edit_stage
    
    click.echo(f"Running edit stage with runner={runner}, model={model}")
    run_edit_stage(
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
    )
    click.echo("Edit stage completed")


@main.command()
@click.argument("sample_path", type=click.Path(exists=True))
@click.argument("edit_path", type=click.Path(exists=True))
@click.option("--judge-mode", type=click.Choice(["deterministic", "llm"]), default="deterministic", help="Judge mode")
@click.option("--judge-model", help="Judge model (for LLM mode)")
@click.option("--output-dir", type=click.Path(), default="output/judges", help="Output directory for judgments")
def judge(
    sample_path: str,
    edit_path: str,
    judge_mode: str,
    judge_model: Optional[str],
    output_dir: str,
) -> None:
    """Judge stage: Score agent edits against ground truth."""
    from long_context_bench.stages.judge import run_judge_stage
    
    click.echo(f"Running judge stage with mode={judge_mode}")
    run_judge_stage(
        sample_path=Path(sample_path),
        edit_path=Path(edit_path),
        judge_mode=judge_mode,
        judge_model=judge_model,
        output_dir=Path(output_dir),
    )
    click.echo("Judge stage completed")


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


if __name__ == "__main__":
    main()

