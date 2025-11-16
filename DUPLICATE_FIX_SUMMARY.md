# Duplicate Judge Data Fix Summary

## Problem

The benchmark had duplicate judge data files for some PRs:
- **Head-to-Head Results**: 47 files instead of 40 (8 PRs had duplicates)
- **Cross-Agent Analysis**: 42 files instead of 40 (2 PRs had duplicates)

This occurred because multiple runs of the judging process created new files for the same PRs without cleaning up old ones.

## Root Cause

The `generate_index_manifest()` function in `long_context_bench/stats.py` was adding ALL judge files to the index without deduplication. When multiple judge runs were performed on the same PR, both old and new results were included.

## Solution

### 1. Updated `stats.py`

Modified the `generate_index_manifest()` function to:
- Group results by PR number
- Keep only the latest result per PR (based on timestamp)
- Log when duplicates are found and which file is kept

This applies to both:
- Head-to-head results (`output/head_to_head/`)
- Cross-agent analyses (`output/cross_agent_analysis/`)

### 2. Created Cleanup Script

Created `scripts/fix_duplicate_h2h.py` to:
- Scan existing data for duplicates
- Update `index.json` to include only the latest result per PR
- Optionally remove duplicate files from disk

## Results

After running the fix:

### Head-to-Head Results
- **Before**: 47 files (8 duplicates)
- **After**: 40 files (1 per PR)
- **Duplicates Removed**:
  - pr114860_21d918ff.json (older)
  - pr114974_bfcbfe6a.json (older)
  - pr114977_8c97dc64.json (older)
  - pr114980_1b8e91c2.json (older)
  - pr114983_f8d0f5a3.json (older)
  - pr114986_445cd405.json (older)
  - pr114989_847140eb.json (older)
  - pr114992_764ebc04.json (older)

### Cross-Agent Analysis
- **Before**: 42 files (2 duplicates)
- **After**: 40 files (1 per PR)
- **Duplicates Removed**:
  - pr114854_8428e5d5.json (older)
  - pr114869_75a175ed.json (older)

## Data Integrity

Each PR now has exactly one result showing:
- **3 unique agent-model combinations**:
  - auggie:sonnet4.5
  - claude-code:claude-sonnet-4-5
  - factory:claude-sonnet-4-5-20250929
- **All pairwise comparisons** between these agents
- **Latest judge evaluations** with most recent timestamps

## Web UI Impact

The web UI now correctly displays:
- 40 PRs in the head-to-head leaderboard
- 40 PRs in the cross-agent analysis
- No duplicate entries per PR
- Consistent agent statistics across all views

## Prevention

Going forward, the updated `generate_index_manifest()` function will automatically:
1. Detect when multiple results exist for the same PR
2. Keep only the latest one (by timestamp)
3. Log a warning message about the deduplication

This ensures the index always reflects the most recent judge evaluations without manual intervention.

## How to Run the Fix Script

If you encounter duplicates in the future:

```bash
python scripts/fix_duplicate_h2h.py
```

The script will:
1. Scan for duplicates in both head-to-head and cross-agent results
2. Update `index.json` and `web/index.json`
3. Prompt you to remove duplicate files (optional)

