#!/usr/bin/env python3
"""Fix the MCP summary with correct total_samples count."""

import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from long_context_bench.stats import compute_aggregate_summary, update_web_app
from long_context_bench.models import Sample, Edit, Judge

def load_samples_from_dir(samples_dir: Path):
    """Load all samples from a samples directory."""
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

def fix_agent_summary(output_dir: Path, run_id: str, edit_run_id: str, judge_run_id: str, runner: str, model: str, common_prs: set = None):
    """Fix summary for a single agent.

    Args:
        common_prs: If provided, only count PRs that are in this set (PRs where all agents competed)
    """
    print(f"\n{'='*60}")
    print(f"Fixing summary for {runner}/{model} run {run_id}")
    print(f"{'='*60}")

    # Load samples from v1 dataset
    samples_dir = Path("data") / "samples" / "v1"
    samples = load_samples_from_dir(samples_dir)
    print(f"Loaded {len(samples)} samples from {samples_dir}")

    # Load edits
    edit_dir = output_dir / "edits" / runner / model / edit_run_id
    edits = load_edits(edit_dir)
    print(f"Loaded {len(edits)} edits from {edit_dir}")

    # Load judges
    judge_dir = output_dir / "judges" / "llm" / "claude-sonnet-4-5" / judge_run_id
    judges = load_judges(judge_dir)
    print(f"Loaded {len(judges)} judges from {judge_dir}")

    # Filter to common PRs if specified
    if common_prs:
        edits = [e for e in edits if e.pr_number in common_prs]
        judges = [j for j in judges if j.pr_number in common_prs]
        print(f"Filtered to {len(edits)} edits in common PRs")
        print(f"Filtered to {len(judges)} judges in common PRs")

    # Filter samples to only those that were attempted (have edits)
    edit_pr_numbers = {e.pr_number for e in edits}
    samples_attempted = [s for s in samples if s.pr_number in edit_pr_numbers]
    print(f"Filtered to {len(samples_attempted)} samples that were attempted")

    # Use only the samples that were attempted for total_samples
    # This gives us 100% success rate when all attempted PRs succeeded
    print(f"\nUsing {len(samples_attempted)} as total_samples (only attempted PRs)")
    print(f"Successful: {len([e for e in edits if e.status == 'success'])}")
    print(f"Failed: {len([e for e in edits if e.status in ['error', 'timeout']])}")
    print(f"Skipped: {len(samples_attempted) - len(edits)}")

    # Compute summary
    summary = compute_aggregate_summary(
        run_id=run_id,
        samples=samples_attempted,  # Use only attempted samples for correct success rate
        edits=edits,
        judges=judges,
        edit_run_id=edit_run_id,
        judge_run_id=judge_run_id,
        test_label=None,
        runner=runner,
        model=model,
    )

    print(f"\nSummary stats:")
    print(f"  total_samples: {summary.total_samples}")
    print(f"  successful_samples: {summary.successful_samples}")
    print(f"  failed_samples: {summary.failed_samples}")
    print(f"  skipped_samples: {summary.skipped_samples}")
    print(f"  success_rate: {summary.success_rate:.2%}")
    print(f"  mean_aggregate: {summary.mean_aggregate:.3f}")

    # Save summary
    summary_dir = output_dir / "summaries" / f"{run_id}_{runner}_{model}"
    summary_dir.mkdir(parents=True, exist_ok=True)

    summary_file = summary_dir / "summary.json"
    with open(summary_file, "w") as f:
        f.write(summary.model_dump_json(indent=2))
    print(f"\nSaved summary to {summary_file}")


def main():
    output_dir = Path("output")

    # Define all agents to fix
    agents = [
        {
            "run_id": "64fedffe",
            "edit_run_id": "db9474a5",
            "judge_run_id": "64fedffe",
            "runner": "factory",
            "model": "glm-4.6-mcp"
        },
        {
            "run_id": "b7f00db5",
            "edit_run_id": "8d6f99fc",
            "judge_run_id": "b7f00db5",
            "runner": "claude-code",
            "model": "claude-sonnet-4-5"
        },
        {
            "run_id": "0efc4336",
            "edit_run_id": "24634b85",
            "judge_run_id": "0efc4336",
            "runner": "factory",
            "model": "glm-4.6"
        }
    ]

    # Find common PRs (PRs where all agents have edits)
    print("Finding common PRs where all agents competed...")
    agent_prs = {}
    for agent in agents:
        edit_dir = output_dir / "edits" / agent["runner"] / agent["model"] / agent["edit_run_id"]
        prs = set()
        for pr_dir in edit_dir.iterdir():
            if pr_dir.is_dir() and (pr_dir / "edit.json").exists():
                # Extract PR number from directory name (e.g., "elastic_elasticsearch_pr1587" -> 1587)
                pr_id = pr_dir.name
                with open(pr_dir / "edit.json") as f:
                    edit_data = json.load(f)
                    prs.add(edit_data["pr_number"])
        agent_prs[f"{agent['runner']}:{agent['model']}"] = prs
        print(f"  {agent['runner']}:{agent['model']}: {len(prs)} PRs")

    # Find intersection
    common_prs = set.intersection(*agent_prs.values())
    print(f"\nCommon PRs where all {len(agents)} agents competed: {len(common_prs)}")
    print(f"Sample common PRs: {sorted(list(common_prs))[:10]}")

    # Fix each agent with common PRs filter
    for agent in agents:
        try:
            fix_agent_summary(output_dir, **agent, common_prs=common_prs)
        except Exception as e:
            print(f"\n[ERROR] Failed to fix {agent['runner']}:{agent['model']}: {e}")

    # Update web app index
    print(f"\n{'='*60}")
    print("Updating web app index...")
    print(f"{'='*60}")
    update_web_app(output_dir)

    print("\n✓ Done! All agent summaries fixed.")

if __name__ == "__main__":
    main()

