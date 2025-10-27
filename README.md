# Long-Context-Bench

A benchmark for evaluating long-context code editing capabilities of CLI-based coding agents on real-world GitHub pull requests.

## Overview

Long-Context-Bench evaluates how well coding agents can understand, modify, and integrate changes across large, multi-file repositories when given natural-language task instructions derived from PR metadata.

**Version:** v0.1.0 (Dataset v0, Harness v0.1.0)

## Features

- **Real-world tasks**: Benchmark based on actual merged GitHub PRs
- **Reproducible**: Deterministic scoring and artifact generation
- **Agent-agnostic**: Pluggable adapter system for different CLI agents
- **Scalable**: Support for sharding and parallel execution
- **Comprehensive metrics**: Five-dimensional scoring (correctness, completeness, code reuse, best practices, unsolicited documentation)

## Installation

### Prerequisites

- Python ≥ 3.11
- Git
- GitHub personal access token (for sampling)
- Agent-specific tokens (e.g., `AUGMENT_API_TOKEN` for Auggie)

### Install from source

```bash
git clone https://github.com/AugmentedAJ/Long-Context-Code-Bench.git
cd Long-Context-Code-Bench
pip install -e .
```

## Quick Start

### Environment Setup

```bash
# Required for sampling PRs
export GITHUB_GIT_TOKEN=your_github_token

# Required for running agents (example for Auggie)
export AUGMENT_API_TOKEN=your_augment_token
```

### Run on a Single PR

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  https://github.com/elastic/elasticsearch/pull/114951
```

### Run on the v0 Dataset (50 Elasticsearch PRs)

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --concurrency 4 \
  data/elasticsearch_prs_50.json
```

### Run with Sharding (for distributed execution)

```bash
# Shard 1 of 4
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --total-shards 4 \
  --shard-index 0 \
  data/elasticsearch_prs_50.json

# Shard 2 of 4
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --total-shards 4 \
  --shard-index 1 \
  data/elasticsearch_prs_50.json
```

## CLI Commands

### `sample`

Create a sample from a single PR:

```bash
long-context-bench sample https://github.com/elastic/elasticsearch/pull/114951
```

### `pipeline`

Run the complete pipeline (sample → edit → judge):

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  [--timeout 1800] \
  [--concurrency 1] \
  [--total-shards 1] \
  [--shard-index 0] \
  [--judge-mode deterministic] \
  [--disable-retrieval] \
  [--disable-shell] \
  <PR_URL or JSON_FILE>
```

### `stats`

Display statistics from a summary file:

```bash
long-context-bench stats output/summaries/<run_id>/summary.json
```

## Configuration Options

### Runner Options

- `--runner`: Runner name (e.g., `auggie`)
- `--model`: Model name (e.g., `claude-sonnet-4`)
- `--agent-binary`: Path to agent binary (optional)
- `--timeout`: Timeout in seconds (default: 1800)

### Execution Options

- `--concurrency`: Number of concurrent tasks (default: 1)
- `--total-shards`: Total number of shards (default: 1)
- `--shard-index`: Shard index, 0-based (default: 0)

### Judge Options

- `--judge-mode`: Judge mode (`deterministic` or `llm`, default: `deterministic`)
- `--judge-model`: Judge model for LLM mode (optional)

### Feature Flags

- `--disable-retrieval`: Disable retrieval features
- `--disable-shell`: Disable shell access
- `--enable-mcp-codebase-qa`: Enable MCP codebase QA

## Output Structure

```
output/
├── samples/
│   └── v0/
│       └── {owner}_{repo}_pr{number}/
│           └── sample.json
├── edits/
│   └── {runner}/
│       └── {model}/
│           └── {run_id}/
│               └── {owner}_{repo}_pr{number}/
│                   ├── edit.json
│                   └── logs.jsonl
├── judges/
│   └── {judge_mode}/
│       └── {judge_model}/
│           └── {run_id}/
│               └── {owner}_{repo}_pr{number}/
│                   └── judge.json
└── summaries/
    └── {run_id}/
        ├── summary.json
        └── run_manifest.json
```

## Metrics

The benchmark evaluates agents on five primary metrics (range: -1.0 to 1.0):

1. **Correctness**: Does the change implement the intended behavior?
2. **Completeness**: Does it achieve all requested changes?
3. **Code Reuse**: Preference for leveraging existing code
4. **Best Practices**: Style, structure, and idiomatic usage
5. **Unsolicited Documentation**: Penalty for unrequested documentation

The **aggregate score** is the unweighted average of these five metrics.

## Supported Runners

- **Auggie** (`auggie`): Augment's CLI coding agent

Additional runners can be added by implementing the `BaseRunner` interface.

## Dataset

**Version v0**: 50 recent merged PRs from the Elasticsearch repository.

Dataset file: `data/elasticsearch_prs_50.json`

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Code Formatting

```bash
black src/
ruff check src/
```

## License

- **Code**: Apache-2.0
- **Documentation**: CC BY 4.0

## Citation

If you use this benchmark in your research, please cite:

```bibtex
@software{long_context_bench,
  title = {Long-Context-Bench: A Benchmark for Long-Context Code Editing},
  author = {Augment Code},
  year = {2025},
  version = {0.1.0},
  url = {https://github.com/AugmentedAJ/Long-Context-Code-Bench}
}
```

## Contributing

Contributions are welcome! Please see our contributing guidelines.

## Support

For issues and questions, please open an issue on GitHub.

