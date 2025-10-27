"""Command-line interface for Long-Context-Bench."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from long_context_bench import __dataset_version__, __version__
from long_context_bench.editor import Editor
from long_context_bench.judge import Judge
from long_context_bench.models import Sample
from long_context_bench.runners import RunnerConfig
from long_context_bench.sampler import PRSampler
from long_context_bench.utils import (
    compute_shard_assignment,
    get_pr_id,
    load_json,
    setup_logging,
)

console = Console()


@click.group()
@click.version_option(version=__version__)
@click.option("--output-dir", type=click.Path(), default="./output", help="Output directory")
@click.option("--verbose", is_flag=True, help="Enable verbose logging")
@click.option("--quiet", is_flag=True, help="Suppress non-error output")
@click.pass_context
def cli(ctx: click.Context, output_dir: str, verbose: bool, quiet: bool) -> None:
    """Long-Context-Bench: Benchmark for long-context code editing."""
    ctx.ensure_object(dict)
    ctx.obj["output_dir"] = Path(output_dir)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    
    # Setup logging
    setup_logging(verbose=verbose, quiet=quiet)


@cli.command()
@click.argument("input", type=str)
@click.option("--dataset-version", default=__dataset_version__, help="Dataset version")
@click.pass_context
def sample(ctx: click.Context, input: str, dataset_version: str) -> None:
    """Sample PRs and generate task instructions.
    
    INPUT can be:
    - A single PR URL
    - A JSON file containing an array of PR URLs
    - A directory of existing samples
    """
    output_dir = ctx.obj["output_dir"]
    
    logger = logging.getLogger(__name__)
    logger.info(f"Sampling with dataset version: {dataset_version}")
    
    sampler = PRSampler(dataset_version=dataset_version)
    
    # Determine input type
    input_path = Path(input)
    
    if input_path.is_file() and input_path.suffix == ".json":
        # JSON file of URLs
        logger.info(f"Loading PR URLs from {input}")
        with open(input_path) as f:
            url_list = json.load(f)
        
        samples = sampler.sample_from_url_list(url_list, output_dir)
        logger.info(f"Sampled {len(samples)} PRs")
        
    elif input.startswith("http"):
        # Single PR URL
        logger.info(f"Sampling single PR: {input}")
        
        # Parse URL
        parts = input.rstrip("/").split("/")
        pr_number = int(parts[-1])
        repo_url = "/".join(parts[:-2])
        
        sample_result = sampler.sample_pr(repo_url, pr_number, output_dir)
        if sample_result:
            logger.info("Sample created successfully")
        else:
            logger.error("Failed to create sample")
            sys.exit(1)
    else:
        logger.error(f"Invalid input: {input}")
        sys.exit(1)


@cli.command()
@click.option("--runner", required=True, help="Agent runner name")
@click.option("--model", required=True, help="Model name")
@click.option("--agent-binary", type=click.Path(), help="Path to agent binary")
@click.option("--sample-dir", type=click.Path(exists=True), help="Sample directory or file")
@click.option("--timeout", type=int, default=1800, help="Per-task timeout in seconds")
@click.option("--concurrency", type=int, default=1, help="Max concurrent tasks")
@click.option("--total-shards", type=int, default=1, help="Total number of shards")
@click.option("--shard-index", type=int, default=0, help="Shard index (0-based)")
@click.option("--disable-retrieval", is_flag=True, help="Disable codebase retrieval")
@click.option("--disable-shell", is_flag=True, help="Disable shell access")
@click.option("--enable-mcp-codebase-qa", is_flag=True, help="Enable MCP codebase QA")
@click.pass_context
def edit(
    ctx: click.Context,
    runner: str,
    model: str,
    agent_binary: Optional[str],
    sample_dir: Optional[str],
    timeout: int,
    concurrency: int,
    total_shards: int,
    shard_index: int,
    disable_retrieval: bool,
    disable_shell: bool,
    enable_mcp_codebase_qa: bool,
) -> None:
    """Run agent to produce edits."""
    output_dir = ctx.obj["output_dir"]
    
    logger = logging.getLogger(__name__)
    logger.info(f"Running edit stage with runner={runner}, model={model}")
    
    # Load samples
    if sample_dir:
        sample_path = Path(sample_dir)
        if sample_path.is_file():
            # Single sample file
            samples = [Sample(**load_json(sample_path))]
        else:
            # Directory of samples
            samples = []
            for sample_file in sample_path.rglob("sample.json"):
                samples.append(Sample(**load_json(sample_file)))
    else:
        # Load from default location
        samples_dir = output_dir / "samples" / __dataset_version__
        samples = []
        for sample_file in samples_dir.rglob("sample.json"):
            samples.append(Sample(**load_json(sample_file)))
    
    logger.info(f"Loaded {len(samples)} samples")
    
    # Apply sharding
    if total_shards > 1:
        filtered_samples = []
        for sample in samples:
            pr_id = get_pr_id(sample.repo_url, sample.pr_number)
            if compute_shard_assignment(pr_id, total_shards, shard_index):
                filtered_samples.append(sample)
        
        logger.info(
            f"Shard {shard_index}/{total_shards}: {len(filtered_samples)} samples"
        )
        samples = filtered_samples
    
    # Create runner config
    runner_config = RunnerConfig(
        runner=runner,
        model=model,
        agent_binary=agent_binary,
        timeout_s=timeout,
        disable_retrieval=disable_retrieval,
        disable_shell=disable_shell,
        enable_mcp_codebase_qa=enable_mcp_codebase_qa,
    )
    
    # Create editor
    editor = Editor(runner_config=runner_config)
    
    # Run edits
    results = editor.edit_samples(samples, output_dir)
    
    logger.info(f"Completed {len(results)} edits")


@cli.command()
@click.option("--sample-dir", type=click.Path(exists=True), help="Sample directory")
@click.option("--edit-dir", type=click.Path(exists=True), help="Edit directory")
@click.option("--judge-mode", default="deterministic", help="Judge mode: deterministic or llm")
@click.option("--judge-model", help="Judge model (for llm mode)")
@click.option("--concurrency", type=int, default=4, help="Max concurrent tasks")
@click.pass_context
def judge(
    ctx: click.Context,
    sample_dir: Optional[str],
    edit_dir: Optional[str],
    judge_mode: str,
    judge_model: Optional[str],
    concurrency: int,
) -> None:
    """Score agent edits."""
    output_dir = ctx.obj["output_dir"]
    
    logger = logging.getLogger(__name__)
    logger.info(f"Running judge stage with mode={judge_mode}")
    
    # Load samples and edits
    # TODO: Implement loading logic
    
    logger.info("Judge stage not fully implemented yet")


@cli.command()
@click.argument("input", type=str)
@click.option("--runner", required=True, help="Agent runner name")
@click.option("--model", required=True, help="Model name")
@click.option("--agent-binary", type=click.Path(), help="Path to agent binary")
@click.option("--dataset-version", default=__dataset_version__, help="Dataset version")
@click.option("--timeout", type=int, default=1800, help="Per-task timeout in seconds")
@click.option("--concurrency", type=int, default=1, help="Max concurrent tasks")
@click.option("--total-shards", type=int, default=1, help="Total number of shards")
@click.option("--shard-index", type=int, default=0, help="Shard index (0-based)")
@click.option("--disable-retrieval", is_flag=True, help="Disable codebase retrieval")
@click.option("--disable-shell", is_flag=True, help="Disable shell access")
@click.option("--enable-mcp-codebase-qa", is_flag=True, help="Enable MCP codebase QA")
@click.option("--judge-mode", default="deterministic", help="Judge mode")
@click.option("--judge-model", help="Judge model (for llm mode)")
@click.pass_context
def pipeline(ctx: click.Context, input: str, **kwargs) -> None:
    """Run full pipeline (sample → edit → judge)."""
    logger = logging.getLogger(__name__)
    logger.info("Running full pipeline")
    
    # Run sample stage
    ctx.invoke(sample, input=input, dataset_version=kwargs["dataset_version"])
    
    # Run edit stage
    ctx.invoke(
        edit,
        runner=kwargs["runner"],
        model=kwargs["model"],
        agent_binary=kwargs.get("agent_binary"),
        sample_dir=None,
        timeout=kwargs["timeout"],
        concurrency=kwargs["concurrency"],
        total_shards=kwargs["total_shards"],
        shard_index=kwargs["shard_index"],
        disable_retrieval=kwargs["disable_retrieval"],
        disable_shell=kwargs["disable_shell"],
        enable_mcp_codebase_qa=kwargs["enable_mcp_codebase_qa"],
    )
    
    # Run judge stage
    ctx.invoke(
        judge,
        sample_dir=None,
        edit_dir=None,
        judge_mode=kwargs["judge_mode"],
        judge_model=kwargs.get("judge_model"),
        concurrency=kwargs["concurrency"],
    )
    
    logger.info("Pipeline completed")


@cli.command()
@click.argument("run_dir", type=click.Path(exists=True))
@click.option("--format", default="both", help="Output format: json, csv, or both")
@click.pass_context
def stats(ctx: click.Context, run_dir: str, format: str) -> None:
    """Generate statistics and summaries."""
    logger = logging.getLogger(__name__)
    logger.info(f"Generating statistics for {run_dir}")
    
    # TODO: Implement stats generation
    logger.info("Stats generation not fully implemented yet")


def main() -> None:
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()

