"""Statistics and reporting."""

import json
from pathlib import Path
from typing import Optional, List
import statistics

import pandas as pd
from rich.console import Console
from rich.table import Table

from long_context_bench.models import Sample, Edit, Judge, AggregateSummary

console = Console()


def compute_aggregate_summary(
    run_id: str,
    samples: List[Sample],
    edits: List[Edit],
    judges: List[Judge],
    edit_run_id: Optional[str] = None,
    judge_run_id: Optional[str] = None,
    test_label: Optional[str] = None,
    runner: Optional[str] = None,
    model: Optional[str] = None,
) -> AggregateSummary:
    """Compute aggregate summary statistics.

    Per R-5.6-5.9: Aggregate scores and secondary metrics.

    Args:
        run_id: Run ID (for legacy/pipeline mode)
        samples: List of samples
        edits: List of edits
        judges: List of judges
        edit_run_id: Optional edit run ID (for staged mode)
        judge_run_id: Optional judge run ID (for staged mode)
        test_label: Optional test label for comparison grouping
        runner: Optional runner name for comparison reports
        model: Optional model name for comparison reports

    Returns:
        AggregateSummary object
    """
    total_samples = len(samples)

    # Count successful/failed/skipped
    successful_samples = sum(1 for e in edits if e.status == "success")
    failed_samples = sum(1 for e in edits if e.status in ["error", "timeout"])
    skipped_samples = total_samples - len(edits)

    success_rate = successful_samples / total_samples if total_samples > 0 else 0.0

    # Compute mean scores
    if judges:
        mean_correctness = statistics.mean(j.scores.correctness for j in judges)
        mean_completeness = statistics.mean(j.scores.completeness for j in judges)
        mean_code_reuse = statistics.mean(j.scores.code_reuse for j in judges)
        mean_best_practices = statistics.mean(j.scores.best_practices for j in judges)
        mean_unsolicited_docs = statistics.mean(j.scores.unsolicited_docs for j in judges)
        mean_aggregate = statistics.mean(j.aggregate for j in judges)

        # Compute standard deviation
        if len(judges) > 1:
            std_aggregate = statistics.stdev(j.aggregate for j in judges)
        else:
            std_aggregate = 0.0
    else:
        mean_correctness = 0.0
        mean_completeness = 0.0
        mean_code_reuse = 0.0
        mean_best_practices = 0.0
        mean_unsolicited_docs = 0.0
        mean_aggregate = 0.0
        std_aggregate = 0.0

    # Compute latency metrics
    if edits:
        mean_elapsed_ms = statistics.mean(e.elapsed_ms for e in edits)
        # Tasks per hour
        mean_elapsed_hours = mean_elapsed_ms / (1000 * 3600)
        tasks_per_hour = 1 / mean_elapsed_hours if mean_elapsed_hours > 0 else 0.0
    else:
        mean_elapsed_ms = 0.0
        tasks_per_hour = 0.0

    # Extract runner and model from edits if not provided
    if not runner and edits:
        runner = edits[0].runner
    if not model and edits:
        model = edits[0].model

    return AggregateSummary(
        run_id=run_id,
        total_samples=total_samples,
        successful_samples=successful_samples,
        failed_samples=failed_samples,
        skipped_samples=skipped_samples,
        success_rate=success_rate,
        mean_correctness=mean_correctness,
        mean_completeness=mean_completeness,
        mean_code_reuse=mean_code_reuse,
        mean_best_practices=mean_best_practices,
        mean_unsolicited_docs=mean_unsolicited_docs,
        mean_aggregate=mean_aggregate,
        std_aggregate=std_aggregate,
        mean_elapsed_ms=mean_elapsed_ms,
        tasks_per_hour=tasks_per_hour,
        edit_run_id=edit_run_id,
        judge_run_id=judge_run_id,
        test_label=test_label,
        runner=runner,
        model=model,
    )


def load_results_from_dir(results_dir: Path) -> tuple[List[Sample], List[Edit], List[Judge]]:
    """Load all results from a directory.
    
    Args:
        results_dir: Results directory
        
    Returns:
        Tuple of (samples, edits, judges)
    """
    samples = []
    edits = []
    judges = []
    
    # Load samples
    samples_dir = results_dir / "samples"
    if samples_dir.exists():
        for sample_file in samples_dir.rglob("sample.json"):
            with open(sample_file) as f:
                samples.append(Sample(**json.load(f)))
    
    # Load edits
    edits_dir = results_dir / "edits"
    if edits_dir.exists():
        for edit_file in edits_dir.rglob("edit.json"):
            with open(edit_file) as f:
                edits.append(Edit(**json.load(f)))
    
    # Load judges
    judges_dir = results_dir / "judges"
    if judges_dir.exists():
        for judge_file in judges_dir.rglob("judge.json"):
            with open(judge_file) as f:
                judges.append(Judge(**json.load(f)))
    
    return samples, edits, judges


def generate_summary_for_runs(
    results_dir: Path,
    edit_run_id: Optional[str] = None,
    judge_run_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> None:
    """Generate summary for specific edit/judge runs.

    Args:
        results_dir: Results directory
        edit_run_id: Optional edit run ID to filter by
        judge_run_id: Optional judge run ID to filter by
        output_dir: Optional output directory for summary files
    """
    console.print(f"[bold]Generating summary from {results_dir}[/bold]")
    if edit_run_id:
        console.print(f"  Edit run ID: {edit_run_id}")
    if judge_run_id:
        console.print(f"  Judge run ID: {judge_run_id}")

    # Load all results
    all_samples, all_edits, all_judges = load_results_from_dir(results_dir)

    # Filter by run IDs
    samples = all_samples
    edits = [e for e in all_edits if not edit_run_id or e.edit_run_id == edit_run_id]
    judges = [j for j in all_judges if not judge_run_id or j.judge_run_id == judge_run_id]

    console.print(f"  Loaded {len(samples)} samples")
    console.print(f"  Filtered to {len(edits)} edits")
    console.print(f"  Filtered to {len(judges)} judges")

    if not samples:
        console.print("[yellow]No samples found[/yellow]")
        return

    # Compute summary
    run_id = judge_run_id or edit_run_id or "summary"
    summary = compute_aggregate_summary(
        run_id=run_id,
        samples=samples,
        edits=edits,
        judges=judges,
        edit_run_id=edit_run_id,
        judge_run_id=judge_run_id,
    )

    # Display table
    table = Table(title="Aggregate Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Samples", str(summary.total_samples))
    table.add_row("Successful", str(summary.successful_samples))
    table.add_row("Failed", str(summary.failed_samples))
    table.add_row("Skipped", str(summary.skipped_samples))
    table.add_row("Success Rate", f"{summary.success_rate:.1%}")
    table.add_row("", "")
    table.add_row("Mean Correctness", f"{summary.mean_correctness:.2f}")
    table.add_row("Mean Completeness", f"{summary.mean_completeness:.2f}")
    table.add_row("Mean Code Reuse", f"{summary.mean_code_reuse:.2f}")
    table.add_row("Mean Best Practices", f"{summary.mean_best_practices:.2f}")
    table.add_row("Mean Unsolicited Docs", f"{summary.mean_unsolicited_docs:.2f}")
    table.add_row("", "")
    table.add_row("Mean Aggregate Score", f"{summary.mean_aggregate:.2f}")
    table.add_row("Std Aggregate Score", f"{summary.std_aggregate:.2f}")
    table.add_row("", "")
    table.add_row("Mean Elapsed (ms)", f"{summary.mean_elapsed_ms:.0f}")
    table.add_row("Tasks/Hour", f"{summary.tasks_per_hour:.2f}")

    console.print(table)

    # Write output files
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

        summary_file = output_dir / "summary.json"
        with open(summary_file, "w") as f:
            f.write(summary.model_dump_json(indent=2))

        csv_file = output_dir / "summary.csv"
        df = pd.DataFrame([summary.model_dump()])
        df.to_csv(csv_file, index=False)

        console.print(f"\n[green]Summary written to {output_dir}[/green]")

    # Per-PR breakdown
    if judges:
        console.print("\n[bold]Per-PR Scores (Top 10)[/bold]")

        pr_table = Table()
        pr_table.add_column("PR", style="cyan")
        pr_table.add_column("Aggregate", style="green")
        pr_table.add_column("Correctness", style="yellow")
        pr_table.add_column("Completeness", style="yellow")

        # Sort by aggregate score
        sorted_judges = sorted(judges, key=lambda j: j.aggregate, reverse=True)

        for judge in sorted_judges[:10]:
            pr_id = f"PR#{judge.pr_number}"
            pr_table.add_row(
                pr_id,
                f"{judge.aggregate:.2f}",
                f"{judge.scores.correctness:.2f}",
                f"{judge.scores.completeness:.2f}",
            )

        console.print(pr_table)


def generate_comparison(
    results_dir: Path,
    test_label: str,
    output_file: Optional[Path] = None,
    format: str = "comparison",
    rank_by: str = "mean_aggregate",
) -> None:
    """Generate comparison or leaderboard report for runs with the same test label.

    Args:
        results_dir: Results directory
        test_label: Test label to filter by
        output_file: Optional output file for comparison report
        format: Output format ('comparison' or 'leaderboard')
        rank_by: Metric to rank by (for leaderboard format)
    """
    console.print(f"[bold]Generating {format} for test label: {test_label}[/bold]")

    # Load all manifests to find runs with this test label
    edit_manifests = []
    judge_manifests = []

    # Find edit run manifests
    edits_dir = results_dir / "edits"
    if edits_dir.exists():
        for manifest_file in edits_dir.rglob("edit_run_manifest.json"):
            with open(manifest_file) as f:
                from long_context_bench.models import EditRunManifest
                manifest = EditRunManifest(**json.load(f))
                if manifest.test_label == test_label:
                    edit_manifests.append(manifest)

    # Find judge run manifests
    judges_dir = results_dir / "judges"
    if judges_dir.exists():
        for manifest_file in judges_dir.rglob("judge_run_manifest.json"):
            with open(manifest_file) as f:
                from long_context_bench.models import JudgeRunManifest
                manifest = JudgeRunManifest(**json.load(f))
                if manifest.test_label == test_label:
                    judge_manifests.append(manifest)

    console.print(f"  Found {len(edit_manifests)} edit run(s)")
    console.print(f"  Found {len(judge_manifests)} judge run(s)")

    if not edit_manifests:
        console.print(f"[yellow]No runs found with test label '{test_label}'[/yellow]")
        return

    # Load all results
    all_samples, all_edits, all_judges = load_results_from_dir(results_dir)

    # Group results by runner/model combination
    from collections import defaultdict
    results_by_agent = defaultdict(lambda: {"samples": [], "edits": [], "judges": []})

    for manifest in edit_manifests:
        agent_key = f"{manifest.runner}/{manifest.model}"

        # Find edits for this run
        run_edits = [e for e in all_edits if e.edit_run_id == manifest.edit_run_id]
        results_by_agent[agent_key]["edits"].extend(run_edits)

        # Find judges for this run
        run_judges = [j for j in all_judges if j.edit_run_id == manifest.edit_run_id]
        results_by_agent[agent_key]["judges"].extend(run_judges)

    # Use all samples for each agent
    for agent_key in results_by_agent:
        results_by_agent[agent_key]["samples"] = all_samples

    # Compute summaries for each agent
    summaries = {}
    for agent_key, data in results_by_agent.items():
        runner, model = agent_key.split("/", 1)
        summary = compute_aggregate_summary(
            run_id=test_label,
            samples=data["samples"],
            edits=data["edits"],
            judges=data["judges"],
            test_label=test_label,
            runner=runner,
            model=model,
        )
        summaries[agent_key] = summary

    if not summaries:
        console.print("[yellow]No results to compare[/yellow]")
        return

    # Display table based on format
    if format == "leaderboard":
        _display_leaderboard(summaries, test_label, rank_by)
    else:
        _display_comparison(summaries, test_label)

    # Write output files
    if output_file:
        if output_file.suffix == ".json":
            # Write JSON with all summaries
            output_data = {
                "test_label": test_label,
                "agents": {k: v.model_dump() for k, v in summaries.items()},
            }
            with open(output_file, "w") as f:
                json.dump(output_data, f, indent=2)
        elif output_file.suffix == ".csv":
            # Write CSV with one row per agent
            df = pd.DataFrame([s.model_dump() for s in summaries.values()])
            df.to_csv(output_file, index=False)

        console.print(f"\n[green]Comparison written to {output_file}[/green]")


def _display_leaderboard(summaries: dict, test_label: str, rank_by: str) -> None:
    """Display leaderboard table with rankings.

    Args:
        summaries: Dictionary of agent_key -> AggregateSummary
        test_label: Test label for the leaderboard
        rank_by: Metric to rank by
    """
    # Validate rank_by metric
    valid_metrics = [
        "mean_aggregate", "success_rate", "tasks_per_hour",
        "mean_correctness", "mean_completeness", "mean_code_reuse",
        "mean_best_practices", "mean_unsolicited_docs"
    ]
    if rank_by not in valid_metrics:
        console.print(f"[yellow]Warning: Unknown metric '{rank_by}', using 'mean_aggregate'[/yellow]")
        rank_by = "mean_aggregate"

    # Sort by ranking metric (higher is better for most metrics)
    sorted_agents = sorted(
        summaries.items(),
        key=lambda x: getattr(x[1], rank_by),
        reverse=True
    )

    # Create leaderboard table
    table = Table(title=f"Leaderboard: {test_label} (ranked by {rank_by})")
    table.add_column("Rank", style="yellow", justify="center", width=6)
    table.add_column("Agent", style="cyan", width=25)
    table.add_column("Success Rate", justify="right", width=13)
    table.add_column("Mean Aggregate", justify="right", width=15)
    table.add_column("Mean Correctness", justify="right", width=17)
    table.add_column("Mean Completeness", justify="right", width=18)
    table.add_column("Tasks/Hour", justify="right", width=12)
    table.add_column("Total Samples", justify="right", width=14)

    for rank, (agent_key, summary) in enumerate(sorted_agents, start=1):
        # Highlight top 3
        rank_style = "bold yellow" if rank == 1 else "bold" if rank <= 3 else ""

        table.add_row(
            str(rank),
            agent_key,
            f"{summary.success_rate:.1%}",
            f"{summary.mean_aggregate:.3f}",
            f"{summary.mean_correctness:.3f}",
            f"{summary.mean_completeness:.3f}",
            f"{summary.tasks_per_hour:.1f}",
            str(summary.total_samples),
            style=rank_style,
        )

    console.print(table)


def _display_comparison(summaries: dict, test_label: str) -> None:
    """Display side-by-side comparison table.

    Args:
        summaries: Dictionary of agent_key -> AggregateSummary
        test_label: Test label for the comparison
    """
    table = Table(title=f"Comparison: {test_label}")
    table.add_column("Metric", style="cyan")

    # Add column for each agent
    agent_keys = sorted(summaries.keys())
    for agent_key in agent_keys:
        table.add_column(agent_key, style="green")

    # Add rows for each metric
    metrics = [
        ("Total Samples", lambda s: str(s.total_samples)),
        ("Successful", lambda s: str(s.successful_samples)),
        ("Failed", lambda s: str(s.failed_samples)),
        ("Success Rate", lambda s: f"{s.success_rate:.1%}"),
        ("", lambda s: ""),  # Separator
        ("Mean Correctness", lambda s: f"{s.mean_correctness:.2f}"),
        ("Mean Completeness", lambda s: f"{s.mean_completeness:.2f}"),
        ("Mean Code Reuse", lambda s: f"{s.mean_code_reuse:.2f}"),
        ("Mean Best Practices", lambda s: f"{s.mean_best_practices:.2f}"),
        ("Mean Unsolicited Docs", lambda s: f"{s.mean_unsolicited_docs:.2f}"),
        ("", lambda s: ""),  # Separator
        ("Mean Aggregate Score", lambda s: f"{s.mean_aggregate:.2f}"),
        ("Std Aggregate Score", lambda s: f"{s.std_aggregate:.2f}"),
        ("", lambda s: ""),  # Separator
        ("Mean Elapsed (ms)", lambda s: f"{s.mean_elapsed_ms:.0f}"),
        ("Tasks/Hour", lambda s: f"{s.tasks_per_hour:.2f}"),
    ]

    for metric_name, metric_fn in metrics:
        row = [metric_name]
        for agent_key in agent_keys:
            row.append(metric_fn(summaries[agent_key]))
        table.add_row(*row)

    console.print(table)


def generate_stats(
    results_dir: Path,
    output_file: Optional[Path] = None,
) -> None:
    """Generate aggregate statistics from results.

    Args:
        results_dir: Results directory
        output_file: Optional output file for stats
    """
    console.print(f"[bold]Generating statistics from {results_dir}[/bold]")

    # Load results
    samples, edits, judges = load_results_from_dir(results_dir)

    console.print(f"  Loaded {len(samples)} samples")
    console.print(f"  Loaded {len(edits)} edits")
    console.print(f"  Loaded {len(judges)} judges")

    if not samples:
        console.print("[yellow]No samples found[/yellow]")
        return

    # Compute summary
    summary = compute_aggregate_summary("stats", samples, edits, judges)

    # Display table
    table = Table(title="Aggregate Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Samples", str(summary.total_samples))
    table.add_row("Successful", str(summary.successful_samples))
    table.add_row("Failed", str(summary.failed_samples))
    table.add_row("Skipped", str(summary.skipped_samples))
    table.add_row("Success Rate", f"{summary.success_rate:.1%}")
    table.add_row("", "")
    table.add_row("Mean Correctness", f"{summary.mean_correctness:.2f}")
    table.add_row("Mean Completeness", f"{summary.mean_completeness:.2f}")
    table.add_row("Mean Code Reuse", f"{summary.mean_code_reuse:.2f}")
    table.add_row("Mean Best Practices", f"{summary.mean_best_practices:.2f}")
    table.add_row("Mean Unsolicited Docs", f"{summary.mean_unsolicited_docs:.2f}")
    table.add_row("", "")
    table.add_row("Mean Aggregate Score", f"{summary.mean_aggregate:.2f}")
    table.add_row("Std Aggregate Score", f"{summary.std_aggregate:.2f}")
    table.add_row("", "")
    table.add_row("Mean Elapsed (ms)", f"{summary.mean_elapsed_ms:.0f}")
    table.add_row("Tasks/Hour", f"{summary.tasks_per_hour:.2f}")

    console.print(table)

    # Write output file
    if output_file:
        if output_file.suffix == ".json":
            with open(output_file, "w") as f:
                f.write(summary.model_dump_json(indent=2))
        elif output_file.suffix == ".csv":
            df = pd.DataFrame([summary.model_dump()])
            df.to_csv(output_file, index=False)

        console.print(f"\n[green]Stats written to {output_file}[/green]")

    # Per-PR breakdown
    if judges:
        console.print("\n[bold]Per-PR Scores (Top 10)[/bold]")

        pr_table = Table()
        pr_table.add_column("PR", style="cyan")
        pr_table.add_column("Aggregate", style="green")
        pr_table.add_column("Correctness", style="yellow")
        pr_table.add_column("Completeness", style="yellow")

        # Sort by aggregate score
        sorted_judges = sorted(judges, key=lambda j: j.aggregate, reverse=True)

        for judge in sorted_judges[:10]:
            pr_id = f"PR#{judge.pr_number}"
            pr_table.add_row(
                pr_id,
                f"{judge.aggregate:.2f}",
                f"{judge.scores.correctness:.2f}",
                f"{judge.scores.completeness:.2f}",
            )

        console.print(pr_table)

