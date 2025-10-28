# Long-Context-Bench

A benchmark for evaluating and ranking long-context code editing capabilities of CLI-based coding agents on real-world GitHub pull requests from massive codebases.

## Overview

Long-Context-Bench evaluates how well coding agents can understand, modify, and integrate changes across **massive repositories with tens of thousands of files** when given natural-language task instructions derived from PR metadata. The primary use cases are **generating leaderboards** to rank agent performance and **comparing agents side-by-side** using labeled test runs.

**Key Features:**
- 🏆 **Leaderboard Generation**: Rank multiple agents across standardized benchmarks
- 🔬 **Agent Comparison**: Label runs and generate side-by-side performance comparisons
- 📊 Evaluates agents on 50 real Elasticsearch PRs (dataset v0, ~40K files per codebase)
- 🔌 Agent-agnostic: pluggable adapters for different CLI agents (Auggie, Claude Code, etc.)
- 📈 Comprehensive metrics: correctness, completeness, code reuse, best practices, and more
- ⚡ Scalable: supports sharding and concurrency for parallel execution
- 📝 Traceable: complete provenance tracking for all runs

## Installation

### Prerequisites

- Python ≥ 3.11
- Git
- GitHub token for API access (set as `GITHUB_GIT_TOKEN`)
- **Agent authentication** (choose one):
  - **Auggie**: OAuth login (recommended) or API token
  - **Claude Code**: OAuth login (recommended) or API key

### Install from source

```bash
git clone https://github.com/AugmentedAJ/Long-Context-Code-Bench.git
cd Long-Context-Code-Bench
pip install -e .
```

## Quick Start: Leaderboard & Comparison

The primary workflows are generating leaderboards to rank agents and comparing specific agents side-by-side using test labels.

### 1. Authenticate with Agents

**Recommended: Use OAuth (subscription mode)**

For Auggie:
```bash
auggie login  # Opens browser for OAuth authentication
```

For Claude Code:
```bash
claude setup-token  # Sets up subscription-based authentication
```

**Alternative: Use API keys/tokens**

```bash
export GITHUB_GIT_TOKEN=your_github_token

# For Auggie (if not using OAuth)
export AUGMENT_API_TOKEN=your_augment_token

# For Claude Code (if not using OAuth)
export ANTHROPIC_API_KEY=your_key

# For LLM judge (optional)
export OPENAI_API_KEY=your_key
```

### 2. Generate Samples (One-Time Setup)

Extract PR metadata and create sample files:

```bash
long-context-bench sample
```

This creates `output/samples/v0/<pr_id>/sample.json` for all 50 PRs in the dataset.

### 3. Run Agents with Test Label

Run each agent you want to compare, using the **same test label**:

```bash
# Run Auggie
long-context-bench edit output/samples/v0 \
  --runner auggie \
  --model claude-sonnet-4.5 \
  --test-label "sonnet-4.5-comparison"

# Run Claude Code
long-context-bench edit output/samples/v0 \
  --runner claude-code \
  --model claude-sonnet-4.5 \
  --test-label "sonnet-4.5-comparison"
```

**Note:** Agent runs are non-deterministic. Running the same agent multiple times will produce different results due to the stochastic nature of LLMs.

### 4. Evaluate Results

Judge the agent outputs against ground truth:

```bash
long-context-bench judge \
  --edit-run-ids <run_id_1>,<run_id_2> \
  --test-label "sonnet-4.5-comparison"
```

You can find the edit run IDs in the console output or in `output/edits/<runner>/<model>/` directories.

### 5. Generate Leaderboard or Comparison

**Option A: Generate Leaderboard (Ranked)**

Create a ranked leaderboard of all agents:

```bash
long-context-bench compare output/ "sonnet-4.5-comparison" \
  --format leaderboard \
  --rank-by mean_aggregate \
  --output-file leaderboard.csv
```

This displays agents ranked by performance (default: mean aggregate score).

**Option B: Generate Side-by-Side Comparison**

Create a detailed side-by-side comparison:

```bash
long-context-bench compare output/ "sonnet-4.5-comparison" \
  --format comparison \
  --output-file comparison.csv
```

Both formats support CSV and JSON output.

## Features

### Leaderboard Generation

Rank multiple agents across standardized benchmarks:

1. **Run agents with a test label**: Execute multiple agents/models with the same test label (e.g., `--test-label "v0-leaderboard"`)
2. **Generate leaderboard**: Use `compare --format leaderboard` to rank all agents by performance
3. **Customize ranking**: Use `--rank-by` to rank by different metrics (mean_aggregate, success_rate, tasks_per_hour, etc.)
4. **Export results**: Save leaderboard as CSV or JSON for sharing

Example command:
```bash
long-context-bench compare output/ "v0-leaderboard" \
  --format leaderboard \
  --rank-by mean_aggregate \
  --output-file leaderboard.csv
```

Example leaderboard output:
```
┌──────┬─────────────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ Rank │ Agent               │ Success Rate │ Mean Agg     │ Tasks/Hour   │ Total Samples│
├──────┼─────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│  1   │ auggie/sonnet-4.5   │ 88.0%        │ 0.82         │ 85.3         │ 50           │
│  2   │ claude-code/sonnet  │ 85.0%        │ 0.78         │ 72.1         │ 50           │
│  3   │ auggie/opus-4       │ 82.0%        │ 0.75         │ 45.2         │ 50           │
│  4   │ cursor/gpt-4        │ 78.0%        │ 0.71         │ 92.5         │ 50           │
└──────┴─────────────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

**Ranking Metrics:**
- `mean_aggregate` (default): Overall performance score
- `success_rate`: Percentage of successful completions
- `tasks_per_hour`: Speed/throughput metric
- `mean_correctness`: Accuracy of changes
- `mean_completeness`: Coverage of required changes

### Agent Comparison with Test Labels

Compare specific agents side-by-side:

1. **Label your runs**: Add `--test-label "my-comparison"` to edit and judge commands
2. **Run multiple agents**: Execute different agents/models with the same test label
3. **Generate comparison**: Use `compare` command to see side-by-side metrics

Example comparison output:
```
┌─────────────────────┬──────────────┬──────────────┐
│ Metric              │ auggie       │ claude-code  │
├─────────────────────┼──────────────┼──────────────┤
│ Success Rate        │ 85.0%        │ 82.0%        │
│ Mean Correctness    │ 0.78         │ 0.75         │
│ Mean Completeness   │ 0.82         │ 0.79         │
│ Mean Aggregate      │ 0.78         │ 0.75         │
│ Tasks/Hour          │ 80.0         │ 69.2         │
└─────────────────────┴──────────────┴──────────────┘
```

### Built-in Dataset

The v0 dataset (50 Elasticsearch PRs) is included in the repository. No need to download or specify file paths!

### Repository Caching & Workspace Isolation

The benchmark implements strict workspace isolation to ensure valid, unbiased evaluation:

**Workspace Materialization:**
- Each agent run gets a fresh, isolated workspace initialized at the base commit
- Shallow fetch (--depth=1) minimizes git history exposure
- The `.git` directory is hidden from agents during execution to prevent history inspection
- After agent execution, `.git` is restored to capture accurate diffs

**Cache Usage:**
- Repositories are cached in `.repo_cache/` for sample/judge stages (not for agent workspaces)
- Shallow fetches minimize bandwidth and history exposure
- Cache is used only for fetching commits needed for ground-truth diffs

**Security:**
- Agents cannot access PR fix commits or full git history
- No persistent remote configured in agent workspaces
- Git interactive prompts disabled during execution

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
# Recommended: Use OAuth (run 'auggie login' first)
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4

# Alternative: Use API token
export AUGMENT_API_TOKEN=your_token
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4
```

**Authentication:**
- **Recommended:** OAuth via `auggie login` (uses subscription)
- **Alternative:** Set `AUGMENT_API_TOKEN` environment variable

**Model aliases:** Use `sonnet`, `opus`, `haiku` or full model names

### Claude Code

Anthropic's command-line coding agent.

```bash
# Recommended: Use OAuth (run 'claude setup-token' first)
long-context-bench pipeline \
  --runner claude-code \
  --model sonnet

# Alternative: Use API key
export ANTHROPIC_API_KEY=your_key
long-context-bench pipeline \
  --runner claude-code \
  --model sonnet
```

**Authentication:**
- **Recommended:** OAuth via `claude setup-token` (uses subscription)
- **Alternative:** Set `ANTHROPIC_API_KEY` environment variable

**Model aliases:** Use `sonnet`, `opus`, `haiku` or full model names like `claude-sonnet-4`

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

### Web Dashboard (Recommended)

The benchmark automatically generates an interactive web dashboard for visualizing results.

#### Starting the Web Server

After running any benchmark command, start the web server:

```bash
cd output/web
npm install  # First time only
npm start
```

Then open http://localhost:3000 in your browser.

The web app provides:
- **Leaderboard**: Compare all runs with filtering and sorting
- **Run Details**: Deep dive into individual run metrics and per-PR results
- **Agent Comparison**: Side-by-side comparison with interactive charts
- **Real-time Updates**: Refresh to see latest results

The web app is automatically deployed and updated when you run:
- `long-context-bench pipeline`
- `long-context-bench summary`
- `long-context-bench stats`
- `long-context-bench compare`

### Generate Statistics (CLI)

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
├── web/                          # Interactive web dashboard
│   ├── index.html               # Leaderboard view
│   ├── summary.html             # Run details view
│   └── comparison.html          # Agent comparison view
├── index.json                   # Manifest for web app
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

## Reproducibility and Provenance

All runs record complete provenance for traceability:

- Dataset version
- Harness version
- Runner and model
- OS and Python version
- All flags and configuration
- Timestamps
- Test label (for comparison runs)

**Important:** Agent runs are **non-deterministic** due to the stochastic nature of LLMs. Running the same agent with identical inputs will produce different outputs each time. This is why the benchmark uses:
- **Unique run IDs** for each execution
- **Test labels** to group related runs for comparison
- **Complete provenance tracking** to understand what produced each result

The **judge stage** (evaluation) is deterministic when using `--judge-mode deterministic` (default), ensuring consistent scoring of the same agent output.

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

