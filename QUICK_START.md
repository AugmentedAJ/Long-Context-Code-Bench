# Long-Context-Bench Quick Start Guide

## Installation

```bash
# Clone the repository
git clone https://github.com/AugmentedAJ/Long-Context-Code-Bench.git
cd Long-Context-Code-Bench

# Install the package
pip install -e .
```

## Prerequisites

Set up your environment variables:

```bash
export GITHUB_GIT_TOKEN=your_github_token_here
export AUGMENT_API_TOKEN=your_augment_token_here  # If using Auggie
```

## Basic Usage

### Run on Full Dataset (50 PRs)

The dataset is built-in, no need to specify a file:

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4
```

### Run on Specific PRs

By PR number:

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --pr-numbers "115001,114998,114995"
```

By index (0-based):

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --pr-indices "0,1,2"
```

### View Results

```bash
long-context-bench stats output/
```

## Advanced Usage

### Parallel Execution with Sharding

Run 4 shards in parallel (in separate terminals or CI jobs):

```bash
# Terminal 1
long-context-bench pipeline --runner auggie --model claude-sonnet-4 \
  --total-shards 4 --shard-index 0

# Terminal 2
long-context-bench pipeline --runner auggie --model claude-sonnet-4 \
  --total-shards 4 --shard-index 1

# Terminal 3
long-context-bench pipeline --runner auggie --model claude-sonnet-4 \
  --total-shards 4 --shard-index 2

# Terminal 4
long-context-bench pipeline --runner auggie --model claude-sonnet-4 \
  --total-shards 4 --shard-index 3
```

### Custom Configuration

```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --timeout 3600 \
  --concurrency 2 \
  --disable-retrieval \
  --judge-mode deterministic \
  --cache-dir .my_cache
```

## Individual Stages

### 1. Sample Only

Samples are created automatically from the built-in dataset:

```bash
long-context-bench sample --dataset-version v0
```

### 2. Edit Only

```bash
long-context-bench edit \
  --runner auggie \
  --model claude-sonnet-4 \
  output/samples/v0/elastic_elasticsearch_pr115001/sample.json
```

### 3. Judge Only

```bash
long-context-bench judge \
  output/samples/v0/elastic_elasticsearch_pr115001/sample.json \
  output/edits/auggie/claude-sonnet-4/<run_id>/elastic_elasticsearch_pr115001/edit.json
```

## Output Structure

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

## Understanding Results

### Metrics (Range: -1.0 to 1.0)

- **Correctness**: Does the change implement the intended behavior?
- **Completeness**: Does it achieve all requested changes?
- **Code Reuse**: Preference for leveraging existing code
- **Best Practices**: Style, structure, and idiomatic usage
- **Unsolicited Docs**: Penalty for unrequested documentation

### Aggregate Score

Unweighted average of the five metrics.

### Example Output

```
Aggregate Statistics
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Metric                 ┃ Value  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ Total Samples          │ 50     │
│ Successful             │ 45     │
│ Failed                 │ 5      │
│ Success Rate           │ 90.0%  │
│ Mean Aggregate Score   │ 0.65   │
│ Mean Correctness       │ 0.70   │
│ Mean Completeness      │ 0.68   │
└────────────────────────┴────────┘
```

## Troubleshooting

### GitHub Rate Limits

If you hit rate limits:
- Use an authenticated token (GITHUB_GIT_TOKEN)
- Reduce concurrency
- Use sharding to distribute load

### Timeouts

If tasks timeout:
- Increase `--timeout` (default: 1800s)
- Check agent configuration
- Review logs in `output/edits/.../logs.jsonl`

### Agent Errors

Check the edit.json file for error details:
```bash
cat output/edits/<runner>/<model>/<run_id>/<pr_id>/edit.json
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [CONTRIBUTING.md](CONTRIBUTING.md) to contribute
- Review [prd.md](prd.md) for complete requirements
- See [examples/](examples/) for shell scripts

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review the implementation summary in [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

