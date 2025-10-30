# Dataset Files

This directory contains the benchmark datasets for Long-Context-Code-Bench.

## Files

### `elasticsearch_prs_50.json`
**Current default dataset (v0) - PR URLs**

- **Size:** 42 validated PRs from elastic/elasticsearch
- **Methodology:** PR recreation - agents recreate changes given PR descriptions
- **Status:** Curated and validated (no 404s)

This is the primary dataset used by the benchmark. It contains only valid PR URLs that can be successfully fetched from GitHub.

### `samples/v0/`
**Pre-synthesized prompts for v0 dataset**

- **Size:** 40 PRs with synthesized task instructions (2 PRs return 404 from GitHub)
- **Synthesis Model:** `auggie/claude-sonnet-4.5`
- **Synthesis Date:** 2025-10-30
- **Status:** Standard dataset for v0 benchmark runs

This directory contains the **official v0 dataset** with pre-synthesized task instructions. The pipeline automatically uses these samples instead of re-sampling from GitHub. Each `sample.json` includes:
- PR metadata (base/head commits, repo URL)
- Template-based task instructions (PR title + body)
- **Synthesized task instructions** (LLM-generated natural prompts)
- Diff statistics and context size

**This is the standard dataset that will be used for all published v0 benchmark results.**

### `elasticsearch_prs_50_original.json`
**Original uncurated dataset**

- **Size:** 50 entries (mix of PRs and issues)
- **Status:** Archived for reference
- **Issues:** Contains 8 GitHub issue numbers that cause 404 errors when fetched as PRs

This file is preserved for reproducibility and historical reference. It is **not** used by the benchmark.

### `elasticsearch_prs_50_v0_valid.json`
**Intermediate validated dataset**

- **Size:** 42 validated PRs
- **Status:** Identical to current `elasticsearch_prs_50.json`

This file was generated during curation and is kept for backward compatibility. It is functionally identical to the current default dataset.

## Curation Process

The v0 dataset was curated in two stages:

### Stage 1: PR URL Validation

Removed GitHub issue numbers that would cause 404 errors:

1. **Original dataset:** 50 entries (mix of PRs and issues)
2. **Identified issues:** 8 entries were GitHub issues, not PRs
3. **Removed issue numbers:** 114968, 114962, 114956, 114947, 114941, 114926, 114902, 114893
4. **Final dataset:** 42 validated PR URLs

To reproduce:

```bash
python scripts/make_v0_valid_from_known_issues.py \
  --input data/elasticsearch_prs_50_original.json \
  --out data/elasticsearch_prs_50.json
```

### Stage 2: Prompt Synthesis

Generated natural task instructions for all valid PRs:

1. **Input:** 42 validated PR URLs
2. **Synthesis:** Used `auggie/claude-sonnet-4.5` to generate concise, natural task instructions
3. **Output:** 40 complete samples (2 PRs returned 404 during synthesis)
4. **Location:** `data/samples/v0/`

The synthesized prompts are more concise and natural than template-based prompts, better reflecting how developers actually use coding agents.

**Example:**
- **Template-based** (369 chars): "You are working on a codebase. Your task is to make the necessary code changes to accomplish the following: [DOCS] Update local data extraction version info..."
- **Synthesized** (69 chars): "Update the documentation for the local data extraction module version"

## Future Datasets

A v2 dataset is under development on the `feature/v2-issue-based-dataset` branch. It uses a different methodology:

- Maps GitHub issues to their closing PRs
- Uses issue descriptions (the problem) as task instructions
- Uses PR diffs (the solution) as ground truth

This represents a different evaluation paradigm: solving problems from scratch vs. recreating described solutions.

