## RFC-0001: Long-Context-Code-Bench as the Enterprise Standard for AI Coding Agents

Status: Draft
Author: AJ (@techfren)
Date: 2025-10-28

### 1) Summary

I propose to position Long-Context-Code-Bench (LCB) as the industry standard for evaluating AI coding agents in enterprise-scale repositories with 40,000+ files. LCB focuses on real GitHub pull requests (PRs) from massive codebases, measuring whether agents can understand, modify, and safely integrate changes at repository scale. The primary workflow is reproducible, apples-to-apples comparison using test labels across agent runs; leaderboards are supported but are secondary to side-by-side comparisons for decision-making.

### 2) Motivation and Vision

**The Benchmark Marketing Machine Problem**

SWE-bench and Terminal bench have become powerful marketing machines for companies like Augment Code and Factory. Every major model release from OpenAI, Anthropic, Google, and others now prominently features SWE-bench charts showing incremental improvements. T-bench has similarly positioned itself as the go-to benchmark for terminal and systems tasks. These benchmarks have successfully captured mindshare and become the de facto standards that labs optimize for and showcase in their release notes.

However, **these benchmarks don't measure what matters most for enterprise adoption**: the ability to work effectively in massive, real-world codebases with tens of thousands of files. SWE-bench focuses on relatively small Python repositories (typically <5k files) with isolated issues. T-bench evaluates terminal tasks, not repository-scale code editing. Neither benchmark stresses the context engines and retrieval systems that are critical for enterprise-scale development.

**Augment Code's Market Leadership in Large Codebases**

Augment Code is the market leader in handling large codebases. Our context engine and retrieval technology are specifically designed for enterprise-scale repositories with 40,000+ files—the real-world environments where most professional software development happens.

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

### 4) Technical Overview (Current State)

**Repository**: https://github.com/AugmentedAJ/Long-Context-Code-Bench

**Architecture**

The benchmark is built as a Python CLI tool with a staged pipeline architecture:

1. **Sample Stage**: Extracts PR metadata from GitHub and creates sample.json files
   - Stores PR URL, title, body, base commit SHA, head commit SHA
   - No source code stored—only metadata and URLs
   - v0 dataset: 50 PRs from elastic/elasticsearch (~40,000 files)

2. **Edit Stage**: Runs agents on samples and captures their code changes
   - Clones repository at base commit
   - Hides `.git` directory to prevent ground truth leakage
   - Provides PR title + body as instructions to the agent
   - Captures all file changes made by the agent
   - Supports multiple runners: Auggie, Claude Code, Codex CLI, Aider, Generic (stdin-based)
   - Each run gets a unique run ID and manifest with full provenance

3. **Judge Stage**: Evaluates agent edits against ground truth PR diff
   - Five primary metrics: correctness, completeness, code reuse, best practices, unsolicited docs
   - Aggregate score computed from weighted metrics
   - Two judge modes:
     - **Deterministic** (default): Rule-based evaluation using diff analysis
     - **LLM-based**: Uses LiteLLM with seeded temperature for reproducibility
   - Outputs detailed scores per sample and aggregate summary

**Test Labels and Comparison**

- **Test labels**: Optional string labels for grouping runs (e.g., "sonnet-4.5-comparison")
- **Primary workflow**: Run multiple agents with the same test label, then generate comparison reports
- **Comparison formats**:
  - Side-by-side comparison (agents as columns, metrics as rows)
  - Leaderboard (ranked by configurable metric: aggregate score, success rate, tasks/hour, etc.)
- **Export**: CSV and JSON formats for further analysis

**Web Dashboard**

- Node.js web app (not static HTML to avoid CORS issues)
- Reads JSON result files dynamically
- Features:
  - Leaderboard view with rankings
  - Run details and per-sample breakdowns
  - Agent comparison charts
  - Uses Chart.js for visualizations
  - Modern, minimalist, data-dense design

**Current Capabilities**

✅ Fully functional CLI with sample, edit, judge, and pipeline commands
✅ Support for 5 different agent runners
✅ Deterministic and LLM-based judging
✅ Test label system for organizing comparisons
✅ Leaderboard and comparison report generation
✅ CSV/JSON export
✅ Comprehensive test coverage (21 tests passing)
✅ v0 dataset: 50 Elasticsearch PRs (~40k file codebase)

**What's Not Yet Built**

❌ Web dashboard (Node app structure defined but not implemented)
❌ Public leaderboard hosting
❌ Submission API for third-party runs
❌ Multi-repo dataset (v1+)
❌ Automated compile/test validation
❌ CI/CD recipes for cloud runners


### 5) Opportunities

**Market Timing**

The timing is perfect for LCB to become the enterprise standard:

1. **AI coding agents are exploding**: Every major lab (OpenAI, Anthropic, Google, Meta) is investing heavily in coding agents. New models are released every few months with coding improvements as a headline feature.

2. **Enterprise adoption is accelerating**: Companies are moving from experimentation to production deployment of AI coding tools. They need benchmarks that reflect their actual environments (40k+ file codebases).

3. **Benchmark fatigue with SWE-bench**: While SWE-bench is valuable, it's becoming saturated. Labs are hitting 50%+ solve rates on SWE-bench Verified. The community is looking for new, harder, more realistic benchmarks.

4. **Context window wars**: Labs are competing on context window size (100k, 200k, 1M+ tokens). LCB directly measures whether these larger context windows translate to better performance on real-world tasks.

**Strategic Advantages**

1. **First-mover advantage**: No existing benchmark focuses on 40k+ file repositories. We can define the standard before competitors emerge.

2. **Augment's technical moat**: Our context engine and retrieval technology are specifically built for this use case. LCB showcases our core strengths.

3. **Dataset control**: We control the dataset, evaluation criteria, and infrastructure. We can evolve the benchmark to stay relevant and challenging.

4. **Community building**: Open-sourcing the benchmark builds goodwill and positions Augment as a thought leader in enterprise AI coding.

**Revenue and Growth Opportunities**

1. **Enterprise sales**: LCB results become a key part of sales conversations. "Our agent scores X% on LCB, the industry standard for enterprise codebases."

2. **Partnerships with labs**: Co-marketing opportunities with frontier labs when they release new models with LCB results.

3. **Consulting and services**: Help enterprises run LCB on their internal repositories; offer custom benchmark development.

4. **Premium features**: Offer hosted leaderboard, private benchmarks, advanced analytics as paid features.

**Technical and Research Opportunities**

1. **Dataset expansion**: Build v1+ with diverse repos (Java, TypeScript, Go, Rust) to cover more enterprise environments.

2. **New evaluation dimensions**: Add compile/test validation, security checks, performance regression detection.

3. **Academic partnerships**: Collaborate with universities on research papers, workshops, and competitions.

4. **Open source contributions**: Attract community contributions for new runners, datasets, and evaluation methods.

### 6) Weaknesses and Risks

**Technical Risks**

1. **Cost and runtime**: Running agents on 40k+ file repositories is expensive and time-consuming. Each run can take hours and cost $10-50 in API fees.
   - *Mitigation*: Implement aggressive caching, sharding, and concurrency controls. Provide cost estimates upfront.

2. **Non-determinism**: LLM agents are inherently non-deterministic. Same inputs can produce different outputs.
   - *Mitigation*: Emphasize test labels for comparison (not absolute reproducibility). Use deterministic judge by default. Seed LLM judge with temperature 0.

3. **Dataset contamination**: Risk that training data includes our benchmark PRs, inflating scores.
   - *Mitigation*: Document release dates and temporal cutoffs. Use recent PRs. Encourage labs to report training data cutoff dates.

4. **Gaming and overfitting**: Labs might optimize specifically for LCB, reducing its value as a general benchmark.
   - *Mitigation*: Regularly update dataset. Add new repos and tasks. Keep some test sets private.

**Adoption Risks**

1. **Chicken-and-egg problem**: Labs won't care about LCB until it's widely recognized. It won't be widely recognized until labs use it.
   - *Mitigation*: Partner with 2-3 friendly labs early. Get initial results published. Build momentum through marketing.

2. **Complexity barrier**: Running LCB is more complex than SWE-bench (larger repos, longer runtimes, more infrastructure).
   - *Mitigation*: Provide excellent documentation, one-line setup commands, cloud runner recipes, and cost calculators.

3. **Competitive benchmarks**: Other companies might launch competing enterprise-scale benchmarks.
   - *Mitigation*: Move fast. Build community. Establish LCB as the standard before competitors emerge.

**Business Risks**

1. **Resource commitment**: Building and maintaining a benchmark requires ongoing engineering, research, and marketing resources.
   - *Mitigation*: Start lean. Focus on v0 adoption before expanding. Seek community contributions.

2. **Perception risk**: If Augment's own agent doesn't perform well on LCB, it could backfire.
   - *Mitigation*: Ensure Auggie is competitive before public launch. Use LCB internally to drive improvements.

3. **Open source vs. proprietary tension**: Open-sourcing the benchmark means competitors can use it too.
   - *Mitigation*: This is a feature, not a bug. Industry standards must be open. We benefit from being the creator and maintainer.

**Data and Legal Risks**

1. **Licensing and redistribution**: We can't redistribute source code from GitHub repos.
   - *Mitigation*: Store only URLs and metadata. Users clone repos themselves. Clear documentation on licensing.

2. **Privacy and security**: Benchmark runs might expose sensitive patterns or vulnerabilities.
   - *Mitigation*: Clear guidance on what metadata to include in public submissions. Support private benchmarks for enterprises.

### 7) Request for Feedback

I'm seeking feedback on the following questions:

**Strategic Direction**

1. **Is this the right positioning?** Should LCB be "the enterprise standard" or should we position it differently (e.g., "the context engine benchmark", "the large codebase benchmark")?

2. **What's the right launch strategy?** Should we:
   - Launch publicly immediately and build in the open?
   - Partner with 2-3 labs first, get initial results, then launch publicly?
   - Run internal Auggie benchmarks first, optimize performance, then launch?

3. **How aggressive should we be?** Should we directly call out SWE-bench's limitations or take a more collaborative tone?

**Technical Priorities**

4. **What should v1 dataset include?** Which repos and languages should we prioritize?
   - Java monorepos (e.g., Spring Framework, Kafka)?
   - TypeScript/React (e.g., VS Code, Next.js)?
   - Go microservices (e.g., Kubernetes, Docker)?
   - Rust systems (e.g., Servo, Tokio)?

5. **Should we add compile/test validation?** Is diff-based judging sufficient or should we require that changes compile and tests pass?

6. **What's the right balance between deterministic and LLM judging?** Should we default to deterministic, LLM, or offer both equally?

**Go-to-Market**

7. **Which labs should we partner with first?** OpenAI? Anthropic? Google? Meta? Smaller labs?

8. **What's the right timing for public launch?** Should we coordinate with a major model release or launch independently?

9. **How should we handle the web dashboard?** Build it ourselves, partner with a visualization company, or keep it minimal (just CSV/JSON exports)?

**Resource Allocation**

10. **What's the minimum viable team?** How many engineers, researchers, and marketing people do we need to make this successful?

11. **What's the timeline?** Should we aim for public launch in 3 months, 6 months, 12 months?

12. **What are the success criteria?** How do we measure whether LCB is achieving its goals?

**Open Questions**

13. **Am I missing any major risks or opportunities?**

14. **Are there any fatal flaws in this proposal that would prevent LCB from becoming the enterprise standard?**

15. **What would make you excited about this project? What would make you skeptical?**

---

**Please provide feedback by**: [Date TBD]

**Feedback channels**:
- Comment directly on this RFC document
- Slack: #long-context-bench (if channel exists)
- Email: aj47@users.noreply.github.com
- GitHub Issues: https://github.com/AugmentedAJ/Long-Context-Code-Bench/issues

Thank you for your time and input!