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
        # Judge configuration (optional, present for newer runs)
        'judge_mode': result_data.get('judge_mode'),
        'judge_runner': result_data.get('judge_runner'),
        'judge_runner_model': result_data.get('judge_runner_model'),
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
    """Generate metadata file from all head-to-head results."""
    output_path = Path(output_dir)
    head_to_head_dir = output_path / 'head_to_head'
    
    if not head_to_head_dir.exists():
        print(f"Error: {head_to_head_dir} does not exist")
        return False
    
    # Load index to get list of head-to-head files
    index_path = output_path / 'web' / 'index.json'
    if not index_path.exists():
        print(f"Error: {index_path} does not exist")
        return False
    
    with open(index_path) as f:
        index = json.load(f)
    
    metadata_list = []
    
    for run in index.get('head_to_head_runs', []):
        file_path = output_path / run['file']
        
        if not file_path.exists():
            print(f"Warning: {file_path} does not exist, skipping")
            continue
        
        try:
            with open(file_path) as f:
                result_data = json.load(f)
            
            metadata = extract_metadata(result_data)
            metadata['file'] = run['file']  # Store the file path for loading later
            metadata_list.append(metadata)
            
            print(f"✓ Processed {result_data.get('pr_number')}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue
    
    # Write metadata file
    metadata_path = output_path / 'web' / 'head_to_head_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump({
            'results': metadata_list,
            'count': len(metadata_list)
        }, f, indent=2)
    
    print(f"\n✅ Generated metadata file: {metadata_path}")
    print(f"   {len(metadata_list)} PRs")
    print(f"   Size: {metadata_path.stat().st_size / 1024:.1f} KB")
    
    return True


if __name__ == '__main__':
    output_dir = sys.argv[1] if len(sys.argv) > 1 else 'output'
    success = generate_metadata(output_dir)
    sys.exit(0 if success else 1)

