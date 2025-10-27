# Upgrade Guide: v0.1.0 → v0.2.0

This guide helps you upgrade from Long-Context-Bench v0.1.0 to v0.2.0.

## What's New in v0.2.0

### 🎯 Built-in Dataset
No need to specify dataset file paths anymore! The dataset is automatically loaded from the repository.

### 🎯 Selective PR Execution
Run specific PRs using `--pr-numbers` or `--pr-indices` flags for faster development iteration.

### ⚡ Repository Caching
Repositories are cached for **4-10x speedup** on subsequent runs.

## Quick Migration

### Before (v0.1.0)
```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  data/elasticsearch_prs_50.json
```

### After (v0.2.0)
```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4
```

That's it! The dataset is now built-in.

## New Features

### 1. Run Specific PRs

#### By PR Number
```bash
# Run a single PR
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --pr-numbers "115001"

# Run multiple PRs
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --pr-numbers "115001,114998,114995"
```

#### By Index (0-based)
```bash
# Run first PR
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --pr-indices "0"

# Run first 5 PRs
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --pr-indices "0,1,2,3,4"
```

### 2. Repository Caching

Caching is **automatic** and enabled by default:

```bash
# First run: Clones repositories to .repo_cache/
long-context-bench pipeline --runner auggie --model claude-sonnet-4

# Second run: Reuses cached repositories (4-10x faster!)
long-context-bench pipeline --runner auggie --model claude-sonnet-4
```

#### Custom Cache Directory
```bash
long-context-bench pipeline \
  --runner auggie \
  --model claude-sonnet-4 \
  --cache-dir /path/to/my/cache
```

#### Clear Cache
```bash
rm -rf .repo_cache/
```

## Breaking Changes

### CLI Interface

**Changed:** The `input_path` argument is no longer required for the `pipeline` command.

**Before:**
```bash
long-context-bench pipeline --runner auggie --model claude-sonnet-4 data/elasticsearch_prs_50.json
```

**After:**
```bash
long-context-bench pipeline --runner auggie --model claude-sonnet-4
```

**Impact:** If you have scripts that pass the dataset file path, they will still work but the path is ignored. Update your scripts to remove the path argument.

## Updating Scripts

### Shell Scripts

**Before:**
```bash
#!/bin/bash
DATASET="data/elasticsearch_prs_50.json"
long-context-bench pipeline --runner auggie --model claude-sonnet-4 "$DATASET"
```

**After:**
```bash
#!/bin/bash
long-context-bench pipeline --runner auggie --model claude-sonnet-4
```

### GitHub Actions

**Before:**
```yaml
- name: Run benchmark
  run: |
    long-context-bench pipeline \
      --runner auggie \
      --model claude-sonnet-4 \
      data/elasticsearch_prs_50.json
```

**After:**
```yaml
- name: Run benchmark
  run: |
    long-context-bench pipeline \
      --runner auggie \
      --model claude-sonnet-4
```

### Python Scripts

**Before:**
```python
import subprocess

subprocess.run([
    "long-context-bench", "pipeline",
    "--runner", "auggie",
    "--model", "claude-sonnet-4",
    "data/elasticsearch_prs_50.json"
])
```

**After:**
```python
import subprocess

subprocess.run([
    "long-context-bench", "pipeline",
    "--runner", "auggie",
    "--model", "claude-sonnet-4"
])
```

## Performance Improvements

### Benchmark Comparison

| Scenario | v0.1.0 | v0.2.0 | Speedup |
|----------|--------|--------|---------|
| First run (50 PRs) | ~120 min | ~120 min | 1x |
| Second run (50 PRs) | ~120 min | ~20-30 min | **4-6x** |
| Single PR (first) | ~2-3 min | ~2-3 min | 1x |
| Single PR (cached) | ~2-3 min | ~10-30 sec | **4-10x** |

### Development Workflow

**Before (v0.1.0):**
- Test change on 1 PR: ~2-3 minutes
- Test change on 5 PRs: ~10-15 minutes
- Full benchmark: ~2 hours

**After (v0.2.0):**
- Test change on 1 PR: ~10-30 seconds (cached)
- Test change on 5 PRs: ~1-3 minutes (cached)
- Full benchmark: ~20-30 minutes (cached)

## Recommended Workflow

### Development Iteration

1. **Quick test** (1 PR):
   ```bash
   long-context-bench pipeline --runner auggie --model claude-sonnet-4 --pr-indices "0"
   ```

2. **Validation** (5 PRs):
   ```bash
   long-context-bench pipeline --runner auggie --model claude-sonnet-4 --pr-indices "0,1,2,3,4"
   ```

3. **Full benchmark** (50 PRs):
   ```bash
   long-context-bench pipeline --runner auggie --model claude-sonnet-4
   ```

### Debugging

Re-run a specific failing PR:
```bash
long-context-bench pipeline --runner auggie --model claude-sonnet-4 --pr-numbers "115001"
```

## FAQ

### Q: Do I need to delete the dataset file?
**A:** No, the dataset file is still included in the repository for reference. It's just not required as a CLI argument anymore.

### Q: Can I still use the old command with the file path?
**A:** The file path argument is no longer accepted. Update your scripts to remove it.

### Q: How much disk space does the cache use?
**A:** The Elasticsearch repository is ~500 MB. The cache will use approximately this much space.

### Q: Can I disable caching?
**A:** Caching is always enabled, but you can use a temporary directory that gets cleaned up:
```bash
long-context-bench pipeline --runner auggie --model claude-sonnet-4 --cache-dir /tmp/bench_cache
```

### Q: Does caching work with sharding?
**A:** Yes! All shards can share the same cache directory for maximum efficiency.

### Q: What if I want to force a fresh clone?
**A:** Delete the cache directory:
```bash
rm -rf .repo_cache/
```

## Troubleshooting

### Issue: "Dataset file not found"
**Solution:** Make sure you're running from the repository root or have installed the package correctly:
```bash
pip install -e .
```

### Issue: Cache directory permission errors
**Solution:** Ensure the cache directory is writable:
```bash
chmod -R u+w .repo_cache/
```

### Issue: Stale cache
**Solution:** Clear the cache and re-run:
```bash
rm -rf .repo_cache/
long-context-bench pipeline --runner auggie --model claude-sonnet-4
```

## Getting Help

- Read the [IMPROVEMENTS.md](IMPROVEMENTS.md) for detailed technical information
- Check the [README.md](README.md) for updated usage examples
- Review the [CHANGELOG.md](CHANGELOG.md) for all changes
- Open an issue on GitHub for bugs or questions

## Summary

v0.2.0 makes Long-Context-Bench **faster** and **easier to use**:
- ✅ No more file paths to remember
- ✅ Run specific PRs for faster iteration
- ✅ 4-10x speedup with automatic caching
- ✅ Simpler, cleaner CLI interface

Update your scripts by removing the dataset file path argument, and enjoy the performance boost!

