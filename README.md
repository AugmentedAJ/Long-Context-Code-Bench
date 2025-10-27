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

### Run on Full Dataset (v0)

Run on all 50 PRs from the built-in v0 dataset:

```bash
export GITHUB_GIT_TOKEN=your_github_token
export AUGMENT_API_TOKEN=your_augment_token  # if using Auggie

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

The benchmark consists of three stages:

### 1. Sample Stage

Extracts PR metadata and creates sample.json files (uses built-in dataset by default):

```bash
long-context-bench sample \
  --dataset-version v0 \
  --output-dir output/samples
```

**Output:** `output/samples/v0/<pr_id>/sample.json`

### 2. Edit Stage

Runs the agent on samples and captures diffs:

```bash
long-context-bench edit \
  --runner auggie \
  --model claude-sonnet-4 \
  output/samples/v0/elastic_elasticsearch_pr115001/sample.json
```

**Output:** `output/edits/<runner>/<model>/<run_id>/<pr_id>/edit.json`

### 3. Judge Stage

Scores agent edits against ground truth:

```bash
long-context-bench judge \
  output/samples/v0/elastic_elasticsearch_pr115001/sample.json \
  output/edits/auggie/claude-sonnet-4/<run_id>/elastic_elasticsearch_pr115001/edit.json
```

**Output:** `output/judges/<judge_mode>/<judge_model>/<run_id>/<pr_id>/judge.json`

## Evaluation Metrics

Each sample is scored on five primary metrics (range: -1.0 to 1.0):

1. **Correctness**: Does the change implement the intended behavior?
2. **Completeness**: Does it achieve all requested changes?
3. **Code Reuse**: Preference for leveraging existing code over duplication
4. **Best Practices**: Style, structure, and idiomatic usage
5. **Unsolicited Documentation**: Penalizes documentation added when not requested

**Aggregate Score**: Unweighted average of the five metrics

## Supported Runners

### Auggie

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --agent-binary /path/to/auggie \
  data/elasticsearch_prs_50.json
```

### Generic CLI Agent

For other CLI agents, use the generic runner:

```bash
long-context-bench pipeline \
  --runner generic \
  --model your-model \
  --agent-binary /path/to/your/agent \
  data/elasticsearch_prs_50.json
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

