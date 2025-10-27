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
) -> AggregateSummary:
    """Compute aggregate summary statistics.
    
    Per R-5.6-5.9: Aggregate scores and secondary metrics.
    
    Args:
        run_id: Run ID
        samples: List of samples
        edits: List of edits
        judges: List of judges
        
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

