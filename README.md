# Long-Context-Bench

A benchmark for evaluating long-context code editing capabilities of CLI-based coding agents on real-world GitHub pull requests.

## Overview

Long-Context-Bench evaluates how well coding agents can understand, modify, and integrate changes across large, multi-file repositories when given natural-language task instructions derived from PR metadata.

**Key Features:**
- 📊 Evaluates agents on 50 real Elasticsearch PRs (dataset v0)
- 🔄 Reproducible: identical inputs yield identical scores
- 🔌 Agent-agnostic: pluggable adapters for different CLI agents
- 📈 Comprehensive metrics: correctness, completeness, code reuse, best practices, and more
- ⚡ Scalable: supports sharding and concurrency for parallel execution

## Installation

### Prerequisites

- Python ≥ 3.11
- Git
- GitHub token for API access (set as `GITHUB_GIT_TOKEN`)
- Agent-specific tokens (e.g., `AUGMENT_API_TOKEN` for Auggie)

### Install from source

```bash
git clone https://github.com/AugmentedAJ/Long-Context-Code-Bench.git
cd Long-Context-Code-Bench
pip install -e .
```

## Quick Start

### 1. Set Environment Variables

```bash
export GITHUB_GIT_TOKEN=your_github_token
export AUGMENT_API_TOKEN=your_augment_token  # if using Auggie
# OR
export ANTHROPIC_API_KEY=your_key  # if using Claude Code or LLM judge
export OPENAI_API_KEY=your_key     # if using OpenAI models or LLM judge
```

### 2. Run on Full Dataset (v0)

Run on all 50 PRs from the built-in v0 dataset:

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4
```

### Run on Specific PRs

Run on specific PR numbers:

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --pr-numbers "115001,114998,114995"
```

Or run on specific indices (0-based):

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --pr-indices "0,1,2"
```

### With Sharding (for parallel execution)

Split the workload across 4 shards:

```bash
# Shard 0
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --total-shards 4 \
  --shard-index 0

# Shard 1
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --total-shards 4 \
  --shard-index 1

# ... and so on for shards 2 and 3
```

## Features

### Built-in Dataset

The v0 dataset (50 Elasticsearch PRs) is included in the repository. No need to download or specify file paths!

### Repository Caching

Repositories are cached in `.repo_cache/` to avoid re-cloning on subsequent runs. This significantly speeds up execution:
- First run: Clones repositories
- Subsequent runs: Reuses cached repositories

### Selective Execution

Run specific PRs using:
- `--pr-numbers`: Filter by PR number (e.g., `--pr-numbers "115001,114998"`)
- `--pr-indices`: Filter by index in dataset (e.g., `--pr-indices "0,1,2"`)

## Pipeline Stages

The benchmark consists of three stages that can be run together (pipeline mode) or separately (staged mode).

### Pipeline Mode (All Stages Together)

Run all stages in one command:

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4
```

### Staged Mode (Run Stages Separately)

Run stages independently for more control:

#### 1. Sample Stage

Extracts PR metadata and creates sample.json files (uses built-in dataset by default):

```bash
long-context-bench sample \
  --dataset-version v0 \
  --output-dir output/samples
```

**Output:** `output/samples/v0/<pr_id>/sample.json`

#### 2. Edit Stage

Runs the agent on samples and captures diffs. Each run gets a unique ID:

```bash
long-context-bench edit \
  --runner auggie \
  --model claude-sonnet-4 \
  --dataset-version v0 \
  --output-dir output/edits \
  output/samples/v0
```

**Output:**
- `output/edits/<runner>/<model>/<edit_run_id>/edit_run_manifest.json` - Run metadata
- `output/edits/<runner>/<model>/<edit_run_id>/<pr_id>/edit.json` - Full edit data
- `output/edits/<runner>/<model>/<edit_run_id>/<pr_id>/edit_summary.json` - Clean JSON without inline patch
- `output/edits/<runner>/<model>/<edit_run_id>/<pr_id>/edit.patch` - Diff patch file
- `output/edits/<runner>/<model>/<edit_run_id>/<pr_id>/logs.jsonl` - Agent logs

**Returns:** Edit run ID (e.g., `a1b2c3d4`)

#### 3. Judge Stage

Scores agent edits against ground truth. Can evaluate one or more edit runs:

```bash
# Evaluate specific edit run(s)
long-context-bench judge \
  --edit-run-ids a1b2c3d4,b2c3d4e5 \
  --judge-mode deterministic \
  --output-dir output/judges
```

**Output:** `output/judges/<judge_mode>/<judge_model>/<judge_run_id>/<pr_id>/judge.json`
**Returns:** Judge run ID (e.g., `e5f6g7h8`)

#### 4. Summary

Generate aggregate statistics for specific runs:

```bash
long-context-bench summary \
  --edit-run-id a1b2c3d4 \
  --judge-run-id e5f6g7h8 \
  --output-dir output/summaries/my_run \
  output
```

### Staged Execution Use Cases

**Compare Multiple Models:**
```bash
# Run two models
long-context-bench edit --runner auggie --model claude-sonnet-4 output/samples/v0
# Returns: Edit run ID: aaaa1111

long-context-bench edit --runner auggie --model gpt-4 output/samples/v0
# Returns: Edit run ID: bbbb2222

# Evaluate both
long-context-bench judge --edit-run-ids aaaa1111,bbbb2222 --judge-mode deterministic
```

**Re-evaluate with Different Judge:**
```bash
# Initial evaluation
long-context-bench judge --edit-run-ids aaaa1111 --judge-mode deterministic

# Re-evaluate with LLM judge
long-context-bench judge --edit-run-ids aaaa1111 --judge-mode llm --judge-model gpt-4
```

## Evaluation Metrics

Each sample is scored on five primary metrics (range: -1.0 to 1.0):

1. **Correctness**: Does the change implement the intended behavior?
2. **Completeness**: Does it achieve all requested changes?
3. **Code Reuse**: Preference for leveraging existing code over duplication
4. **Best Practices**: Style, structure, and idiomatic usage
5. **Unsolicited Documentation**: Penalizes documentation added when not requested

**Aggregate Score**: Unweighted average of the five metrics

### Judge Modes

The benchmark supports two judge modes:

#### Deterministic Judge (default)

Uses exact-match and overlap heuristics to score diffs:
- Fast and reproducible
- No API costs
- Good baseline for comparison

```bash
long-context-bench judge \
  --edit-run-ids a1b2c3d4 \
  --judge-mode deterministic
```

#### LLM Judge

Uses an LLM (via LiteLLM) to evaluate diffs with detailed reasoning:
- More nuanced evaluation
- Provides rationale for scores
- Supports any model via LiteLLM (OpenAI, Anthropic, etc.)
- Deterministic settings (temperature=0.0, seed=42)

```bash
# Using Claude (via Anthropic)
export ANTHROPIC_API_KEY=your_key
long-context-bench judge \
  --edit-run-ids a1b2c3d4 \
  --judge-mode llm \
  --judge-model anthropic/claude-3-5-sonnet-20241022

# Using OpenAI
export OPENAI_API_KEY=your_key
long-context-bench judge \
  --edit-run-ids a1b2c3d4 \
  --judge-mode llm \
  --judge-model gpt-4o-mini

# Using any LiteLLM-supported model
long-context-bench judge \
  --edit-run-ids a1b2c3d4 \
  --judge-mode llm \
  --judge-model bedrock/anthropic.claude-v2
```

**Note:** LLM judge falls back to deterministic scoring if the API call fails or returns invalid JSON.

## Supported Runners

The benchmark supports multiple CLI coding agents through pluggable adapters:

### Auggie

Augment's CLI coding agent.

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --agent-binary /path/to/auggie  # Optional, defaults to 'auggie' in PATH
```

**Environment:** Requires `AUGMENT_API_TOKEN`

### Claude Code

Anthropic's command-line coding agent.

```bash
long-context-bench pipeline \
  --runner claude-code \
  --model claude-sonnet-4 \
  --agent-binary /path/to/claude  # Optional, defaults to 'claude' in PATH
```

**Environment:** Requires `ANTHROPIC_API_KEY`

### Codex CLI

OpenAI's command-line coding agent.

```bash
long-context-bench pipeline \
  --runner codex \
  --model gpt-5-codex \
  --agent-binary /path/to/codex  # Optional, defaults to 'codex' in PATH
```

**Install:** `npm install -g @openai/codex`
**Environment:** Requires `OPENAI_API_KEY`

### Aider

Open-source AI pair programming tool.

```bash
long-context-bench pipeline \
  --runner aider \
  --model claude-sonnet-4 \
  --agent-binary /path/to/aider  # Optional, defaults to 'aider' in PATH
```

**Install:** `pip install aider-chat`
**Environment:** Requires API keys for the model provider (e.g., `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)

### Generic CLI Agent

For other CLI agents not listed above, use the generic runner:

```bash
long-context-bench pipeline \
  --runner generic \
  --model your-model \
  --agent-binary /path/to/your/agent
```

The generic runner passes task instructions via stdin.

## Configuration Options

### Required Options

- `--runner`: Agent runner name (e.g., `auggie`, `generic`)
- `--model`: Model name to use

### Optional Flags

- `--agent-binary`: Path to agent binary (defaults to runner name in PATH)
- `--timeout`: Timeout in seconds per task (default: 1800)
- `--concurrency`: Max concurrent tasks (default: 1)
- `--total-shards`: Total number of shards (default: 1)
- `--shard-index`: Current shard index, 0-based (default: 0)
- `--disable-retrieval`: Disable retrieval features
- `--disable-shell`: Disable shell access
- `--enable-mcp-codebase-qa`: Enable MCP codebase QA

### Judge Options

- `--judge-mode`: Judge mode (`deterministic` or `llm`, default: `deterministic`)
- `--judge-model`: Judge model (for LLM mode)

## Viewing Results

### Generate Statistics

```bash
long-context-bench stats output/
```

This displays:
- Success rate
- Mean scores for all metrics
- Per-PR breakdown (top 10)
- Latency metrics

### Output Files

Results are saved in the following structure:

```
output/
├── samples/v0/<pr_id>/sample.json
├── edits/<runner>/<model>/<run_id>/<pr_id>/
│   ├── edit.json
│   └── logs.jsonl
├── judges/<judge_mode>/<judge_model>/<run_id>/<pr_id>/judge.json
└── summaries/<run_id>/
    ├── summary.json
    ├── summary.csv
    └── run_manifest.json
```

## Reproducibility

Per R-3.14-3.15, all runs record complete provenance:

- Dataset version
- Harness version
- Runner and model
- OS and Python version
- All flags and configuration
- Timestamps

Re-running with identical inputs and flags produces identical results (excluding timestamps).

## Dataset

**Version:** v0  
**Size:** 50 PRs from elastic/elasticsearch  
**File:** `data/elasticsearch_prs_50.json`

The v0 dataset is frozen. Future versions may rotate or expand PRs with semantic versioning.

## License

- **Harness code:** Apache-2.0
- **Documentation:** CC BY 4.0
- **Dataset metadata:** Compliant with GitHub ToS (URLs and metadata only, no source code redistribution)

## Contributing

Contributions are welcome! Please see the PRD (`prd.md`) for detailed requirements and design specifications.

## Citation

If you use Long-Context-Bench in your research, please cite:

```bibtex
@software{long_context_bench,
  title = {Long-Context-Bench: Benchmark for Long-Context Code Editing},
  author = {Augment Code},
  year = {2025},
  version = {0.1.0},
  url = {https://github.com/AugmentedAJ/Long-Context-Code-Bench}
}
```

## Support

For issues and questions, please open an issue on GitHub.

