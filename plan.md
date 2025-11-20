# Final Head-to-Head Judging Plan

## 1. Context & Goals

Current judging: each agent’s diff is independently scored against the ground-truth diff by a single LLM (`compute_llm_scores` in `stages/judge.py`), then aggregated via `stats.py` and visualized on the web. This has been criticized for limited context, lack of direct head-to-head comparisons, and dependence on a single judge model.

**Goals:**
- Head-to-head evaluation per PR across all agents that produced edits.
- Use the agents’ own underlying models as judges where possible, plus optional neutral judges.
- Improve context (optionally include real codebase files, not just diffs).
- Maintain compatibility with existing pipeline, stats, and UI; add new artifacts rather than breaking existing ones.

## 2. Core Approach (High Level)

For each PR with edits from ≥2 agents:
- Build a set of **agent submissions** (one per `runner:model:edit_run_id`).
- Generate all unordered pairs of submissions.
- For each pair, run one or more **anonymized pairwise judgments**:
  - Submissions are “Submission A” and “Submission B” in the prompt.
  - Judge sees task instructions, ground-truth diff (optional), and both diffs; optionally also a curated set of codebase files.
  - Judge outputs a JSON verdict indicating which submission is preferred (or tie), plus per-metric preferences and rationale.
- Aggregate pairwise decisions into per-PR and global head-to-head metrics (wins/losses/ties, Elo ratings, etc.).

## 3. Data Models (in `long_context_bench/models.py`)

1. **PairwiseJudgeDecision** (per judge, per pair, per PR)
   - Identity:
     - `repo_url`, `pr_number`
     - `submission_a_id`, `submission_b_id` (e.g. `"runner:model:edit_run_id"`)
     - `judge_model` (LLM ID) and optional `judge_runner` (if a CLI agent judged)
     - `order_seed` (used to reconstruct A/B assignment)
   - Verdict:
     - `winner`: `"A" | "B" | "tie"`
     - Optional per-metric preferences: e.g. `correctness_preference`, `completeness_preference`, `code_quality_preference`, `integration_preference` (each `"A" | "B" | "tie"`)
     - Optional `raw_scores`: per-submission numeric scores per metric
     - `rationale`: brief explanation
   - Metadata: `timestamp`, optional `codebase_context_files` (list of file paths included).

2. **HeadToHeadPRResult** (per PR)
   - PR/sample metadata: `repo_url`, `pr_number`, `base_commit`, `head_commit`, `task_instructions`.
   - `agent_results`: reuse existing `AgentResult` model (one per submission) to surface per-agent scores and patches.
   - `pairwise_decisions`: list of `PairwiseJudgeDecision`.
   - Derived per-agent stats for this PR: `wins`, `losses`, `ties`.

3. **HeadToHeadGlobalSummary** (cross-PR, per test label)
   - Per agent (identified by `runner`, `model`, optionally `test_label`):
     - `wins`, `losses`, `ties`, `matches`, `win_rate`.
     - `elo_rating` (float) and optional `elo_uncertainty`.
   - Optional `head_to_head_matrix`: nested mapping `[agent_id][opponent_id] → {wins, losses, ties}`.

## 4. Judge Model Mapping & Codebase Context

1. **Judge model selection (CLI)**
   - Use a single `judge_model` string passed via the `head-to-head-pr` CLI command.
   - Use this judge model both to select which prior LLM judge outputs to reuse for per-agent scores (from `judge` or `cross_agent_analysis`) **and** as the LLM judge for pairwise decisions in the head-to-head stage.

2. **Codebase context retrieval** (`stages/head_to_head.py`)
   - Function `get_codebase_context_for_pr(sample, max_files, max_bytes, cache_dir)`:
     - Uses repo at base commit (similar to `materialize_workspace` / `get_ground_truth_diff`).
     - Identifies files changed in ground-truth diff.
     - Optionally expands to related files (same directory, key imports) until hitting `max_files`/`max_bytes`.
     - Returns `Dict[path, content]` and a list of included paths for metadata.
   - This context is optional and can be toggled via CLI flag (e.g. `--include-codebase-context`).

## 5. Head-to-Head Stage Implementation (`stages/head_to_head.py`)

1. **Loading submissions for a PR**
   - Reuse `find_edits_for_pr(pr_number, repo_url, output_dir, test_label)` from `cross_agent_analysis` to get `(Edit, edit_file)` per agent.
   - Build an `agent_id` for each submission: `"{runner}:{model}:{edit_run_id}"`.
   - Load `AgentResult` entries per submission from existing LLM judge artifacts (prefer `cross_agent_analysis` outputs for the same `pr_number` / `test_label` / `judge_model`), falling back to neutral scores if none are available. The head-to-head stage itself does **not** call `compute_llm_scores`.

2. **Pairwise judgment (LLM judge, current implementation)**
   - Generate all unordered pairs of agent_ids.
   - For each pair of submissions (e.g., Factory vs Auggie):
     - Randomize which submission is A vs B in a deterministic way (record `order_seed`).
     - Build a judging prompt that includes:
       - Task instructions.
       - Human ground-truth diff (truncated if necessary).
       - Optional codebase context (selected files at base commit).
       - Submission A/B diffs.
       - A strict JSON schema for the verdict and per-agent "match to human" scores.
     - Call the configured LLM judge (via LiteLLM) once per pair using `judge_model`.
     - Parse the JSON response into a `PairwiseJudgeDecision` with `judge_model` set and `judge_runner=None`.

3. **Future refinements: richer judging modes**
   - Optionally extend `RunnerAdapter` with a dedicated `evaluate_pair(...)` API that can:
     - Materialize **two** workspaces (patch A and patch B applied) when runners support that style of comparison.
     - Enforce stricter output contracts (e.g., dedicated JSON-only channels) to reduce parsing fragility.
   - These refinements are aspirational; the current branch uses the simpler “prompt-only judge” approach above.

4. **Per-PR aggregation & artifact writing**
   - From all `PairwiseJudgeDecision` entries for a PR:
     - For each unordered pair of agents, aggregate multiple decisions (different judges or A/B orderings) by majority vote into a final pairwise outcome.
     - Tally per-agent `wins`, `losses`, `ties` (within this PR).
   - Construct `HeadToHeadPRResult` and write to `output/head_to_head/pr{pr_number}_{h2h_run_id}.json`.

## 6. Ranking & Stats (`ranking.py` and `stats.py`)

1. **Ranking utilities (`ranking.py`)**
   - `compute_win_loss_matrix(comparisons: List[PairwiseJudgeDecision])` → head-to-head counts.
   - `compute_elo_ratings(comparisons, initial_rating=1500.0, k_factor=32.0)` → per-agent Elo.
   - `rank_agents(comparisons, method="elo" | "win_loss")` → ordered agent_ids.

2. **Global summary (`stats.py` integration)**
   - Add a function to read all `HeadToHeadPRResult` under `output/head_to_head` (optionally filtered by `test_label`).
   - Use `ranking.py` to compute `HeadToHeadGlobalSummary` and emit JSON/CSV for comparisons and leaderboards.

## 7. CLI & Web Integration

1. **CLI (`cli.py`)**
   - New command `head-to-head-pr`:
     - Options: `--pr-number`, `--test-label`, `--judge-config`, `--include-codebase-context/--no-...`, `--output-dir`, `--cache-dir`, `--force`.
     - Calls `run_head_to_head_for_pr(...)` in `stages/head_to_head.py`.
   - Optional batch command `judge-h2h` that takes `--edit-run-ids` and runs head-to-head for all PRs touched by those edit runs.
   - Extend existing `compare` command with `--format head-to-head` to use `HeadToHeadGlobalSummary`.

2. **Web & packaging**
   - Update packaging scripts to include `output/head_to_head` in `index.json` and artifacts copied to Cloudflare bundles.
   - Extend the web UI to:
     - Show per-PR head-to-head outcomes and rationales alongside existing views.
     - Display a head-to-head leaderboard (Elo + win-loss records) and an agent-vs-agent matrix.

## 8. Implementation Roadmap (Phased)

1. **Phase 1: Models & LLM-based head-to-head**
   - Implement new models and LLM-based pairwise judging (diff-based, optional minimal codebase context), plus a `head-to-head-pr` CLI. This phase is complete and the LLM-based head-to-head judge is the primary implementation in this branch.

2. **Phase 2: Ranking, stats, and web**
   - Implement `ranking.py`, extend `stats.py` and `cli.compare`, and update web + packaging to surface head-to-head metrics. This phase is complete.

3. **Phase 3: Agents as CLI judges & richer context (future/experimental)**
   - Optionally explore using CLI agents (e.g., Auggie, Factory) as judges for head-to-head pairwise decisions, reusing existing LLM judge outputs only for scalar per-agent scores.
   - Potentially add a dedicated `evaluate_pair` API and richer workspace-level comparison in future iterations.

