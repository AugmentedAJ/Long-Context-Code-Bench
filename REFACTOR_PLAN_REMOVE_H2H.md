# Refactor Plan: Remove Head-to-Head Evaluation

## Overview

This refactor removes the head-to-head (pairwise agent-as-judge) evaluation system from the benchmark, keeping only the cross-agent analysis (LLM-based comparative evaluation).

## Rationale

- **Cross-agent analysis is sufficient**: It provides individual scores and comparative rankings
- **Simpler architecture**: Removes complex pairwise comparison logic and ELO rating system
- **Reduced complexity**: Eliminates agent-as-judge infrastructure
- **Cleaner web UI**: Single evaluation paradigm is easier to understand

## Scope of Changes

### 1. Data Models (`long_context_bench/models.py`)

**Remove these models:**
- `PairwiseJudgeDecision` - Pairwise comparison results
- `HeadToHeadAgentStats` - Per-agent stats for a single PR
- `HeadToHeadPRResult` - Head-to-head results for a PR
- `HeadToHeadAgentSummary` - Cross-PR summary for an agent
- `HeadToHeadGlobalSummary` - Global summary across PRs

**Keep these models:**
- `AgentResult` - Used by cross-agent analysis
- `CrossAgentJudge` - Main cross-agent analysis model
- `ComparativeAnalysis` - LLM comparative analysis

### 2. Stage Implementation

**Delete entire file:**
- `long_context_bench/stages/head_to_head.py` (670 lines)
  - Contains `run_head_to_head_for_pr()`
  - Contains `run_agent_pairwise_judge()`
  - Contains agent-as-judge prompt generation

### 3. CLI Commands (`long_context_bench/cli.py`)

**Remove:**
- `@main.command(name="head-to-head-pr")` (lines 260-319)
- `--format head-to-head` option from `compare` command (line 562)
- Import: `from long_context_bench.stages.head_to_head import run_head_to_head_for_pr`

**Keep:**
- `analyze-pr` command (cross-agent analysis)
- `compare` command with `comparison` and `leaderboard` formats

### 4. Ranking Utilities (`long_context_bench/ranking.py`)

**Check if file is only used for h2h:**
- `compute_win_loss_matrix()` - Only for h2h
- `compute_elo_ratings()` - Only for h2h
- `rank_agents()` - Only for h2h

**Action:** Delete entire file if only used for head-to-head

### 5. Stats Functions (`long_context_bench/stats.py`)

**Remove:**
- `generate_head_to_head_summary()` function (lines 412-530)
- Import: `HeadToHeadPRResult, HeadToHeadAgentSummary, HeadToHeadGlobalSummary`
- Head-to-head scanning in `generate_index_manifest()` (lines 927-983)

**Update:**
- Remove `head_to_head_runs` from index structure
- Keep cross-agent analysis scanning

### 6. Tests

**Delete these test files:**
- `tests/test_head_to_head_parsing.py` (89 lines)
- `tests/test_ranking.py` (62 lines)

**Update:**
- `tests/test_models.py`: Remove h2h model tests (lines 196-324)

### 7. Web UI - HTML (`long_context_bench/web/`)

**index.html:**
- Remove head-to-head leaderboard section (lines 42-68)
- Keep cross-agent analysis section

**comparison.html:**
- Remove win/loss matrix section (lines 108-122)
- Keep per-PR comparison table

### 8. Web UI - JavaScript

**app.js:**
- Remove `loadHeadToHeadLeaderboard()` (lines 48-69)
- Remove `displayHeadToHeadLeaderboard()` (lines 74-103)
- Remove `loadHeadToHeadPRDetails()` (lines 108-129)
- Remove `displayHeadToHeadPRList()` (lines 134-179)
- Remove `showHeadToHeadDetail()` (lines 185-304)

**data-loader.js:**
- Remove `loadAllHeadToHeadResults()` (lines 565-598)
- Remove `aggregateHeadToHeadData()` (lines 603-647)
- Remove `computeHeadToHeadWinLossMatrix()` (lines 650-689)
- Remove `computeHeadToHeadEloRatings()` (lines 694-730)

### 9. Documentation

**README.md:**
- Remove head-to-head section (lines 185-203)
- Update output structure (remove head_to_head directory)

**plan.md:**
- Remove head-to-head design sections
- Keep cross-agent analysis sections

**DUPLICATE_FIX_SUMMARY.md:**
- Update to reflect cross-agent only
- Remove head-to-head references

### 10. Scripts

**scripts/fix_duplicate_h2h.py:**
- Remove head-to-head handling
- Rename to `fix_duplicate_cross_agent.py`
- Keep only cross-agent deduplication logic

### 11. Data Cleanup

**Remove:**
- `output/head_to_head/` directory and all contents
- `head_to_head_runs` from `output/index.json`
- `head_to_head_runs` from `output/web/index.json`

## Migration Path

1. **Backup existing data** (optional)
2. **Remove code** (models → stages → CLI → stats → tests)
3. **Update web UI** (HTML → JavaScript)
4. **Update documentation**
5. **Clean up data files**
6. **Run tests** to verify

## Impact Assessment

### Breaking Changes
- CLI: `head-to-head-pr` command removed
- CLI: `compare --format head-to-head` removed
- Web UI: Head-to-head leaderboard removed
- Data: `output/head_to_head/` directory no longer used

### No Impact
- Cross-agent analysis continues to work
- Existing cross-agent data is preserved
- Web UI cross-agent views unchanged

## Testing Strategy

1. Run `pytest` to ensure all tests pass
2. Verify cross-agent analysis still works:
   ```bash
   long-context-bench analyze-pr --pr-number 114869 --judge-model anthropic/claude-3-5-sonnet-20241022
   ```
3. Verify web UI loads without errors
4. Check that index.json is valid

## Estimated Effort

- **Code removal**: ~1500 lines
- **Test updates**: ~200 lines
- **Documentation**: ~100 lines
- **Total time**: 2-3 hours

## Files to Modify

1. `long_context_bench/models.py` - Remove 5 models
2. `long_context_bench/cli.py` - Remove 1 command, update 1 command
3. `long_context_bench/stats.py` - Remove 1 function, update index generation
4. `long_context_bench/web/index.html` - Remove leaderboard section
5. `long_context_bench/web/app.js` - Remove 5 functions
6. `long_context_bench/web/data-loader.js` - Remove 4 functions
7. `long_context_bench/web/comparison.html` - Remove matrix section
8. `tests/test_models.py` - Remove h2h tests
9. `README.md` - Remove h2h documentation
10. `scripts/fix_duplicate_h2h.py` - Simplify and rename

## Files to Delete

1. `long_context_bench/stages/head_to_head.py`
2. `long_context_bench/ranking.py` (if only used for h2h)
3. `tests/test_head_to_head_parsing.py`
4. `tests/test_ranking.py`
5. `output/head_to_head/` (directory)

