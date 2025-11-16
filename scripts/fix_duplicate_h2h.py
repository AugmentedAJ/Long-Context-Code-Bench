#!/usr/bin/env python3
"""Fix duplicate head-to-head and cross-agent results by keeping only the latest per PR."""

import json
from pathlib import Path
from datetime import datetime

def fix_duplicate_cross_agent_results(output_dir: Path):
    """Fix duplicate cross-agent results in index.json."""

    print("\nFixing duplicate cross-agent results...")

    # Load current index
    index_file = output_dir / "index.json"
    if not index_file.exists():
        print(f"Error: {index_file} not found")
        return

    with open(index_file) as f:
        index = json.load(f)

    # Group cross-agent results by PR number
    ca_dir = output_dir / "cross_agent_analysis"
    if not ca_dir.exists():
        print(f"No cross_agent_analysis directory found")
        return

    pr_to_results = {}

    for ca_file in ca_dir.glob("pr*_*.json"):
        try:
            with open(ca_file) as f:
                result = json.load(f)

            pr_number = result.get("pr_number")
            if pr_number is None:
                continue

            ca_info = {
                "file": ca_file.name,
                "pr_number": pr_number,
                "analysis_run_id": result.get("analysis_run_id"),
                "test_label": result.get("test_label"),
                "judge_mode": result.get("judge_mode"),
                "judge_model": result.get("judge_model"),
                "timestamp": result.get("timestamp"),
                "file_path": ca_file,
            }

            if pr_number not in pr_to_results:
                pr_to_results[pr_number] = []
            pr_to_results[pr_number].append(ca_info)

        except Exception as e:
            print(f"Warning: Failed to process {ca_file}: {e}")

    # Find duplicates and keep only the latest
    new_ca_runs = []
    duplicates_to_remove = []

    for pr_number, results in sorted(pr_to_results.items()):
        if len(results) == 1:
            # Only one result, keep it
            result = results[0]
            new_ca_runs.append({
                "file": result["file"],
                "pr_number": result["pr_number"],
                "analysis_run_id": result["analysis_run_id"],
                "test_label": result["test_label"],
                "judge_mode": result["judge_mode"],
                "judge_model": result["judge_model"],
            })
        else:
            # Multiple results, sort by timestamp and keep the latest
            print(f"\nPR {pr_number}: Found {len(results)} results")

            results_with_timestamp = [r for r in results if r.get("timestamp")]
            if results_with_timestamp:
                results_with_timestamp.sort(key=lambda r: r["timestamp"], reverse=True)
                latest = results_with_timestamp[0]

                print(f"  Keeping: {latest['file']} (timestamp: {latest['timestamp']})")
                new_ca_runs.append({
                    "file": latest["file"],
                    "pr_number": latest["pr_number"],
                    "analysis_run_id": latest["analysis_run_id"],
                    "test_label": latest["test_label"],
                    "judge_mode": latest["judge_mode"],
                    "judge_model": latest["judge_model"],
                })

                # Mark others for removal
                for r in results:
                    if r["file"] != latest["file"]:
                        print(f"  Removing: {r['file']} (timestamp: {r.get('timestamp', 'N/A')})")
                        duplicates_to_remove.append(r["file_path"])
            else:
                # No timestamps, just keep the first one
                print(f"  No timestamps found, keeping first: {results[0]['file']}")
                new_ca_runs.append({
                    "file": results[0]["file"],
                    "pr_number": results[0]["pr_number"],
                    "analysis_run_id": results[0]["analysis_run_id"],
                    "test_label": results[0]["test_label"],
                    "judge_mode": results[0]["judge_mode"],
                    "judge_model": results[0]["judge_model"],
                })

                for r in results[1:]:
                    print(f"  Removing: {r['file']}")
                    duplicates_to_remove.append(r["file_path"])

    # Update index
    index["cross_agent_runs"] = new_ca_runs
    index["last_updated"] = datetime.utcnow().isoformat()

    # Write updated index
    with open(index_file, "w") as f:
        json.dump(index, f, indent=2)

    print(f"\n✓ Updated {index_file}")
    print(f"  Total cross-agent results: {len(new_ca_runs)}")
    print(f"  Duplicates found: {len(duplicates_to_remove)}")

    # Also update web/index.json
    web_index_file = output_dir / "web" / "index.json"
    if web_index_file.exists():
        with open(web_index_file, "w") as f:
            json.dump(index, f, indent=2)
        print(f"✓ Updated {web_index_file}")

    return duplicates_to_remove

def fix_duplicate_h2h_results(output_dir: Path):
    """Fix duplicate head-to-head results in index.json."""
    
    print("Fixing duplicate head-to-head results...")
    
    # Load current index
    index_file = output_dir / "index.json"
    if not index_file.exists():
        print(f"Error: {index_file} not found")
        return
    
    with open(index_file) as f:
        index = json.load(f)
    
    # Group head-to-head results by PR number
    h2h_dir = output_dir / "head_to_head"
    if not h2h_dir.exists():
        print(f"No head_to_head directory found")
        return
    
    pr_to_results = {}
    
    for h2h_file in h2h_dir.glob("pr*_*.json"):
        try:
            with open(h2h_file) as f:
                result = json.load(f)
            
            pr_number = result.get("pr_number")
            if pr_number is None:
                continue
            
            h2h_info = {
                "file": h2h_file.name,
                "pr_number": pr_number,
                "head_to_head_run_id": result.get("head_to_head_run_id"),
                "test_label": result.get("test_label"),
                "timestamp": result.get("timestamp"),
                "file_path": h2h_file,
            }
            
            if pr_number not in pr_to_results:
                pr_to_results[pr_number] = []
            pr_to_results[pr_number].append(h2h_info)
            
        except Exception as e:
            print(f"Warning: Failed to process {h2h_file}: {e}")
    
    # Find duplicates and keep only the latest
    new_h2h_runs = []
    duplicates_to_remove = []
    
    for pr_number, results in sorted(pr_to_results.items()):
        if len(results) == 1:
            # Only one result, keep it
            result = results[0]
            new_h2h_runs.append({
                "file": result["file"],
                "pr_number": result["pr_number"],
                "head_to_head_run_id": result["head_to_head_run_id"],
                "test_label": result["test_label"],
            })
        else:
            # Multiple results, sort by timestamp and keep the latest
            print(f"\nPR {pr_number}: Found {len(results)} results")
            
            results_with_timestamp = [r for r in results if r.get("timestamp")]
            if results_with_timestamp:
                results_with_timestamp.sort(key=lambda r: r["timestamp"], reverse=True)
                latest = results_with_timestamp[0]
                
                print(f"  Keeping: {latest['file']} (timestamp: {latest['timestamp']})")
                new_h2h_runs.append({
                    "file": latest["file"],
                    "pr_number": latest["pr_number"],
                    "head_to_head_run_id": latest["head_to_head_run_id"],
                    "test_label": latest["test_label"],
                })
                
                # Mark others for removal
                for r in results:
                    if r["file"] != latest["file"]:
                        print(f"  Removing: {r['file']} (timestamp: {r.get('timestamp', 'N/A')})")
                        duplicates_to_remove.append(r["file_path"])
            else:
                # No timestamps, just keep the first one
                print(f"  No timestamps found, keeping first: {results[0]['file']}")
                new_h2h_runs.append({
                    "file": results[0]["file"],
                    "pr_number": results[0]["pr_number"],
                    "head_to_head_run_id": results[0]["head_to_head_run_id"],
                    "test_label": results[0]["test_label"],
                })
                
                for r in results[1:]:
                    print(f"  Removing: {r['file']}")
                    duplicates_to_remove.append(r["file_path"])
    
    # Update index
    index["head_to_head_runs"] = new_h2h_runs
    index["last_updated"] = datetime.utcnow().isoformat()
    
    # Write updated index
    with open(index_file, "w") as f:
        json.dump(index, f, indent=2)
    
    print(f"\n✓ Updated {index_file}")
    print(f"  Total head-to-head results: {len(new_h2h_runs)}")
    print(f"  Duplicates found: {len(duplicates_to_remove)}")
    
    # Also update web/index.json
    web_index_file = output_dir / "web" / "index.json"
    if web_index_file.exists():
        with open(web_index_file, "w") as f:
            json.dump(index, f, indent=2)
        print(f"✓ Updated {web_index_file}")

    return duplicates_to_remove

if __name__ == "__main__":
    output_dir = Path("output")

    # Fix cross-agent duplicates
    ca_duplicates = fix_duplicate_cross_agent_results(output_dir)

    # Fix head-to-head duplicates
    h2h_duplicates = fix_duplicate_h2h_results(output_dir)

    # Combine all duplicates for removal
    all_duplicates = (ca_duplicates or []) + (h2h_duplicates or [])

    if all_duplicates:
        print(f"\n{'='*60}")
        print(f"SUMMARY: Found {len(all_duplicates)} total duplicate files")
        print(f"{'='*60}")
        for file_path in all_duplicates:
            print(f"  - {file_path.name}")

        response = input("\nRemove all duplicate files? (y/N): ").strip().lower()
        if response == 'y':
            for file_path in all_duplicates:
                file_path.unlink()
                print(f"  Removed: {file_path.name}")
            print(f"\n✓ Removed {len(all_duplicates)} duplicate files")
        else:
            print("\nDuplicate files kept (not removed)")
    else:
        print("\n✓ No duplicates found!")

