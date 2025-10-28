## RFC-0001: Long-Context-Code-Bench as the Enterprise Standard for AI Coding Agents

Status: Draft
Author: AJ (@techfren)
Date: 2025-10-28
Reviewers: Engineering Lead, Research, Product

### 1) Summary

I propose to position Long-Context-Code-Bench (LCB) as the industry standard for evaluating AI coding agents in enterprise-scale repositories with 40,000+ files. LCB focuses on real GitHub pull requests (PRs) from massive codebases, measuring whether agents can understand, modify, and safely integrate changes at repository scale. The primary workflow is reproducible, apples-to-apples comparison using test labels across agent runs; leaderboards are supported but are secondary to side-by-side comparisons for decision-making.

### 2) Motivation and Vision

**The Benchmark Marketing Machine Problem**

SWE-bench and T-bench have become powerful marketing machines for frontier AI labs. Every major model release from OpenAI, Anthropic, Google, and others now prominently features SWE-bench charts showing incremental improvements. T-bench has similarly positioned itself as the go-to benchmark for terminal and systems tasks. These benchmarks have successfully captured mindshare and become the de facto standards that labs optimize for and showcase in their release notes.

However, **these benchmarks don't measure what matters most for enterprise adoption**: the ability to work effectively in massive, real-world codebases with tens of thousands of files. SWE-bench focuses on relatively small Python repositories (typically <5k files) with isolated issues. T-bench evaluates terminal tasks, not repository-scale code editing. Neither benchmark stresses the context engines and retrieval systems that are critical for enterprise-scale development.

**Augment Code's Market Leadership in Large Codebases**

Augment Code is the market leader in handling large codebases. Our context engine and retrieval technology are specifically designed for enterprise-scale repositories with 40,000+ files—the real-world environments where most professional software development happens. We have:

- **Proprietary context engine**: World-class retrieval and embedding models optimized for massive repositories
- **Real-time indexing**: Maintains up-to-date understanding across tens of thousands of files
- **Enterprise customers**: Proven track record with companies running large monorepos and mission-critical services
- **Multi-language support**: Handles polyglot codebases that span multiple languages and frameworks

**The Opportunity**

There is currently **no industry-standard benchmark** that measures agent performance on enterprise-scale repositories. This is our opportunity to:

1. **Define the standard** for evaluating AI coding agents in the environments that matter most to enterprises
2. **Showcase Augment's strengths** by creating a benchmark that measures the capabilities we excel at
3. **Become the benchmark** that frontier labs include in their model releases, just as they do with SWE-bench
4. **Drive awareness** of Augment Code's leadership in large codebase understanding

When labs release new models, they should include LCB results and charts (via our web dashboard) to demonstrate enterprise readiness. Just as SWE-bench has become synonymous with coding agent evaluation, LCB should become synonymous with enterprise-scale code understanding.

**Why This Matters**

- Enterprises run on large, multi-language monorepos and mission-critical services with 40,000+ files
- Improving agent performance in these environments directly impacts productivity and quality at scale
- Existing benchmarks are valuable but don't measure repository-scale context understanding and safe editing against realistic PRs with strict provenance and workspace isolation
- We have the technical capability and market position to set this standard

### 3) What LCB Measures (Differentiators)

- **Repository scale**: Evaluates agents on PR tasks drawn from massive, real-world repos with **40,000+ files** (v0: 50 Elasticsearch PRs from a ~40k file codebase; future: multi-repo, multi-language).
- **Context engine stress**: Focuses on agents’ ability to locate, reason about, and modify code across tens of thousands of files without leaking ground truth. This is where Augment Code's proprietary context engine excels.
- **Realistic tasks**: Uses actual PR intent (title + body) as instructions; no handcrafted prompts, no training-time exposure to the PR diff.
- **Strict isolation**: Workspaces materialized at the base commit; `.git` hidden during editing; ground-truth diff computed locally for judging.
- **Reproducible judging**: Deterministic judge baseline plus optional LLM judge (seeded) with full provenance; comparisons organized by test labels.
- **Agent-agnostic harness**: Pluggable runners (Auggie, Claude Code, Codex CLI, Aider, Generic) with a uniform contract.

### 4) Competitive Landscape (selected)

**SWE-bench (and SWE-bench Verified)**
- Real GitHub issues across 12 Python repos; Verified subset (500) is human-validated for solvability
- **Repository size**: Typically <5k files per repo (e.g., django, flask, requests)
- **Strength**: Excellent issue-resolution benchmark with strong adoption by frontier labs
- **Gap**: Not focused on repository-scale PR editing (40k+ files) or isolation constraints for enterprise settings
- Links: https://github.com/SWE-bench/SWE-bench • https://www.swebench.com/

**Terminal-Bench (T-bench)**
- Evaluates agent capability on diverse terminal tasks end-to-end
- **Strength**: Great for systems/prod tasks; strong marketing presence
- **Gap**: Orthogonal to repository-scale PR editing and code understanding
- Link: https://www.tbench.ai/

**LiveCodeBench**
- Contamination-aware, continuously updated coding tasks
- **Strength**: Strong stance on temporal integrity
- **Gap**: Not directly repo-scale PR editing
- Link: https://arxiv.org/abs/2403.07974

**RepoBench**
- Repository-level code auto-completion
- **Gap**: Focuses on completion rather than end-to-end PR editing and judging
- Links: https://arxiv.org/abs/2306.03091 • https://github.com/Leolty/repobench

**CodeRAG-Bench**
- Retrieval-augmented code generation tasks across heterogeneous sources
- **Gap**: Adjacent but not PR-edit centric
- Link: https://code-rag-bench.github.io/

**LCB's Unique Position**: None of these benchmarks directly target enterprise repo editing at scale (40k+ files) or emphasize context engine performance in massive codebases. This is the gap LCB fills and where Augment Code's technology leadership shines.

### 5) Users and Primary Scenarios

- Model labs: Publish LCB comparison charts in release notes; track regressions/improvements by model and agent variants.
- Enterprise engineering leaders: Compare agents under realistic constraints before pilot/rollout; run staged evaluations on internal repos.
- Researchers: Study retrieval, context windows, and agent tool-use under repository-scale constraints.

Primary workflow: test-label comparison. Teams run multiple agents/models with the same test label, judge them deterministically (or with a seeded LLM judge), and review side-by-side comparisons in the web dashboard.

### 6) Technical Overview (current state)

- **Dataset v0**: 50 PRs from elastic/elasticsearch (~40,000 files) (frozen). Artifacts store URLs and metadata only.
- **Pipeline**: sample → edit → judge (staged or pipeline mode). Full provenance via run manifests; caching and sharding supported.
- **Runners**: Adapters for Auggie, Claude Code, Codex CLI, Aider, and a Generic stdin-based runner.
- **Judging**: Five primary metrics (correctness, completeness, code reuse, best practices, unsolicited docs), aggregate score; deterministic baseline and optional seeded LLM judge (via LiteLLM).
- **Web dashboard**: Node-based web app reading JSON outputs for leaderboards, run details, and agent comparisons.
- **Test labels**: Organize runs for apples-to-apples comparison; primary workflow for reproducible evaluation.

### 7) Enterprise Readiness Requirements (roadmap highlights)

- **Dataset scale-out**: v1+ to expand beyond a single repository (multi-repo, multi-language, all 40k+ files), with semantic versioning and changelogs. Target diverse enterprise environments: Java monorepos, TypeScript/React frontends, Go microservices, etc.
- **Submission API and Leaderboard governance**: Documented format and validation for third-party submissions; lightweight review and anti-gaming checks. Make it easy for labs to submit runs and get featured on the leaderboard.
- **Strong contamination posture**: Document release dates, temporal cutoffs, and suggested practices for labs; guidance for internal enterprise datasets.
- **Expanded metrics**: Add safety/regression checks (e.g., tests pass/fail if available), compile/build checks, and repo policy adherence.
- **CI/Cloud recipes**: Reference GitHub Actions and cloud runners; cost-aware sharding and concurrency; resumable runs.
- **Agent capability flags**: Standardize flags for retrieval/shell/tools to enable fair comparisons across agents.
- **Security and privacy**: Clear guidance on tokens, network access, and artifact hygiene; reinforce no redistribution of source blobs.

### 8) Go-To-Market (GTM) and Community

**Phase 1: Establish the Standard (Months 1-3)**
- **Labs partnership program**: Reach out to OpenAI, Anthropic, Google, and other frontier labs. Co-design initial public comparisons; ensure LCB charts appear in their next model release notes alongside SWE-bench.
- **Public leaderboard launch**: Maintain a public leaderboard with curated, reproducible runs; highlight comparison runs organized by test label (primary scenario). Make it visually compelling and shareable.
- **Positioning**: "The Enterprise Standard for AI Coding Agents" - emphasize 40k+ file codebases, context engine performance, and Augment's leadership.

**Phase 2: Build Momentum (Months 4-6)**
- **Academic/industry presence**: Publish a whitepaper/tech report; submit to relevant venues (NeurIPS, ICML, ICLR workshops); release periodic benchmark reports showing trends.
- **Community contributions**: Accept new runners, datasets, and evaluators via RFCs; document adapter conformance tests.
- **Media and awareness**: Blog posts, conference talks, social media campaigns highlighting how LCB measures what SWE-bench doesn't.

**Phase 3: Ecosystem Growth (Months 7-12)**
- **Third-party submissions**: Open submission API for labs and researchers to submit runs
- **Enterprise adoption**: Work with 5-10 enterprise customers to run LCB on their internal repos
- **Benchmark reports**: Quarterly "State of AI Coding Agents" reports showing performance trends across models and agents

### 9) Success Metrics

**Market Adoption (Primary)**
- **Model release inclusion**: # of frontier lab model releases citing LCB charts (target: 3+ labs within 6 months)
- **Leaderboard submissions**: # of labs regularly submitting runs (target: 5+ labs within 12 months)
- **Enterprise pilots**: # of enterprises running LCB on internal repos (target: 10+ within 12 months)
- **Media mentions**: # of articles, blog posts, and social media mentions positioning LCB as the enterprise standard

**Benchmark Usage**
- Monthly unique runs; # of comparison runs (test labels) created; web dashboard views
- GitHub stars, forks, and community contributions

**Technical Outcomes**
- Reduction in edit timeouts; improvement in aggregate scores over time; variance reduction between reruns
- Diversity of repos in dataset (target: 10+ repos with 40k+ files by v2)

### 10) Risks and Mitigations

- Adoption risk: Provide easy on-ramps (built-in dataset, one-line pipeline, web dashboard). Partner early with 2–3 labs for launch.
- Cost/time risk: Sharding, concurrency controls, resumable runs, and caching to control runtime and spend.
- Non-determinism: Treat comparison as primary; deterministic judge by default; LLM judge seeded with temperature 0.
- Data/licensing: Distribute URLs/metadata only; enforce guidance not to republish code artifacts.

### 11) Open Questions for Review

- **Dataset expansion**: What additional enterprise repos with 40k+ files should be prioritized for v1? Target language diversity (Java, TypeScript, Go, Rust), build systems, test suites.
- **Validation steps**: Do we require an automated compile/test step for some repos to complement diff-based judging?
- **Submission process**: What external submission/verification process is acceptable (fully automated vs. curated)? How do we prevent gaming?
- **Leaderboard transparency**: What is the minimal metadata to include in public leaderboards to balance transparency and privacy/security?
- **Lab partnerships**: Which 2-3 frontier labs should we prioritize for initial partnerships? OpenAI, Anthropic, Google?
- **Timing**: When should we launch the public leaderboard to maximize impact? Coordinate with a major model release?

### 12) References (selected)

- SWE-bench: https://github.com/SWE-bench/SWE-bench • Leaderboard: https://www.swebench.com/
- SWE-bench Verified: https://openai.com/index/introducing-swe-bench-verified/ • HF dataset: https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified
- Terminal-Bench: https://www.tbench.ai/
- LiveCodeBench (paper): https://arxiv.org/abs/2403.07974
- RepoBench: https://arxiv.org/abs/2306.03091 • Code: https://github.com/Leolty/repobench
- CodeRAG-Bench: https://code-rag-bench.github.io/

---

Appendix A: Alignment with current PRD
- Primary flow (sample → edit → judge) with provenance and determinism is already implemented (see prd.md).
- Test-label comparison is supported and will be presented as the primary evaluation mode in docs.
- Web dashboard is already a Node app that reads JSON results; we will continue to invest here for shareable charts.

