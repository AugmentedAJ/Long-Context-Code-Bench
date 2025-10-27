# Long-Context-Bench

A benchmark for evaluating long-context code editing capabilities of CLI-based coding agents on real-world GitHub pull requests.

## Overview

Long-Context-Bench evaluates how well coding agents can understand, modify, and integrate changes across large, multi-file repositories when given natural-language task instructions derived from PR metadata.

**Version**: v0.1.0 (dataset v0; harness v0.1.0)

## Features

- **Real-world PRs**: Evaluates on actual merged GitHub pull requests
- **Agent-agnostic**: Supports multiple CLI-based coding agents through pluggable adapters
- **Reproducible**: Deterministic scoring with full provenance tracking
- **Scalable**: Supports sharding and concurrency for parallel execution
- **Comprehensive metrics**: Evaluates correctness, completeness, code reuse, best practices, and unsolicited documentation

## Installation

### Prerequisites

- Python ≥3.11
- Git
- Node.js (for some agents)
- GitHub personal access token (for sampling)
- Agent-specific API tokens (for editing)

### Install from source

```bash
git clone https://github.com/AugmentedAJ/Long-Context-Code-Bench.git
cd Long-Context-Code-Bench
pip install -e .
```

### Environment Variables

```bash
# Required for sampling (GitHub API access)
export GITHUB_GIT_TOKEN="your_github_token"

# Required for editing (agent-specific)
export AUGMENT_API_TOKEN="your_augment_token"  # For Auggie
# or other agent-specific tokens
```

## Quick Start

### Run on a single PR

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  https://github.com/elastic/elasticsearch/pull/12345
```

### Run on the full v0 dataset (50 Elasticsearch PRs)

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  data/elasticsearch_prs_50.json
```

### Run individual stages

```bash
# Sample stage only
long-context-bench sample https://github.com/elastic/elasticsearch/pull/12345

# Edit stage (requires existing sample)
long-context-bench edit \
  --runner auggie \
  --model claude-sonnet-4 \
  --sample-dir output/samples/v0/elastic_elasticsearch_pr12345

# Judge stage (requires sample and edit)
long-context-bench judge \
  --sample-dir output/samples/v0/elastic_elasticsearch_pr12345 \
  --edit-dir output/edits/auggie/claude-sonnet-4/run_123/elastic_elasticsearch_pr12345
```

## Command Reference

### Global Options

- `--output-dir PATH`: Output directory for artifacts (default: `./output`)
- `--verbose`: Enable verbose logging
- `--quiet`: Suppress non-error output

### `sample` - Sample PRs and generate task instructions

```bash
long-context-bench sample [OPTIONS] INPUT
```

**Arguments:**
- `INPUT`: PR URL, JSON file of URLs, or directory of samples

**Options:**
- `--dataset-version TEXT`: Dataset version (default: v0)

### `edit` - Run agent to produce edits

```bash
long-context-bench edit [OPTIONS]
```

**Options:**
- `--runner TEXT`: Agent runner (required)
- `--model TEXT`: Model name (required)
- `--agent-binary PATH`: Path to agent binary
- `--sample-dir PATH`: Sample directory or file
- `--timeout INT`: Per-task timeout in seconds (default: 1800)
- `--concurrency INT`: Max concurrent tasks (default: 1)
- `--total-shards INT`: Total number of shards (default: 1)
- `--shard-index INT`: Shard index (0-based, default: 0)
- `--disable-retrieval`: Disable codebase retrieval
- `--disable-shell`: Disable shell access
- `--enable-mcp-codebase-qa`: Enable MCP codebase QA

### `judge` - Score agent edits

```bash
long-context-bench judge [OPTIONS]
```

**Options:**
- `--sample-dir PATH`: Sample directory
- `--edit-dir PATH`: Edit directory
- `--judge-mode TEXT`: Judge mode: deterministic or llm (default: deterministic)
- `--judge-model TEXT`: Judge model (for llm mode)
- `--concurrency INT`: Max concurrent tasks (default: 4)

### `pipeline` - Run full pipeline (sample → edit → judge)

```bash
long-context-bench pipeline [OPTIONS] INPUT
```

Combines all options from `sample`, `edit`, and `judge` commands.

### `stats` - Generate statistics and summaries

```bash
long-context-bench stats [OPTIONS] RUN_DIR
```

**Options:**
- `--format TEXT`: Output format: json, csv, or both (default: both)

## Sharding and Parallelism

For large-scale runs, use sharding to distribute work across multiple machines:

```bash
# Machine 1 (shard 0 of 4)
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --total-shards 4 \
  --shard-index 0 \
  --concurrency 4 \
  data/elasticsearch_prs_50.json

# Machine 2 (shard 1 of 4)
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --total-shards 4 \
  --shard-index 1 \
  --concurrency 4 \
  data/elasticsearch_prs_50.json

# ... and so on for shards 2 and 3
```

## Output Structure

```
output/
├── samples/
│   └── v0/
│       └── elastic_elasticsearch_pr12345/
│           ├── sample.json
│           └── sample_meta.json
├── edits/
│   └── auggie/
│       └── claude-sonnet-4/
│           └── run_20240127_120000/
│               └── elastic_elasticsearch_pr12345/
│                   ├── edit.json
│                   └── logs.jsonl
├── judges/
│   └── deterministic/
│       └── none/
│           └── run_20240127_120000/
│               └── elastic_elasticsearch_pr12345/
│                   └── judge.json
└── summaries/
    └── run_20240127_120000/
        ├── summary.json
        ├── summary.csv
        └── run_manifest.json
```

## Metrics

The benchmark evaluates five primary metrics (range: -1.0 to 1.0):

1. **Correctness**: Does the change implement the intended behavior?
2. **Completeness**: Does it achieve all requested changes and nothing extra?
3. **Code Reuse**: Preference for leveraging existing code over duplication
4. **Best Practices**: Style, structure, and idiomatic usage
5. **Unsolicited Documentation**: Penalty for documentation added when not requested

The aggregate score is the unweighted average of these five metrics.

## Supported Runners

- `auggie`: Augment's CLI agent
- More runners coming soon (contributions welcome!)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on adding new runner adapters.

## License

- Harness code: Apache-2.0
- Documentation: CC BY 4.0
- Dataset metadata: Compliant with GitHub ToS

## Citation

If you use this benchmark in your research, please cite:

```bibtex
@software{long_context_bench,
  title = {Long-Context-Bench: A Benchmark for Long-Context Code Editing},
  author = {Augment Code},
  year = {2024},
  url = {https://github.com/AugmentedAJ/Long-Context-Code-Bench}
}
```

