# Long-Context-Code-Bench: Agent Comparison Analysis Report

## Executive Summary

This report analyzes the performance of four AI coding agents on 100 Elasticsearch pull requests. **Codex (gpt-5.1-codex)** significantly outperformed all other agents, while **Auggie (sonnet4.5)** underperformed relative to expectations.

| Agent | Model | Mean Aggregate | Win Rate |
|-------|-------|----------------|----------|
| **Codex** | gpt-5.1-codex | **0.003** | **40%** |
| Auggie | sonnet4.5 | -0.100 | 28% |
| Claude-Code | claude-sonnet-4-5 | -0.105 | 31% |
| Factory | glm-4.6 | -0.161 | 27% |

---

## Detailed Score Breakdown

### Per-Metric Performance (Scale: -1.0 to 1.0)

| Metric | Codex | Auggie | Claude-Code | Factory |
|--------|-------|--------|-------------|---------|
| Correctness | -0.229 | -0.335 | -0.340 | -0.391 |
| Completeness | -0.297 | -0.381 | -0.423 | -0.362 |
| Code Reuse | -0.050 | -0.141 | -0.133 | -0.237 |
| Best Practices | -0.104 | -0.194 | -0.183 | -0.283 |
| Unsolicited Docs | **0.695** | 0.551 | 0.554 | 0.471 |

**Key Observation**: Codex leads in every metric, with the largest advantage in **unsolicited_docs** (+0.144 vs Auggie).

---

## Head-to-Head: Auggie vs Codex

| Outcome | Count |
|---------|-------|
| Codex wins | **56** |
| Auggie wins | 30 |
| Ties | 14 |

### Largest Performance Gaps

**Codex's Biggest Advantages:**
| PR | Auggie | Codex | Gap |
|----|--------|-------|-----|
| pr134881 | -0.20 | 1.00 | +1.20 |
| pr134495 | -0.55 | 0.56 | +1.11 |
| pr134477 | -0.18 | 0.84 | +1.02 |

**Auggie's Biggest Advantages:**
| PR | Auggie | Codex | Gap |
|----|--------|-------|-----|
| pr2715 | 0.74 | -0.28 | -1.02 |
| pr134745 | 1.00 | 0.00 | -1.00 |
| pr134395 | 0.60 | 0.00 | -0.60 |

---

## Why Auggie Underperformed

### Pattern Analysis of Auggie's Failures

Analysis of 59 PRs where Auggie scored negative (aggregate < 0):

| Issue Pattern | Frequency | % of Failures |
|---------------|-----------|---------------|
| **Missed changes** | 42 | 71.2% |
| **Unsolicited tests/docs** | 25 | 42.4% |
| Wrong files/location | 8 | 13.6% |
| Missing changelog | 6 | 10.2% |
| Scope issues | 3 | 5.1% |

### Root Cause Analysis

#### 1. **Incomplete Task Understanding** (Primary Issue)
Auggie frequently missed subtle but critical changes required by the task:
- **PR 134881**: Changed JSON files but missed the Java source file (`DocsV3Support.java`) that generates them
- **PR 134495**: Worked on entirely wrong test files (qa/ directory instead of x-pack/plugin/esql/)

#### 2. **Unsolicited Content Generation**
Auggie added unnecessary tests and documentation more frequently than Codex:
- **Unsolicited docs score**: Auggie 0.551 vs Codex 0.695
- **Perfect scores (1.0)**: Auggie 60% vs Codex 72%
- **Negative scores (<0)**: Auggie 11% vs Codex 4%

#### 3. **Scope Misinterpretation**
When tasks mentioned "tests," Auggie sometimes created new test files instead of modifying existing ones, or added YAML REST tests when unit tests were expected.

---

## Why Codex Performed Well

### Key Strengths

#### 1. **Better Task Scope Adherence**
Codex more accurately identified which files needed modification and avoided adding unnecessary content.

#### 2. **More Conservative Approach**
Codex was less likely to add unsolicited documentation or tests, resulting in higher unsolicited_docs scores.

#### 3. **Broader Context Understanding**
In cases like PR 134881, Codex correctly identified that the task required changes across 275+ files, not just the 2 shown in the minimal ground truth.

### Example: PR 134881 (Codex Perfect Score)
- **Task**: Change `snapshot_only` to `snapshotOnly` for consistency
- **Codex**: Changed all 277 affected files (JSON + Java source)
- **Auggie**: Changed JSON files but missed the Java generator file
- **Result**: Codex 1.00, Auggie -0.20

---

## Case Studies

### Case 1: PR 134495 - Wrong File Location (Gap: 1.11)

**Task**: Consolidate repetitive assertion code in CCS metadata tests

| Agent | Score | Issue |
|-------|-------|-------|
| Auggie | -0.55 | Modified files in `qa/ccs-unavailable-clusters/` instead of `x-pack/plugin/esql/` |
| Codex | +0.56 | Correctly identified ESQL test files, though missed some enrich-based tests |

**Auggie's Failure**: Misidentified "CCS metadata tests" as referring to the qa/ directory tests rather than the ESQL cross-cluster test suite.

### Case 2: PR 2715 - Auggie's Architectural Win (Gap: -1.02)

**Task**: Fix id field validation to reject arrays/objects

| Agent | Score | Approach |
|-------|-------|----------|
| Auggie | +0.74 | Validated in `IdFieldMapper.java` (field mapping layer) |
| Codex | -0.28 | Validated in `BulkRequest.java` (wrong layer - API request parsing) |

**Auggie's Success**: Chose a more architecturally appropriate location for validation, with comprehensive tests.

---

## Recommendations for Improving Auggie

### 1. **Improve File Location Accuracy**
- Train on more examples of codebase navigation
- Better parsing of task descriptions to identify target directories

### 2. **Reduce Unsolicited Content**
- Add guardrails against creating new test files unless explicitly requested
- Penalize adding documentation/changelog files not mentioned in task

### 3. **Enhance Completeness Checking**
- Implement verification step to ensure all related files are modified
- Cross-reference changes with imports/dependencies

### 4. **Better Scope Interpretation**
- Distinguish between "add tests" (new) vs "update tests" (existing)
- Recognize project-specific conventions (e.g., Elasticsearch changelog requirements)

---

## Methodology Notes

- **Benchmark**: 100 Elasticsearch PRs from the elastic/elasticsearch repository
- **Judge Model**: claude-sonnet-4-5 (LLM-based evaluation)
- **Metrics**: 5 dimensions scored -1.0 to 1.0, averaged for aggregate
- **Win Rate**: Fraction of PRs where agent aggregate > 0 (beat human reference)

