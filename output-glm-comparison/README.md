# GLM 4.6 with/without MCP Comparison

This is a special edition of the Long-Context-Code-Bench web UI that compares **GLM 4.6** with and without **MCP (Model Context Protocol)** support.

## Results Summary

### Agents Compared
1. **factory:glm-4.6** - GLM 4.6 without MCP
2. **factory:custom:glm-4.6** - GLM 4.6 with MCP (Auggie MCP)

### Dataset
- **47 PRs** from the Elasticsearch repository (~20,000 files)
- Only PRs where both agents successfully generated edits are included
- All PRs evaluated by the same judge model (Claude Sonnet 4.5)

### Performance Comparison

| Agent | Win Rate | Correctness | Completeness | Code Reuse | Best Practices | Unsol. Docs |
|-------|----------|-------------|--------------|------------|----------------|-------------|
| **factory:glm-4.6** (no MCP) | **27.0%** | -0.39 | -0.36 | -0.24 | -0.28 | 0.47 |
| **factory:custom:glm-4.6** (with MCP) | **21.3%** | -0.42 | -0.43 | -0.24 | -0.33 | 0.43 |

### Key Findings
- **GLM 4.6 without MCP** performs slightly better overall (27.0% vs 21.3% win rate)
- Both versions show similar performance on **Code Reuse** (-0.24)
- The non-MCP version has slightly better **Correctness** and **Completeness** scores
- The non-MCP version has slightly better **Unsolicited Documentation** score (0.47 vs 0.43)

## Viewing the Results

### Option 1: Static Build (Recommended for Deployment)
The `web/` directory contains a complete static build ready for deployment to Cloudflare Pages or any static hosting service.

```bash
cd output-glm-comparison/web
python3 -m http.server 8888
```

Then open http://localhost:8888 in your browser.

See `web/DEPLOYMENT.md` for detailed deployment instructions.

### Option 2: Node.js Server (Development)
```bash
cd long_context_bench/web
OUTPUT_DIR=/Users/ajjoobandi/Development/augmentcode/Long-Context-Code-Bench/output-glm-comparison node server.js
```

Then open http://localhost:3000 in your browser.

### What You Can See
- **Leaderboard**: Side-by-side comparison of both GLM versions
- **Metric Comparison Chart**: Visual comparison across all 5 metrics
- **PR-by-PR Results**: See which agent won on each of the 47 PRs
- **Detailed PR Views**: Click "View Details" to see:
  - Judge's detailed rationale
  - Side-by-side diff comparisons
  - Agent execution logs
  - Metric scores for each agent

## Data Location

All data is symlinked from the main `output/` directory:
- `edits/` → `../output/edits/`
- `judges/` → `../output/judges/`
- `summaries/` → `../output/summaries/`
- `index.json` - Filtered to only include the two GLM agents

## Reproducing the Results

### 1. Judge the MCP Edits
```bash
python3 -m long_context_bench.cli judge \
  --edit-run-ids 6bf04592 \
  --judge-model claude-sonnet-4-5 \
  --output-dir output \
  --concurrency 5
```

### 2. Generate Summary
```bash
python3 -m long_context_bench.cli summary output \
  --edit-run-id 6bf04592 \
  --judge-run-id <judge_run_id> \
  --output-dir output
```

### 3. Create Filtered Index
```bash
python3 << 'EOF'
import json
from pathlib import Path

# Load the full index
with open('output/index.json') as f:
    full_index = json.load(f)

# Filter to only GLM 4.6 runs
filtered_runs = [r for r in full_index['runs'] 
                 if r['runner'] == 'factory' and r['model'] in ['glm-4.6', 'custom:glm-4.6']]

# Find common PRs
glm_46_prs = set(filtered_runs[0]['pr_ids'])
glm_46_mcp_prs = set(filtered_runs[1]['pr_ids'])
common_prs = sorted(glm_46_prs & glm_46_mcp_prs)

# Update both runs to only include common PRs
for run in filtered_runs:
    run['pr_ids'] = [pr for pr in run['pr_ids'] if pr in common_prs]

# Create filtered index
filtered_index = {
    'runs': filtered_runs,
    'cross_agent_runs': [],
    'head_to_head_runs': [],
    'test_labels': list(set(r.get('test_label') for r in filtered_runs if r.get('test_label'))),
    'runners': ['factory'],
    'models': ['glm-4.6', 'custom:glm-4.6'],
    'last_updated': full_index['last_updated']
}

# Save filtered index
with open('output-glm-comparison/index.json', 'w') as f:
    json.dump(filtered_index, f, indent=2)
EOF
```

## Notes

- The MCP version uses the Auggie MCP server for codebase context
- Both versions use the same Factory Droid runner
- All edits were generated on the same dataset (Elasticsearch v1)
- The comparison is fair: only PRs where both agents attempted the task are included

