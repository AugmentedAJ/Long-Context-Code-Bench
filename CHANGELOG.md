# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-01-27

### Added
- Initial release of Long-Context-Bench harness v0.1.0
- Dataset v0: 50 Elasticsearch PRs from `data/elasticsearch_prs_50.json`
- Sample stage: Clone repos, extract PR metadata, compute statistics
- Edit stage: Run agents with pluggable runner adapters
- Judge stage: Deterministic baseline judge with 5 metrics
- Pipeline orchestration with sharding and concurrency support
- CLI with subcommands: sample, edit, judge, pipeline, stats
- Comprehensive artifact tracking and provenance recording
- Support for Auggie runner adapter
- Documentation: README, PRD, and inline code documentation
- Apache-2.0 license for code, CC BY 4.0 for documentation

### Dataset v0
- 50 merged Elasticsearch PRs
- Frozen corpus for reproducibility
- Metadata includes: repo URL, PR number, base/head commits, statistics

### Metrics
- Correctness: Implementation of intended behavior
- Completeness: All requested changes, nothing extra
- Code Reuse: Leveraging existing code vs duplication
- Best Practices: Style, structure, idiomatic usage
- Unsolicited Documentation: Penalty for unrequested docs

[0.1.0]: https://github.com/AugmentedAJ/Long-Context-Code-Bench/releases/tag/v0.1.0

