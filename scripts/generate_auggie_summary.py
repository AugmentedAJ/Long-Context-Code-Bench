#!/usr/bin/env python3
"""Generate missing summary for auggie run c7a3f90a."""

import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from long_context_bench.stats import compute_aggregate_summary, update_web_app
from long_context_bench.models import Sample, Edit, Judge

def load_samples(samples_dir: Path):
    """Load all samples."""
    samples = []
    for sample_file in samples_dir.rglob("sample.json"):
        with open(sample_file) as f:
            samples.append(Sample(**json.load(f)))
    return samples

def load_edits(edit_dir: Path):
    """Load edits from a specific edit directory."""
    edits = []
    for edit_file in edit_dir.rglob("edit.json"):
        with open(edit_file) as f:
            edits.append(Edit(**json.load(f)))
    return edits

def load_judges(judge_dir: Path):
    """Load judges from a specific judge directory."""
    judges = []
    for judge_file in judge_dir.rglob("judge.json"):
        with open(judge_file) as f:
            judges.append(Judge(**json.load(f)))
    return judges

def main():
    output_dir = Path("output")
    run_id = "c7a3f90a"
    runner = "auggie"
    model = "sonnet4.5"
    test_label = "v0"
    
    print(f"Generating summary for {runner}/{model} run {run_id}")
    
    # Load samples
    samples_dir = Path("data/samples/v0")
    samples = load_samples(samples_dir)
    print(f"Loaded {len(samples)} samples")
    
    # Load auggie edits
    edit_dir = output_dir / "edits" / runner / model / run_id
    edits = load_edits(edit_dir)
    print(f"Loaded {len(edits)} edits from {edit_dir}")
    
    # Load judges for auggie's PRs
    judge_dir = output_dir / "judges" / "deterministic" / "default" / run_id
    judges = load_judges(judge_dir)
    print(f"Loaded {len(judges)} judges from {judge_dir}")
    
    # Filter judges to only include PRs that auggie ran on
    auggie_pr_numbers = {e.pr_number for e in edits}
    judges = [j for j in judges if j.pr_number in auggie_pr_numbers]
    print(f"Filtered to {len(judges)} judges for auggie's PRs")
    
    # Compute summary
    summary = compute_aggregate_summary(
        run_id=run_id,
        samples=samples,
        edits=edits,
        judges=judges,
        edit_run_id=run_id,
        judge_run_id=run_id,
        test_label=test_label,
        runner=runner,
        model=model,
    )
    
    print(f"\nSummary:")
    print(f"  Success rate: {summary.success_rate:.1%}")
    print(f"  Mean aggregate: {summary.mean_aggregate:.2f}")
    print(f"  Tasks/hour: {summary.tasks_per_hour:.2f}")
    
    # Save summary in the shared run directory
    summaries_dir = output_dir / "summaries" / run_id
    summaries_dir.mkdir(parents=True, exist_ok=True)
    
    summary_file = summaries_dir / f"summary_{runner}_{model}.json"
    with open(summary_file, "w") as f:
        f.write(summary.model_dump_json(indent=2))
    print(f"\nSaved summary to {summary_file}")
    
    # Also create a separate run directory for the web app
    agent_run_dir = output_dir / "summaries" / f"{run_id}_{runner}_{model}"
    agent_run_dir.mkdir(parents=True, exist_ok=True)
    
    agent_summary_file = agent_run_dir / "summary.json"
    with open(agent_summary_file, "w") as f:
        f.write(summary.model_dump_json(indent=2))
    print(f"Saved summary to {agent_summary_file}")
    
    # Update web app index
    print("\nUpdating web app index...")
    update_web_app(output_dir)
    
    print("\n✓ Done! Auggie results should now appear in the web dashboard.")

if __name__ == "__main__":
    main()

