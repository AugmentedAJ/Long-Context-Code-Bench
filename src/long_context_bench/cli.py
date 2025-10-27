"""Command-line interface for the benchmark."""

import json
import logging
import sys
from pathlib import Path

import click

from . import __version__
from .config import BenchmarkConfig
from .pipeline import BenchmarkPipeline
from .sampler import PRSampler
from .utils import load_json, setup_logging

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__)
@click.option('--log-level', default='INFO', help='Logging level')
def cli(log_level: str):
    """Long-Context-Bench: Benchmark for evaluating long-context code editing."""
    setup_logging(log_level)


@cli.command()
@click.argument('pr_url')
@click.option('--output-dir', default='output', help='Output directory')
@click.option('--dataset-version', default='v0', help='Dataset version')
def sample(pr_url: str, output_dir: str, dataset_version: str):
    """Sample a single PR to create a benchmark task."""
    config = BenchmarkConfig(
        output_root=Path(output_dir),
        dataset_version=dataset_version
    )
    config.ensure_directories()
    
    sampler = PRSampler(config)
    result = sampler.sample_pr(pr_url)
    
    if result:
        click.echo(f"✓ Sample created successfully")
        sys.exit(0)
    else:
        click.echo(f"✗ Failed to create sample", err=True)
        sys.exit(1)


@cli.command()
@click.argument('input_path')
@click.option('--runner', required=True, help='Runner name (e.g., auggie)')
@click.option('--model', required=True, help='Model name')
@click.option('--agent-binary', help='Path to agent binary')
@click.option('--timeout', default=1800, help='Timeout in seconds')
@click.option('--output-dir', default='output', help='Output directory')
def edit(
    input_path: str,
    runner: str,
    model: str,
    agent_binary: str,
    timeout: int,
    output_dir: str
):
    """Run edit stage on a sample."""
    click.echo("Edit stage not yet implemented as standalone command")
    click.echo("Use 'pipeline' command instead")
    sys.exit(1)


@cli.command()
@click.argument('input_path')
@click.option('--judge-mode', default='deterministic', help='Judge mode')
@click.option('--judge-model', help='Judge model (for LLM mode)')
@click.option('--output-dir', default='output', help='Output directory')
def judge(
    input_path: str,
    judge_mode: str,
    judge_model: str,
    output_dir: str
):
    """Run judge stage on edit results."""
    click.echo("Judge stage not yet implemented as standalone command")
    click.echo("Use 'pipeline' command instead")
    sys.exit(1)


@cli.command()
@click.argument('input_source')
@click.option('--runner', required=True, help='Runner name (e.g., auggie)')
@click.option('--model', required=True, help='Model name')
@click.option('--agent-binary', help='Path to agent binary')
@click.option('--timeout', default=1800, help='Timeout in seconds')
@click.option('--concurrency', default=1, help='Number of concurrent tasks')
@click.option('--total-shards', default=1, help='Total number of shards')
@click.option('--shard-index', default=0, help='Shard index (0-based)')
@click.option('--judge-mode', default='deterministic', help='Judge mode')
@click.option('--judge-model', help='Judge model (for LLM mode)')
@click.option('--output-dir', default='output', help='Output directory')
@click.option('--dataset-version', default='v0', help='Dataset version')
@click.option('--disable-retrieval', is_flag=True, help='Disable retrieval')
@click.option('--disable-shell', is_flag=True, help='Disable shell')
@click.option('--enable-mcp-codebase-qa', is_flag=True, help='Enable MCP codebase QA')
def pipeline(
    input_source: str,
    runner: str,
    model: str,
    agent_binary: str,
    timeout: int,
    concurrency: int,
    total_shards: int,
    shard_index: int,
    judge_mode: str,
    judge_model: str,
    output_dir: str,
    dataset_version: str,
    disable_retrieval: bool,
    disable_shell: bool,
    enable_mcp_codebase_qa: bool
):
    """Run complete pipeline (sample → edit → judge)."""
    
    # Parse input source
    pr_urls = _parse_input_source(input_source)
    
    if not pr_urls:
        click.echo("✗ No PRs to process", err=True)
        sys.exit(1)
    
    click.echo(f"Processing {len(pr_urls)} PRs")
    
    # Create configuration
    config = BenchmarkConfig(
        output_root=Path(output_dir),
        dataset_version=dataset_version,
        runner=runner,
        model=model,
        agent_binary=agent_binary,
        timeout=timeout,
        concurrency=concurrency,
        total_shards=total_shards,
        shard_index=shard_index,
        judge_mode=judge_mode,
        judge_model=judge_model,
        disable_retrieval=disable_retrieval,
        disable_shell=disable_shell,
        enable_mcp_codebase_qa=enable_mcp_codebase_qa
    )
    config.ensure_directories()
    
    # Run pipeline
    pipeline_runner = BenchmarkPipeline(config)
    summary = pipeline_runner.run_pipeline(pr_urls)
    
    # Display summary
    click.echo("\n" + "="*60)
    click.echo("SUMMARY")
    click.echo("="*60)
    click.echo(f"Run ID: {summary['run_id']}")
    click.echo(f"Total samples: {summary['total_samples']}")
    click.echo(f"Successful: {summary['successful_samples']}")
    
    if summary['metrics']:
        click.echo("\nMetrics:")
        for metric, values in summary['metrics'].items():
            click.echo(f"  {metric}: {values['mean']:.3f}")
    
    click.echo("="*60)


@cli.command()
@click.argument('summary_path')
def stats(summary_path: str):
    """Display statistics from a summary file."""
    try:
        summary = load_json(Path(summary_path))
        
        click.echo("="*60)
        click.echo("BENCHMARK STATISTICS")
        click.echo("="*60)
        click.echo(f"Run ID: {summary.get('run_id', 'N/A')}")
        click.echo(f"Total samples: {summary.get('total_samples', 0)}")
        click.echo(f"Successful: {summary.get('successful_samples', 0)}")
        
        metrics = summary.get('metrics', {})
        if metrics:
            click.echo("\nMetrics:")
            for metric, values in metrics.items():
                click.echo(f"  {metric}:")
                click.echo(f"    Mean: {values.get('mean', 0):.3f}")
                click.echo(f"    Min:  {values.get('min', 0):.3f}")
                click.echo(f"    Max:  {values.get('max', 0):.3f}")
        
        click.echo("="*60)
        
    except Exception as e:
        click.echo(f"✗ Error reading summary: {e}", err=True)
        sys.exit(1)


def _parse_input_source(input_source: str) -> list[str]:
    """Parse input source into list of PR URLs.
    
    Args:
        input_source: Single URL, path to JSON file, or directory
        
    Returns:
        List of PR URLs
    """
    # Check if it's a URL
    if input_source.startswith('http'):
        return [input_source]
    
    # Check if it's a JSON file
    path = Path(input_source)
    if path.is_file() and path.suffix == '.json':
        data = load_json(path)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and 'prs' in data:
            return data['prs']
        else:
            logger.error(f"Invalid JSON format in {input_source}")
            return []
    
    # Check if it's a directory with samples
    if path.is_dir():
        # TODO: Load samples from directory
        logger.error("Directory input not yet implemented")
        return []
    
    logger.error(f"Invalid input source: {input_source}")
    return []


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main()

