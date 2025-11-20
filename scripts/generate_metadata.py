#!/usr/bin/env python3
"""
Generate lightweight metadata file for head-to-head results.
This extracts only the essential information needed for the PR list,
allowing individual PR data to be loaded on demand.
"""

import json
import sys
from pathlib import Path


def extract_metadata(result_data):
    """Extract lightweight metadata from a full head-to-head result."""
    return {
        'pr_number': result_data.get('pr_number'),
        'pr_id': result_data.get('pr_id'),
        'head_to_head_run_id': result_data.get('head_to_head_run_id'),
        'num_agents': len(result_data.get('agent_results', [])),
        'num_decisions': len(result_data.get('pairwise_decisions', [])),
        'agent_ids': [
            f"{ar['runner']}:{ar['model']}"
            for ar in result_data.get('agent_results', [])
        ],
        # Include agent stats for leaderboard calculation
        'agent_stats': result_data.get('agent_stats', []),
    }


def generate_metadata(output_dir):
    """Generate metadata file from all head-to-head results.

    This scans ``output/head_to_head`` directly instead of relying on the
    web ``index.json`` so that we can:

    * Work even if the index is out of date, and
    * Deduplicate multiple runs for the same PR by keeping only the most
      recent one (based on the result's ``timestamp`` field).
    """

    output_path = Path(output_dir)
    head_to_head_dir = output_path / "head_to_head"

    if not head_to_head_dir.exists():
        print(f"Error: {head_to_head_dir} does not exist")
        return False

    # Collect the newest result per PR number.
    by_pr = {}

    for file_path in sorted(head_to_head_dir.glob("pr*_*.json")):
        if not file_path.is_file():
            continue

        try:
            with open(file_path) as f:
                result_data = json.load(f)
        except Exception as e:  # pragma: no cover - defensive
            print(f"Error reading {file_path}: {e}")
            continue

        pr_number = result_data.get("pr_number")
        if pr_number is None:
            print(f"Warning: {file_path} missing pr_number, skipping")
            continue

        timestamp = result_data.get("timestamp") or ""
        key = int(pr_number)

        prev = by_pr.get(key)
        if prev is None or (timestamp and timestamp > prev["timestamp"]):
            by_pr[key] = {
                "timestamp": timestamp,
                "file_path": file_path,
                "result_data": result_data,
            }

    # Build lightweight metadata list sorted by PR number.
    metadata_list = []
    for pr_number in sorted(by_pr.keys()):
        entry = by_pr[pr_number]
        result_data = entry["result_data"]
        file_path = entry["file_path"]

        try:
            metadata = extract_metadata(result_data)
            # Store path relative to the output directory so the web app can
            # fetch it via ``../{metadata['file']}``.
            metadata["file"] = str(file_path.relative_to(output_path))
            metadata_list.append(metadata)

            print(f"✓ Processed PR {metadata.get('pr_number')} -> {metadata['file']}")
        except Exception as e:  # pragma: no cover - defensive
            print(f"Error processing {file_path}: {e}")
            continue

    # Write primary metadata file next to index.json so that both the dev
    # server (/data/head_to_head_metadata.json) and static hosting
    # (../head_to_head_metadata.json from output/web) can find it.
    metadata_path = output_path / "head_to_head_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump({"results": metadata_list, "count": len(metadata_list)}, f, indent=2)

    # Also copy into output/web for backwards compatibility with any
    # existing static hosts that expect the file there.
    web_metadata_path = output_path / "web" / "head_to_head_metadata.json"
    try:
        web_metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(web_metadata_path, "w") as f:
            json.dump({"results": metadata_list, "count": len(metadata_list)}, f, indent=2)
    except Exception as e:  # pragma: no cover - defensive
        print(f"Warning: failed to write web metadata file: {e}")

    print(f"\n✅ Generated metadata file: {metadata_path}")
    print(f"   {len(metadata_list)} PRs")
    print(f"   Size: {metadata_path.stat().st_size / 1024:.1f} KB")

    return True


if __name__ == '__main__':
    output_dir = sys.argv[1] if len(sys.argv) > 1 else 'output'
    success = generate_metadata(output_dir)
    sys.exit(0 if success else 1)

