## Long-Context-Bench: Product Requirements Document (PRD)

Version: v0 (dataset v0; harness v0.1.0)
Audience: Researchers and engineers implementing and running the benchmark
Last Updated: 2025-10-27

### Executive Summary

Long-Context-Bench is a standardized benchmark for evaluating the long-context code editing capabilities of CLI-based coding agents on real-world GitHub pull requests. The benchmark measures how well AI agents can understand, modify, and integrate changes across large, multi-file repositories when given natural-language task instructions derived from PR metadata. This PRD defines the requirements for a reproducible, comparable, and practical evaluation framework that enables fair comparison of different coding agents while addressing the unique challenges of long-context code editing tasks.

### Table of Contents

1. [Overview](#1-overview)
2. [Dataset Specification](#2-dataset-specification)
3. [Benchmark Pipeline](#3-benchmark-pipeline-stages-and-required-behaviors)
4. [Harness Design](#4-harness-design-agent-agnostic)
5. [Evaluation Metrics and Scoring](#5-evaluation-metrics-and-scoring)
6. [Reproducibility, Provenance, and Artifact Layout](#6-reproducibility-provenance-and-artifact-layout)
7. [User Experience and Documentation](#7-user-experience-and-documentation)
8. [Governance, Licensing, and Versioning](#8-governance-licensing-and-versioning)
9. [Risks and Mitigations](#9-risks-and-mitigations)
10. [Acceptance Criteria](#10-acceptance-criteria-testable)
11. [Resource Requirements and Team](#11-resource-requirements-and-team)
12. [Glossary](#glossary)
13. [Example End-to-End Flow](#example-end-to-end-flow-prose)

### 1) Overview

Problem Statement
- R-1.1 The benchmark shall evaluate long-context code editing capabilities of CLI-based coding agents on real-world GitHub pull requests (PRs).
- R-1.2 The benchmark shall measure an agent’s ability to understand, modify, and integrate changes across large, multi-file repositories when given natural-language task instructions derived from PR metadata.

Goals
- R-1.3 Reproducibility: Identical inputs and flags shall yield identical scores and artifacts (excluding timestamps and explicitly volatile fields).
- R-1.4 Comparability: Results shall be agent-agnostic so different CLI agents can be compared fairly.
- R-1.5 Practicality: Pipeline shall be operable locally and via CI with sharding and concurrency.

Non-goals
- R-1.6 Training models or fine-tuning is out of scope.
- R-1.7 Modifying upstream PR history or redistributing copyrighted source code is out of scope.
- R-1.8 Evaluating non-code tasks (e.g., documentation-only PRs) beyond the defined metrics is out of scope.

### 1.1) Target Users and Personas

Primary Users:
- **AI Researchers**: Evaluate and compare long-context capabilities of different coding agents
- **Tool Developers**: Benchmark their CLI-based coding agents against competitors
- **Enterprise Teams**: Assess which coding agents perform best on their specific codebases
- **Academic Institutions**: Conduct reproducible research on AI code generation capabilities

User Needs:
- Reproducible evaluation results that can be independently verified
- Fair comparison framework that eliminates confounding variables
- Scalable benchmarking that works both locally and in CI environments
- Clear metrics that correlate with real-world coding performance

### 2) Dataset Specification

Corpus (v0)
- R-2.1 Dataset v0 shall be exactly the 50 recent Elasticsearch PR URLs listed at path: data/elasticsearch_prs_50.json.
- R-2.2 The harness shall treat this file as the canonical v0 corpus; no additions/removals in v0.

Inclusion Policy
- R-2.3 Each PR must be public, merged, and have an accessible base commit.
- R-2.4 For each PR, the sampler shall pin and record: repository URL, PR number, base commit hash, and head commit hash.
- R-2.5 If a PR fails policy (e.g., base inaccessible), sampler shall record failure with reason and exclude it from scoring; include it in aggregated “skipped” stats.

Update Policy and Versioning
- R-2.6 v0 is frozen. Future versions (v1+) may rotate or expand PRs; changes must be documented in a changelog with semantic versioning (e.g., v0.1.0 for non-breaking metadata additions, v1.0.0 for corpus changes).
- R-2.7 All published results must annotate the dataset version used.

“Long-context” Characterization (for reporting, not filtering)
- R-2.8 For each PR, sampler shall compute and store: files_changed, lines_added, lines_deleted, total_diff_hunks, and an approximate context_size_bytes.
- R-2.9 context_size_bytes shall be defined as the sum of byte sizes of all files touched at the base commit (prior to changes), capped at 20 MB per PR for reporting (with a flag if truncated).

Compliance
- R-2.10 The benchmark shall redistribute only URLs and metadata (e.g., commit hashes, counts, stats). It shall not redistribute source code blobs or full diffs in the dataset package.
- R-2.11 Local runs may cache clones/diffs for execution; guidance shall instruct not to republish code artifacts.

### 2.1) Dataset Dependencies and Assumptions

External Dependencies:
- GitHub API availability and rate limit compliance
- Git repository accessibility for public repositories
- Stable internet connectivity for repository cloning
- Sufficient local storage for repository clones (estimated 20-100GB for full dataset)

Assumptions:
- PRs remain publicly accessible throughout the evaluation period
- Repository structures remain stable enough for meaningful comparison
- Agent runners support the required CLI interface specifications
- Evaluation environments meet minimum hardware requirements (8GB+ RAM, 10GB+ disk)

### 3) Benchmark Pipeline (Stages and Required Behaviors)

Overview
- R-3.1 The pipeline comprises stages: sample → edit → judge. A convenience pipeline executes all three.
- R-3.2 Determinism: All inputs, versions, seeds, and flags shall be recorded to enable exact re-runs.

3.1 Sample Stage
- Inputs: PR URL(s) (single URL, JSON file of URLs, or a directory of pre-generated samples).
- R-3.3 The sampler shall clone the repo, fetch PR metadata, and pin base/head commit hashes.
- R-3.4 The sampler shall extract task_instructions from PR metadata deterministically: use PR title followed by PR body (raw text), truncated to 10,000 characters with a trailing “[truncated]” marker if needed.
- R-3.5 The sampler shall compute statistics per R-2.8–2.9 and store them in sample artifacts.
- R-3.6 Output: One sample.json per PR with schema specified in Section 6.

3.2 Edit Stage
- Inputs: sample.json; agent runner configuration.
- R-3.7 The harness shall materialize a clean workspace at the base commit (detached HEAD), with read/write permissions inside a sandboxed directory.
- R-3.8 The harness shall pass task_instructions to the agent runner via stdin or runner-specific flags, as defined by the runner adapter (Section 4), without including original diffs.
- R-3.9 Upon completion or timeout, the harness shall produce a unified diff (patch) against the base commit by running a clean `git diff` within the workspace; this diff constitutes the agent output.
- R-3.10 Output: One edit.json per sample with schema specified in Section 6, plus structured logs.

3.3 Judge Stage
- Inputs: sample.json and edit.json.
- R-3.11 The judge shall compare the agent-produced diff to the ground-truth PR diff (computed locally from base→head) using a rubric to produce five primary metric scores in [-1.0, 1.0].
- R-3.12 The judge shall support two modes: (a) deterministic baseline judge (e.g., exact-match/overlap heuristics) and (b) LLM-based judge (temperature 0.0, top_p 0) with a fixed prompt and seed.
- R-3.13 Output: One judge.json per sample with schema specified in Section 6.

3.4 Determinism and Run Logs
- R-3.14 The harness shall record: dataset version, harness version, OS, Python/Node versions, runner and version, model, judge mode and model, seeds, flags, timestamps, and environment summaries to a run_manifest.json.
- R-3.15 All I/O that affects outcomes (prompts, flags, versions) shall be persisted in artifacts.

### 4) Harness Design (Agent-Agnostic)

Entry Point and Subcommands
- R-4.1 CLI name: `long-context-bench` with subcommands: `sample`, `edit`, `judge`, `pipeline`, `stats`.
- R-4.2 Inputs accepted by `sample`/`pipeline`: single PR URL, a JSON file containing an array of PR URLs, or a directory of pre-generated samples.
- R-4.3 Outputs: per-task JSON artifacts (samples, edits, judgments) and aggregated CSV/JSON stats.

Runner Abstraction (Adapter Interface)
- R-4.4 The harness shall support pluggable adapters for CLI agents (e.g., auggie, claude-code, copilot) through a common contract:
  - Runner selection via `--runner` and `--agent-binary` path; `--model` specifies the model.
  - Required options: `--runner`, `--model`, `--concurrency`, `--timeout`, `--total-shards`, `--shard-index`.
  - Optional flags: `--disable-retrieval`, `--disable-shell`, `--enable-mcp-codebase-qa`.
  - Environment vars: `GITHUB_GIT_TOKEN` (sampling); `AUGMENT_API_TOKEN` or agent-specific tokens (editing).
  - Exit code 0 = success; non-zero with stderr captured = failure; harness applies retry policy (R-4.8).
- R-4.5 Adapter input (logical spec):
  - workspace_path (checked out at base commit), task_instructions (string), time_budget_s, env, and any adapter-specific flags.
- R-4.6 Adapter output (logical spec):
  - status {success, timeout, error}, elapsed_ms, and side-effect: workspace edits; harness extracts unified diff via git.
- R-4.7 Logging: Adapters shall stream structured logs (JSONL) including progress events, errors, and key decisions; logs are stored under the edit artifact directory.

Parallelism, Timeouts, Retries
- R-4.8 Sharding: Use `--total-shards` and `--shard-index` to partition the PR set by stable hashing of `(repo_url, pr_number)`. Each shard processes a disjoint subset.
- R-4.9 Concurrency: `--concurrency` defines max in-flight tasks per process; implement bounded worker pool per shard.
- R-4.10 Timeouts: Per-task timeout via `--timeout` (seconds). Default 1,800s; may be overridden.
- R-4.11 Retries: On retryable failures (network, 5xx, transient git errors), retry up to 2 times with exponential backoff (base 2) and jitter (±10%). Non-retryable failures (auth, 4xx, schema) do not retry.

### 5) Evaluation Metrics and Scoring

Primary Metrics (per sample; range -1.0 to 1.0)
- R-5.1 Correctness: Does the change implement the intended behavior?
- R-5.2 Completeness: Does it achieve all requested changes and nothing extra?
- R-5.3 Code Reuse: Preference for leveraging existing code over duplication.
- R-5.4 Best Practices: Style, structure, and idiomatic usage for the repo/language.
- R-5.5 Unsolicited Documentation: Penalize documentation added when not requested.

Aggregation
- R-5.6 Default aggregate score is the unweighted average of the five primary metrics, averaged across all scored samples.
- R-5.7 Allow optional custom weighting via a config file recorded in run_manifest.json.

Secondary Metrics
- R-5.8 Success rate (non-error judgments), wall-clock latency per sample, tasks/hour, and optional token usage (if available from the runner) shall be reported.

Reporting
- R-5.9 Produce per-PR and aggregate summaries. Export formats: JSON and CSV for aggregates; JSON per-task.

### 5.1) Success Metrics and Validation Strategy

Primary Success Indicators:
- **Adoption Rate**: Number of research groups and organizations using the benchmark within 6 months
- **Reproducibility Score**: Percentage of runs that achieve identical results when repeated with same inputs
- **Coverage**: Percentage of major coding agent platforms that provide official support
- **Correlation**: Alignment between benchmark scores and real-world performance on similar tasks

Validation Approach:
- Pilot testing with 3-5 diverse coding agents to verify requirement feasibility
- Independent verification by external research groups
- A/B testing to ensure sharding and concurrency don't affect results
- Longitudinal study to verify benchmark stability over time

### 6) Reproducibility, Provenance, and Artifact Layout

Recorded Provenance
- R-6.1 Record in run_manifest.json: repo URL, PR number, base and head commit hashes, agent runner and version, model name/version, judge mode and model, harness version, OS, Python/Node versions, seed, flags, timestamps, and dataset version.

Artifact Directory Structure (all paths relative to an output root)
- R-6.2 samples/<dataset_version>/<pr_id>/sample.json (and sample_meta.json)
- R-6.3 edits/<runner>/<model>/<run_id>/<pr_id>/{edit.json, logs.jsonl}
- R-6.4 judges/<judge_mode>/<judge_model>/<run_id>/<pr_id>/judge.json
- R-6.5 summaries/<run_id>/{summary.json, summary.csv, run_manifest.json}
- R-6.6 pr_id shall be `{owner}_{repo}_pr{number}`.

JSON Schemas (concise; all fields required unless noted)
- R-6.7 sample.json
  - dataset_version (string); repo_url (string); pr_number (int);
  - base_commit (string); head_commit (string);
  - task_instructions (string);
  - stats: {files_changed (int), lines_added (int), lines_deleted (int), total_diff_hunks (int), context_size_bytes (int), truncated (bool)}
- R-6.8 edit.json
  - repo_url (string); pr_number (int); base_commit (string);
  - runner (string); model (string); timeout_s (int); status (string: success|timeout|error);
  - elapsed_ms (int); patch_unified (string; may be empty if failure);
  - logs_path (string; relative); errors (array[string]; optional)
- R-6.9 judge.json
  - repo_url (string); pr_number (int); base_commit (string); head_commit (string);
  - judge_mode (string: deterministic|llm); judge_model (string; optional for deterministic);
  - scores: {correctness (float), completeness (float), code_reuse (float), best_practices (float), unsolicited_docs (float)};
  - aggregate (float); rationale (string; optional)

Caching and Re-run Semantics
- R-6.10 Sampling is cacheable by (repo_url, pr_number, base_commit, harness_version). Edits and judgments are cacheable by their complete input JSON plus runner/model config.
- R-6.11 No hidden state: Re-running with identical inputs/flags regenerates identical artifacts byte-for-byte, except for timestamps and volatile paths explicitly marked.

### 7) User Experience and Documentation

Getting Started (Local)
- R-7.1 Prerequisites: git, Python ≥3.11, Node.js (for some agents), `GITHUB_GIT_TOKEN` (sampling), and agent-specific tokens (editing) such as `AUGMENT_API_TOKEN`.
- R-7.2 Minimal commands:
  - Single PR: run `long-context-bench pipeline --runner <runner> --model <model> <PR_URL>`.
  - Batch (v0 dataset): run `long-context-bench pipeline --runner <runner> --model <model> data/elasticsearch_prs_50.json`.

Remote/CI
- R-7.3 Provide a GitHub Actions workflow with parameters: model, runner, total_shards, concurrency, input path/URL, optional flags per Section 4.

Interpreting Results
- R-7.4 Summaries shall report per-metric means, standard deviations, success rate, and latency; include a ranked table by aggregate score.

Publishing Guidance
- R-7.5 Public artifacts may include summaries (JSON/CSV), run_manifest.json (without tokens), and sample/edit/judge metadata. Do not publish source code blobs or full diffs; publish only URLs and metrics.

### 8) Governance, Licensing, and Versioning

- R-8.1 Harness code license: Apache-2.0.
- R-8.2 Documentation (including this PRD) license: CC BY 4.0.
- R-8.3 Dataset metadata (URLs, commit hashes, stats) are redistributed under terms compliant with GitHub ToS.
- R-8.4 Maintain a CHANGELOG.md for both the harness and dataset; use semantic versioning.

### 8.1) Development Timeline and Milestones

Phase 1 - Foundation (Months 1-2):
- Implement core sampling pipeline and dataset v0
- Develop baseline deterministic judge
- Create initial runner adapters for 2-3 major coding agents
- Establish artifact schemas and caching mechanisms

Phase 2 - Expansion (Months 3-4):
- Add LLM-based judge with configurable models
- Implement full sharding and concurrency support
- Develop comprehensive CLI interface
- Create documentation and examples

Phase 3 - Validation (Month 5):
- Conduct end-to-end testing with all supported runners
- Perform reproducibility validation across different environments
- Gather feedback from pilot users and iterate
- Prepare for public release

Phase 4 - Launch (Month 6):
- Public release of harness v1.0.0 and dataset v0
- Publish initial benchmark results for supported agents
- Establish community feedback channels
- Plan for dataset v1 based on community input

### 9) Risks and Mitigations

- R-9.1 Large repositories / timeouts → Set generous defaults, per-task timeouts, and resume capability; allow increasing `--timeout` and concurrency.
- R-9.2 GitHub rate limits → Backoff with `Retry-After`, authenticated requests, and caching.
- R-9.3 Flaky network → Retries with exponential backoff and jitter; verify integrity via commit hashes.
- R-9.4 Private PRs/permissions → Validate early; record as skipped with reason; do not fail the entire run.
- R-9.5 Agent CLI incompatibilities → Adapters provide normalization; require conformance tests per R-4.4–4.7.
- R-9.6 LLM non-determinism → Deterministic judge mode; fix temperature/top_p and seed for LLM mode; cache judgments by inputs.

### 10) Acceptance Criteria (Testable)

- AC-1 End-to-end Completion: Running the benchmark on the v0 dataset (`data/elasticsearch_prs_50.json`) with any supported runner completes sample→edit→judge and produces per-task artifacts (sample.json, edit.json, judge.json) plus an aggregate summary file (summary.json and summary.csv).
- AC-2 Deterministic Re-runs: Re-running with identical inputs and flags (including judge mode) yields identical scores and artifacts byte-for-byte, excluding timestamps and fields documented as volatile.
- AC-3 Runner Swappability: Switching runners (e.g., from `auggie` to `claude-code`) requires only changing `--runner` and agent-specific flags; no code changes.
- AC-4 Sharding Equivalence: Sharded runs (e.g., `--total-shards=4`, covering all shards) produce the same final aggregate summary as a single-shard run.
- AC-5 Documentation Completeness: Documentation includes minimal working examples for each supported runner and clearly explains required environment variables.

### Glossary
- PR: Pull Request on GitHub.
- Base commit: The commit on the target branch from which the PR diverges.
- Head commit: The PR’s tip commit containing the proposed changes.
- Patch (unified diff): Text representation of code changes between two commits.
- Sample: The benchmark’s representation of a PR task, including instructions and metadata.
- Edit: The agent’s produced diff against the base commit.
- Judge: The scoring step that compares an Edit to the PR’s ground truth.
- Runner: Adapter that interfaces with a specific CLI-based coding agent.
- Shard: A partition of the corpus processed independently to enable parallelism.

### Example End-to-End Flow (Prose)
1) The operator selects dataset v0 (data/elasticsearch_prs_50.json) and invokes the pipeline with a runner and model. 2) The sampler clones each PR’s repository at the base commit, records metadata, and writes sample.json files with deterministic task_instructions and stats. 3) The edit stage creates isolated workspaces per sample, passes task_instructions to the selected agent via the runner adapter, enforces timeouts, and captures the unified diff from git as edit.json. 4) The judge stage computes the ground-truth PR diff from base→head locally, compares it to the agent diff, and assigns five scores plus an aggregate, writing judge.json. 5) The harness aggregates per-PR results into summary.json and summary.csv and writes a run_manifest.json with full provenance, enabling exact re-runs.

### 11) Resource Requirements and Team

Technical Resources:
- **Compute**: Minimum 8-core CPU, 32GB RAM for concurrent evaluation runs
- **Storage**: 100GB+ available disk space for repository clones and artifacts
- **Network**: Stable broadband connection for GitHub API and repository access
- **Services**: GitHub account with API token, cloud storage for artifact distribution

Human Resources:
- **Project Lead**: Overall coordination and stakeholder management
- **Technical Lead**: Architecture decisions and technical implementation
- **ML Engineer**: Judge implementation and metric design
- **DevOps Engineer**: CI/CD, sharding, and infrastructure
- **Technical Writer**: Documentation and user guides
- **QA Engineer**: Testing and validation of reproducibility requirements

