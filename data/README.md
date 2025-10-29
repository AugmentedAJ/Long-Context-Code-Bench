# Dataset Files

This directory contains the benchmark datasets for Long-Context-Code-Bench.

## Files

### `elasticsearch_prs_50.json`
**Current default dataset (v0)**

- **Size:** 42 validated PRs from elastic/elasticsearch
- **Methodology:** PR recreation - agents recreate changes given PR descriptions
- **Status:** Curated and validated (no 404s)

This is the primary dataset used by the benchmark. It contains only valid PR URLs that can be successfully fetched from GitHub.

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

The v0 dataset was curated to remove GitHub issue numbers that would cause 404 errors:

1. **Original dataset:** 50 entries (mix of PRs and issues)
2. **Identified issues:** 8 entries were GitHub issues, not PRs
3. **Removed issue numbers:** 114968, 114962, 114956, 114947, 114941, 114926, 114902, 114893
4. **Final dataset:** 42 validated PRs

### Reproduction

To reproduce the curation:

```bash
python scripts/make_v0_valid_from_known_issues.py \
  --input data/elasticsearch_prs_50_original.json \
  --out data/elasticsearch_prs_50.json
```

## Future Datasets

A v2 dataset is under development on the `feature/v2-issue-based-dataset` branch. It uses a different methodology:

- Maps GitHub issues to their closing PRs
- Uses issue descriptions (the problem) as task instructions
- Uses PR diffs (the solution) as ground truth

This represents a different evaluation paradigm: solving problems from scratch vs. recreating described solutions.

