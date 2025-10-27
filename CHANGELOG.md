# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-10-27

### Added

- Initial release of Long-Context-Bench harness (v0.1.0)
- Dataset v0: 50 Elasticsearch PRs
- Sample stage: PR metadata extraction and task instruction generation
- Edit stage: Agent execution with workspace management
- Judge stage: Deterministic baseline judge with five-metric scoring
- Pipeline orchestration with sharding and concurrency support
- CLI with subcommands: `sample`, `pipeline`, `stats`
- Auggie runner adapter
- Comprehensive documentation (README, PRD)
- Apache-2.0 license for code
- CC BY 4.0 license for documentation

### Known Limitations

- LLM-based judge not yet implemented (falls back to deterministic)
- Standalone `edit` and `judge` commands not yet implemented
- Directory input for samples not yet implemented
- Limited to Auggie runner (additional runners can be added)

## [Unreleased]

### Planned

- LLM-based judge implementation
- Additional runner adapters (Claude Code, GitHub Copilot)
- CSV export for summaries
- Run manifest generation
- GitHub Actions workflow for CI
- Comprehensive test suite
- Dataset v1 with expanded corpus

