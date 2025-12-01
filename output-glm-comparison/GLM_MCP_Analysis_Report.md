# GLM 4.6 Performance Analysis: With vs Without MCP

## Executive Summary

This report analyzes the performance of GLM 4.6 model on Elasticsearch PR tasks, comparing runs with and without MCP (Model Context Protocol) context retrieval capabilities. **Contrary to the hypothesis that MCP would improve performance through better context retrieval, the data shows GLM performed worse with MCP enabled.**

---

## 1. Data Overview

### Sample Sizes and Completion Rates

| Metric | GLM 4.6 (No MCP) | GLM 4.6 (With MCP) |
|--------|------------------|-------------------|
| Total PR directories | 100 | 84 |
| PRs with logs | 100 | 48 |
| PRs with edit.json | 100 | 47 |
| PRs judged | 100 | 47 |
| Completion rate | 100.0% | 57.1% |
| Empty directories | 0 | 36 |

**Observation:** The MCP run had significant completion issues, with 36 empty directories (42.9% of attempts) and only 47 PRs successfully judged compared to 100 in the non-MCP run.

---

## 2. Performance Metrics Comparison

### Overall Scores (from summary.json)

| Metric | GLM 4.6 (No MCP) | GLM 4.6 (With MCP) | Difference |
|--------|------------------|-------------------|------------|
| Win Rate | 27.0% | 21.3% | -5.7% |
| Mean Aggregate | -0.1607 | -0.2011 | -0.0404 |
| Mean Correctness | -0.3915 | -0.4234 | -0.0319 |
| Mean Completeness | -0.3625 | -0.4309 | -0.0684 |
| Mean Code Reuse | -0.2375 | -0.2447 | -0.0072 |
| Mean Best Practices | -0.2830 | -0.3319 | -0.0489 |
| Mean Unsolicited Docs | 0.4710 | 0.4255 | -0.0455 |

### Score Distribution

| Category | GLM 4.6 (No MCP) | GLM 4.6 (With MCP) |
|----------|------------------|-------------------|
| Positive scores (wins) | 27 (27.0%) | 10 (21.3%) |
| Negative scores (losses) | 65 (65.0%) | 34 (72.3%) |
| Zero scores (ties) | 8 (8.0%) | 3 (6.4%) |

---

## 3. Head-to-Head Comparison (47 Common PRs)

When comparing the same 47 PRs that were judged in both runs:

| Outcome | Count | Percentage |
|---------|-------|------------|
| MCP wins | 26 | 55.3% |
| No-MCP wins | 18 | 38.3% |
| Ties | 3 | 6.4% |

### Mean Score Differences (MCP - No MCP) on Common PRs

| Metric | Difference |
|--------|------------|
| Correctness | +0.0330 |
| Completeness | -0.0074 |
| Code Reuse | +0.0330 |
| Best Practices | -0.0170 |
| Unsolicited Docs | +0.0702 |

**Observation:** On the 47 common PRs, MCP actually won more head-to-head comparisons (26 vs 18). The overall worse performance is primarily driven by the incomplete data (only 47 of 100 PRs completed).

---

## 4. MCP Tool Usage Analysis

### Usage Statistics

| Metric | Value |
|--------|-------|
| Total PRs with logs | 48 |
| PRs that used MCP tools | 8 (16.7%) |
| PRs that did NOT use MCP tools | 40 (83.3%) |
| Total MCP tool calls | 12 |
| Average MCP calls per PR (all) | 0.25 |
| Average MCP calls per PR (when used) | 1.50 |

### PRs That Used MCP Tools

| PR ID | MCP Calls | MCP Score | No-MCP Score | Difference |
|-------|-----------|-----------|--------------|------------|
| elastic_elasticsearch_pr134955 | 1 | -0.32 | -0.56 | +0.24 |
| elastic_elasticsearch_pr3632 | 1 | -0.28 | -0.30 | +0.02 |
| elastic_elasticsearch_pr3935 | 1 | -0.12 | +0.02 | -0.14 |
| elastic_elasticsearch_pr3947 | 1 | +0.14 | -0.06 | +0.20 |
| elastic_elasticsearch_pr3966 | 3 | -0.47 | -0.42 | -0.05 |
| elastic_elasticsearch_pr3974 | 1 | -0.60 | -0.40 | -0.20 |
| elastic_elasticsearch_pr4229 | 3 | -0.29 | -0.72 | +0.43 |
| elastic_elasticsearch_pr4236 | 1 | -0.28 | -0.24 | -0.04 |

### Performance When MCP Was Used vs Not Used

| Scenario | Mean Aggregate (MCP Run) | Mean Aggregate (No-MCP Run) | Win Rate |
|----------|--------------------------|----------------------------|----------|
| MCP tools used (8 PRs) | -0.2775 | -0.3350 | 4/8 (50%) |
| MCP tools NOT used (39 PRs) | -0.1854 | -0.2005 | 22/39 (56.4%) |

**Observation:** When MCP tools were actually used, the MCP run performed slightly better on average (-0.2775 vs -0.3350). However, MCP was only used in 16.7% of PRs.

---

## 5. Execution Time Analysis

| Metric | GLM 4.6 (No MCP) | GLM 4.6 (With MCP) | Ratio |
|--------|------------------|-------------------|-------|
| Mean execution time | 2.44 min | 8.04 min | 3.30x slower |
| Min execution time | 0.08 min | 0.70 min | 8.75x slower |
| Max execution time | 8.07 min | 24.35 min | 3.02x slower |
| Tasks per hour | 24.6 | 7.5 | 3.28x fewer |
| PRs hitting 10+ min | 0 (0.0%) | 13 (27.7%) | - |

**Observation:** The MCP run was significantly slower, with 27.7% of PRs exceeding 10 minutes compared to 0% in the non-MCP run.

---

## 6. Tool Usage Patterns (Common PRs)

| Tool | MCP Run | No-MCP Run | Difference |
|------|---------|------------|------------|
| Grep | 545 | 455 | +90 |
| Read | 535 | 449 | +86 |
| Edit | 386 | 270 | +116 |
| TodoWrite | 238 | 241 | -3 |
| Execute | 223 | 198 | +25 |
| LS | 137 | 107 | +30 |
| Create | 64 | 53 | +11 |
| Glob | 30 | 41 | -11 |
| auggie-mcp___codebase-retrieval | 12 | 0 | +12 |

**Observation:** The MCP run used more tool calls overall, particularly Grep (+90), Read (+86), and Edit (+116), suggesting more exploration but not necessarily more effective problem-solving.

---

## 7. Key Findings

### Finding 1: Low MCP Tool Adoption
The MCP context retrieval tool (`auggie-mcp___codebase-retrieval`) was only used in 8 out of 48 PRs (16.7%), with an average of just 0.25 calls per PR. The model largely did not leverage the additional context retrieval capability.

### Finding 2: Significant Completion Issues
The MCP run had a 57.1% completion rate compared to 100% for the non-MCP run. 36 out of 84 PR directories were empty, indicating execution failures or timeouts.

### Finding 3: Substantial Time Overhead
The MCP run was 3.30x slower on average (8.04 min vs 2.44 min), with 27.7% of PRs exceeding 10 minutes. This time overhead did not translate to better performance.

### Finding 4: Head-to-Head Performance is Mixed
On the 47 common PRs that completed in both runs, MCP actually won 26 vs 18 head-to-head comparisons. The overall worse metrics are primarily driven by the incomplete sample size.

### Finding 5: MCP Usage Correlated with Marginal Improvement
When MCP tools were actually used (8 PRs), the mean aggregate score was slightly better (-0.2775 vs -0.3350 for the same PRs in the non-MCP run). However, this sample is too small to draw strong conclusions.

### Finding 6: Increased Tool Usage Without Proportional Benefit
The MCP run used significantly more Grep, Read, and Edit operations, suggesting the model spent more time exploring the codebase but this additional exploration did not translate to better outcomes.

---

## 8. Possible Explanations for Underperformance

1. **Incomplete Execution**: The MCP run only completed 47% of tasks, severely limiting the sample size and potentially biasing results toward easier or faster-completing tasks.

2. **Low Tool Adoption**: The model rarely chose to use the MCP context retrieval tool (16.7% of PRs), suggesting either the tool was not well-integrated into the model's decision-making or the model did not perceive it as useful.

3. **Time Overhead**: The 3.30x slowdown may have caused timeouts or resource constraints that prevented task completion.

4. **Exploration vs Exploitation**: The increased tool usage (Grep, Read, Edit) without corresponding performance gains suggests the model may have spent time exploring rather than efficiently solving problems.

5. **Sample Size Disparity**: Comparing 47 judged PRs (MCP) to 100 judged PRs (No-MCP) introduces statistical uncertainty in the aggregate metrics.

---

## Appendix: Data Sources

- **No-MCP Edits**: `output-glm-comparison/web/edits/factory/glm-4.6/24634b85/`
- **MCP Edits**: `output-glm-comparison/web/edits/factory/mcp:glm-4.6/6bf04592/`
- **No-MCP Judges**: `output-glm-comparison/web/judges/llm/claude-sonnet-4-5/3e164e1c/24634b85/`
- **MCP Judges**: `output-glm-comparison/web/judges/llm/claude-sonnet-4-5/609ef74e/6bf04592/`
- **No-MCP Summary**: `output-glm-comparison/web/summaries/3e164e1c_factory_glm-4.6/summary.json`
- **MCP Summary**: `output-glm-comparison/web/summaries/609ef74e_factory_mcp:glm-4.6/summary.json`

