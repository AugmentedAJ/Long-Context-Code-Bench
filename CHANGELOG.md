# Changelog

All notable changes to Long-Context-Bench will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-XX

### Added
- Initial release of Long-Context-Bench harness (v0.1.0)
- Dataset v0: 50 Elasticsearch PRs from `data/elasticsearch_prs_50.json`
- Sample stage: Extract PR metadata and create sample.json files
- Edit stage: Run agents on samples and capture diffs
- Judge stage: Score agent edits against ground truth
- Pipeline orchestration: Run sample → edit → judge
- Support for sharding and concurrency
- Deterministic judge mode with overlap heuristics
- Runner adapters: Auggie and Generic
- CLI with subcommands: `sample`, `edit`, `judge`, `pipeline`, `stats`
- Aggregate statistics and reporting (JSON and CSV)
- Run manifest for full provenance tracking
- GitHub Actions workflow for CI/CD
- Comprehensive documentation (README.md, PRD)

### Dataset
- v0: 50 PRs from elastic/elasticsearch (frozen)
- PRs range from #114854 to #115001

### Known Limitations
- LLM judge mode not yet implemented (falls back to deterministic)
- Concurrency support is sequential (to be parallelized in future versions)
- Retry logic for transient failures not yet implemented
- Directory-based judging not yet implemented

## [0.2.0] - 2025-01-XX

### Added
- **Built-in dataset support**: No need to specify dataset file path, automatically loaded from repository
- **Selective PR execution**: New `--pr-numbers` and `--pr-indices` flags to run specific PRs
- **Repository caching**: Repositories cached in `.repo_cache/` for 4-10x speedup on subsequent runs
- **Configurable cache directory**: `--cache-dir` option to customize cache location
- New tests for dataset loading and filtering (6 additional tests)

### Changed
- **Breaking**: Removed required `input_path` argument from `pipeline` command (now optional, uses built-in dataset by default)
- Updated CLI help text to clarify default behavior
- Updated README and QUICK_START with new usage examples
- Updated example scripts to use new CLI interface

### Performance
- **4-10x faster** on subsequent runs with repository caching
- Reduced network bandwidth usage
- Reduced GitHub API rate limit pressure

### Documentation
- Added IMPROVEMENTS.md with detailed explanation of changes
- Updated all documentation to reflect new CLI interface
- Added migration guide for existing scripts

## [Unreleased]

### Planned
- LLM-based judge implementation
- Parallel execution with worker pools
- Retry logic with exponential backoff
- Enhanced error handling and logging
- Support for additional runners (claude-code, copilot)
- Token usage tracking
- Custom metric weighting via config file
- Cache compression and cleanup policies

