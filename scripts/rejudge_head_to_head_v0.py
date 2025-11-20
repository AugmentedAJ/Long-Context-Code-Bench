#!/usr/bin/env python3
"""Re-run head-to-head for all v0 PRs with the canonical judge.

This script:
  * Finds all PRs in output/cross_agent_analysis judged with
    test_label == "v0" and judge_model == CANONICAL_JUDGE_MODEL.
  * Deletes any existing head-to-head results and logs for those PRs.
  * Re-runs head-to-head using claude-code / claude-sonnet-4-5 as the
    pairwise judge, reusing scalar scores from the same LLM judge
    model used for cross-agent analysis.

It does NOT call generate_metadata.py or regenerate index.json; run
those separately after this script finishes.

Usage (from repo root):
  python scripts/rejudge_head_to_head_v0.py output
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List, Set
import shutil

from long_context_bench.stages.head_to_head import run_head_to_head_for_pr


CANONICAL_JUDGE_MODEL = "openai/claude-sonnet-4-5-20250929"
CANONICAL_JUDGE_RUNNER = "claude-code"
CANONICAL_JUDGE_RUNNER_MODEL = "claude-sonnet-4-5"
CANONICAL_TEST_LABEL = "v0"


def discover_v0_pr_numbers(output_dir: Path) -> List[int]:
    """Discover PR numbers that have v0 cross-agent analysis.

    We restrict to artifacts where both test_label and judge_model
    match the canonical v0 configuration so we only re-run
    head-to-head where the scalar LLM judge is consistent.
    """

    ca_dir = output_dir / "cross_agent_analysis"
    if not ca_dir.exists():
        return []

    prs: Set[int] = set()
    for path in ca_dir.glob("pr*_*.json"):
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue

        if data.get("test_label") != CANONICAL_TEST_LABEL:
            continue
        if data.get("judge_model") != CANONICAL_JUDGE_MODEL:
            continue

        m = re.match(r"pr(\d+)_", path.name)
        if not m:
            continue
        prs.add(int(m.group(1)))

    return sorted(prs)


def delete_head_to_head_artifacts_for_pr(output_dir: Path, pr_number: int) -> None:
    """Remove existing head-to-head JSON and logs for a PR.

    This ensures we fully drop legacy multi-judge experiments before
    writing fresh single-judge results.
    """

    h2h_dir = output_dir / "head_to_head"
    if h2h_dir.exists():
        for path in h2h_dir.glob(f"pr{pr_number}_*.json"):
            print(f"  Deleting old head-to-head result: {path}")
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    logs_root = h2h_dir / "logs"
    if logs_root.exists():
        for path in logs_root.glob(f"pr{pr_number}_*"):
            print(f"  Deleting old head-to-head logs: {path}")
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass


def main(raw_output_dir: str) -> None:
    output_dir = Path(raw_output_dir).resolve()
    if not output_dir.exists():
        print(f"Error: output directory {output_dir} does not exist")
        sys.exit(1)

    pr_numbers = discover_v0_pr_numbers(output_dir)
    if not pr_numbers:
        print(f"No v0 cross-agent analysis files found under {output_dir}")
        return

    print(f"Found {len(pr_numbers)} v0 PRs: {pr_numbers}")
    cache_dir = Path(".repo_cache")

    for pr in pr_numbers:
        print(f"\n=== Re-running head-to-head for PR {pr} ===")
        delete_head_to_head_artifacts_for_pr(output_dir, pr)

        run_id = run_head_to_head_for_pr(
            pr_number=pr,
            output_dir=output_dir,
            judge_model=CANONICAL_JUDGE_MODEL,
            include_codebase_context=False,
            test_label=CANONICAL_TEST_LABEL,
            cache_dir=cache_dir,
            force=True,
            judge_runner=CANONICAL_JUDGE_RUNNER,
            judge_runner_model=CANONICAL_JUDGE_RUNNER_MODEL,
        )

        if not run_id:
            print(f"!! Head-to-head evaluation failed or was skipped for PR {pr}")
        else:
            print(f"  ✓ New head-to-head run ID for PR {pr}: {run_id}")

    print("\nAll requested PRs processed.")
    print("Next steps:")
    print("  1) Regenerate head-to-head metadata:")
    print("       python scripts/generate_metadata.py", output_dir)
    print("  2) Regenerate index.json for the web app (optional but recommended):")
    print("       python - << 'PY'")
    print("from pathlib import Path")
    print("from long_context_bench.stats import generate_index_manifest")
    print("generate_index_manifest(Path('output'))")
    print("PY")


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "output"
    main(out_dir)

