# Prompt Synthesis

This document describes the prompt synthesis feature in Long-Context-Code-Bench, which generates natural task instructions from PR metadata using LLMs.

## Overview

Long-Context-Code-Bench supports **two types of task instructions**:

1. **Template-based** (default): Simple concatenation of PR title and body
2. **Synthesized** (optional): LLM-generated natural instructions that mimic how a human would describe the task

## Why Synthesize Prompts?

### Benefits

- **More natural**: Synthesized prompts read like human requests, not PR descriptions
- **Focused**: LLM extracts the core task, filtering out PR metadata and solution details
- **Consistent style**: All prompts follow a similar tone and length
- **Better for evaluation**: More realistic representation of how agents are used in practice

### Comparison

**Template-based prompt:**
```
You are working on a codebase. Your task is to make the necessary code changes to accomplish the following:

[DOCS] Update local data extraction version info

This PR updates the documentation to reflect the new version of the local data extraction module.

Please make all necessary code changes to complete this task.
```

**Synthesized prompt:**
```
Update the documentation for the local data extraction module version
```

## How It Works

### Synthesis Process

1. **Input**: PR title, body, and diff
2. **LLM Analysis**: An LLM (default: Claude Sonnet 3.7) analyzes the PR at the HEAD commit
3. **Extraction**: The LLM generates a concise user message that could have prompted the PR
4. **Storage**: The synthesized instruction is saved in `sample.json` alongside the template-based version

### Synthesis Prompt

The synthesis prompt analyzes the PR and generates a natural user message:

```
Analyze the following pull request and the codebase thoroughly and
generate the user message that created it.

The pull request title is:
```
[PR title]
```
The pull request body is:
```
[PR body]
```
The pull request diff is:
```
[PR diff]
```

Example user messages:
--------------
Fix the bug in the search query parser
--------------
Add support for custom field mappings
--------------
...
```

### Guidelines

The LLM follows these rules:
- Focus on non-test code changes
- Match the style and length of example messages
- Don't mention the PR itself
- Don't provide solution details
- Output format: `<user_message>...</user_message>`

## Usage

### Option A: One-off synthesis (legacy / custom datasets)

You can still enable on-the-fly synthesis during the sample stage for custom PR lists:

```bash
long-context-bench sample data/elasticsearch_prs_50.json \
    --output-dir data/samples \
    --dataset-version custom-synthesized \
    --synthesize \
    --synthesis-model auggie/claude-sonnet-4.5 \
    --cache-dir .repo_cache
```

**Flags:**
- `--synthesize`: Enable prompt synthesis
- `--synthesis-model`: Model for synthesis (LiteLLM model or `auggie/<model>`)

**Synthesis Methods:**
1. **Auggie CLI** (recommended): Use `auggie/<model>` prefix (e.g., `auggie/claude-sonnet-4.5`)
   - Requires: `auggie login` for authentication
   - No API keys needed
2. **LiteLLM**: Use model name directly (e.g., `claude-3-7-sonnet-20250219`)
   - Requires: `pip install litellm` and API keys (e.g., `ANTHROPIC_API_KEY`)

### Option B: Use pre-synthesized prompts for the public v1 Elasticsearch dataset

The repository includes a public prompt dataset for 100 Elasticsearch PRs under `prompt_dataset/`.
We precomputed and aligned 5 synthesized prompt variants per PR and wired them directly into
the sampling stage. The v1 dataset lives at:

- PR list: `data/elasticsearch_prs_100_prompt_dataset.json`
- Samples: `data/samples/v1/elastic_elasticsearch_pr*/sample.json`

To (re)generate v1 samples from the PR list using the built-in synthesized prompts mapping:

```bash
long-context-bench sample data/elasticsearch_prs_100_prompt_dataset.json \
    --output-dir data/samples \
    --dataset-version v1 \
    --cache-dir .repo_cache \
    --force
```

During sampling, Long-Context-Bench will:

- Look up the PR number in `prompt_dataset/synthesized_prompts_mapping.json`
- Randomly choose one of the 5 verbosity variants for that PR
- Use that text as `task_instructions` in `sample.json`
- Fall back to the older template-based instructions if a PR is missing from the mapping

The v1 dataset in this repository was created this way, and the resulting `sample.json` files
are checked in for reproducibility.

### Step 2: Run Edit Stage

For the public v0 and v1 datasets, `task_instructions` are already populated in `sample.json`.
You simply point the edit stage at the appropriate directory:

```bash
# v0: 40 Elasticsearch PRs
long-context-bench edit data/samples/v0 \
    --runner auggie \
    --model claude-sonnet-4.5 \
    --test-label v0-benchmark

# v1: 100 Elasticsearch PRs using the public prompt dataset
long-context-bench edit data/samples/v1 \
    --runner auggie \
    --model claude-sonnet-4.5 \
    --test-label v1-benchmark
```

### Step 3: Compare Results

Use test labels to compare performance:

```bash
# View results in web dashboard
cd output/web
npm install  # First time only
npm start
```

Filter by test label to see:
- How synthesized prompts perform vs template-based
- Which approach yields better correctness/completeness scores

## Sample Model Schema

The `Sample` model includes optional synthesis fields:

```python
class Sample(BaseModel):
    # ... existing fields ...
    task_instructions: str  # Template-based (always present)
    
    # Optional synthesis fields
    synthesized_task_instructions: Optional[str] = None
    synthesis_model: Optional[str] = None
    synthesis_timestamp: Optional[str] = None
```

**Example `sample.json`:**
```json
{
  "dataset_version": "v1-synthesized",
  "repo_url": "https://github.com/elastic/elasticsearch.git",
  "pr_number": 115001,
  "base_commit": "abc123...",
  "head_commit": "def456...",
  "task_instructions": "You are working on a codebase...",
  "stats": { ... },
  "synthesized_task_instructions": "Fix the memory leak in the aggregation module",
  "synthesis_model": "claude-3-7-sonnet-20250219",
  "synthesis_timestamp": "2025-01-30T12:34:56Z"
}
```

## Customization

### Custom Example Messages

Modify `DEFAULT_EXAMPLE_MESSAGES` in `long_context_bench/synthesis.py`:

```python
DEFAULT_EXAMPLE_MESSAGES = [
    "Your custom example 1",
    "Your custom example 2",
    # ...
]
```

### Different Models

Use any LiteLLM-supported model:

```bash
# OpenAI GPT-4
--synthesis-model gpt-4-turbo

# Anthropic Claude
--synthesis-model claude-3-7-sonnet-20250219

# Local model via Ollama
--synthesis-model ollama/llama3
```

### Adjust Diff Truncation

Modify `max_diff_chars` in `synthesize_task_instructions()`:

```python
synthesized_instructions = synthesize_task_instructions(
    pr_title=pr_title,
    pr_body=pr_body,
    pr_diff=pr_diff,
    model=synthesis_model,
    max_diff_chars=100000,  # Increase for larger diffs
)
```

## Cost Considerations

Synthesis requires LLM API calls:
- **Cost per sample**: ~$0.01-0.05 (depending on model and diff size)
- **For 50 PRs**: ~$0.50-2.50
- **For 1000 PRs**: ~$10-50

**Recommendation**: Synthesize once during dataset creation, then reuse the cached results.

## Troubleshooting

### Synthesis Fails

If synthesis fails, the sample stage continues with template-based instructions only:

```
✗ Synthesis failed: API rate limit exceeded
✓ Sampled elastic_elasticsearch_pr115001 (template-based only)
```

### Missing Synthesized Instructions

If you run edit stage with `--use-synthesized` but samples don't have synthesized instructions:

```
Warning: --use-synthesized specified but no synthesized instructions available, using template-based
```

**Solution**: Re-run sample stage with `--synthesize --force`

### API Key Not Found

```
Error: ANTHROPIC_API_KEY not found
```

**Solution**: Set the appropriate environment variable for your model provider:
```bash
export ANTHROPIC_API_KEY=your-key-here
export OPENAI_API_KEY=your-key-here
```

## See Also

- [LiteLLM documentation](https://docs.litellm.ai/) - Model configuration
- [RUNNERS.md](RUNNERS.md) - Agent runner documentation

