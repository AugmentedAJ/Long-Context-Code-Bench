"""Data models for long-context-bench artifacts."""

from typing import Optional, List
from pydantic import BaseModel, Field


class SampleStats(BaseModel):
    """Statistics about a PR sample."""
    files_changed: int
    lines_added: int
    lines_deleted: int
    total_diff_hunks: int
    context_size_bytes: int
    truncated: bool


class Sample(BaseModel):
    """Sample artifact representing a PR task."""
    dataset_version: str
    repo_url: str
    pr_number: int
    base_commit: str
    head_commit: str
    task_instructions: str  # Template-based instructions (PR title + body)
    stats: SampleStats

    # Optional synthesized prompt fields
    synthesized_task_instructions: Optional[str] = None  # LLM-generated natural instructions
    synthesis_model: Optional[str] = None  # Model used for synthesis (e.g., "claude-3-7-sonnet-20250219")
    synthesis_timestamp: Optional[str] = None  # ISO timestamp of synthesis


class Edit(BaseModel):
    """Edit artifact representing agent output."""
    repo_url: str
    pr_number: int
    base_commit: str
    runner: str
    model: str
    timeout_s: int
    status: str  # success|timeout|error
    elapsed_ms: int
    patch_unified: str
    logs_path: str
    errors: List[str] = []
    edit_run_id: str
    test_label: Optional[str] = None  # Optional label for grouping runs for comparison


class Scores(BaseModel):
    """Evaluation scores for a single sample."""
    correctness: float = Field(ge=-1.0, le=1.0)
    completeness: float = Field(ge=-1.0, le=1.0)
    code_reuse: float = Field(ge=-1.0, le=1.0)
    best_practices: float = Field(ge=-1.0, le=1.0)
    unsolicited_docs: float = Field(ge=-1.0, le=1.0)


class Judge(BaseModel):
    """Judge artifact representing evaluation results."""
    repo_url: str
    pr_number: int
    base_commit: str
    head_commit: str
    judge_mode: str = "llm"  # Always 'llm' (kept for backward compatibility)
    judge_model: Optional[str] = None
    scores: Scores
    aggregate: float = Field(ge=-1.0, le=1.0)
    rationale: Optional[str] = None
    edit_run_id: Optional[str] = None  # ID of the edit run being evaluated
    judge_run_id: Optional[str] = None  # ID of the judge run that produced this
    ground_truth_patch: Optional[str] = None  # Ground truth unified diff


class EditRunManifest(BaseModel):
    """Manifest for an edit run (attempt generation)."""
    dataset_version: str
    harness_version: str
    runner: str
    runner_version: Optional[str] = None
    model: str
    os: str
    python_version: str
    timeout_s: int
    concurrency: int
    total_shards: int
    shard_index: int
    flags: dict
    timestamp: str
    edit_run_id: str
    test_label: Optional[str] = None  # Optional label for grouping runs for comparison


class JudgeRunManifest(BaseModel):
    """Manifest for a judge run (evaluation)."""
    harness_version: str
    judge_mode: str = "llm"  # Always 'llm' (kept for backward compatibility)
    judge_model: Optional[str] = None
    edit_run_ids: List[str]  # Edit runs being evaluated
    os: str
    python_version: str
    timestamp: str
    judge_run_id: str
    test_label: Optional[str] = None  # Optional label for grouping runs for comparison


class RunManifest(BaseModel):
    """Manifest recording full provenance of a benchmark run (legacy/pipeline mode)."""
    dataset_version: str
    harness_version: str
    runner: str
    runner_version: Optional[str] = None
    model: str
    judge_mode: Optional[str] = "llm"  # Always 'llm' if judge_model provided (kept for backward compatibility)
    judge_model: Optional[str] = None
    os: str
    python_version: str
    timeout_s: int
    concurrency: int
    total_shards: int
    shard_index: int
    flags: dict
    timestamp: str
    run_id: str
    test_label: Optional[str] = None  # Optional label for grouping runs for comparison


class AggregateSummary(BaseModel):
    """Aggregate summary statistics across all samples."""
    run_id: str
    total_samples: int
    successful_samples: int
    failed_samples: int
    skipped_samples: int
    success_rate: float
    win_rate: float = 0.0  # Fraction of PRs where agent beat human (aggregate > 0)
    mean_correctness: float
    mean_completeness: float
    mean_code_reuse: float
    mean_best_practices: float
    mean_unsolicited_docs: float
    mean_aggregate: float
    std_aggregate: float
    mean_elapsed_ms: float
    tasks_per_hour: float
    edit_run_id: Optional[str] = None  # If this summary is for a specific edit run
    judge_run_id: Optional[str] = None  # If this summary is for a specific judge run
    test_label: Optional[str] = None  # Optional label for grouping runs for comparison
    runner: Optional[str] = None  # Runner name for comparison reports
    model: Optional[str] = None  # Model name for comparison reports


class AgentResult(BaseModel):
    """Individual agent's result for cross-agent comparison."""
    runner: str
    model: str
    edit_run_id: str
    status: str  # success|timeout|error
    elapsed_ms: int
    patch_unified: str
    scores: Scores
    aggregate: float = Field(ge=-1.0, le=1.0)
    rationale: Optional[str] = None
    llm_rating: Optional[float] = Field(None, ge=0.0, le=1.0)  # LLM judge rating 0.00-1.00
    llm_summary: Optional[str] = None  # One-line summary from LLM judge
    errors: List[str] = []
    logs_path: Optional[str] = None  # Relative path to logs.jsonl file


class ComparativeAnalysis(BaseModel):
    """LLM-generated comparative analysis of multiple agents."""
    summary: str  # Overall comparison summary
    best_agent: str  # Which agent performed best (runner:model)
    best_agent_reasoning: str  # Why this agent was best
    approach_differences: str  # Key differences in approaches
    ranking: List[str]  # Ordered list of agents (runner:model) from best to worst


class CrossAgentJudge(BaseModel):
    """Cross-agent comparison results for a single PR."""
    repo_url: str
    pr_number: int
    base_commit: str
    head_commit: str
    task_instructions: str
    ground_truth_diff: str
    judge_mode: str = "llm"  # Always 'llm' (kept for backward compatibility)
    judge_model: Optional[str] = None
    test_label: Optional[str] = None
    agent_results: List[AgentResult]  # Results from each agent
    comparative_analysis: Optional[ComparativeAnalysis] = None  # LLM comparative analysis
    timestamp: str
    analysis_run_id: str  # Unique ID for this cross-agent analysis run




class AgentVsHumanDecision(BaseModel):
    """Individual agent judgment against human ground truth diff.

    This model stores the evaluation of a single agent's submission compared
    to the human diff, with detailed scores for each metric.
    """

    # Identity
    repo_url: str
    pr_number: int
    agent_id: str  # runner:model:edit_run_id
    judge_model: Optional[str] = None  # LLM ID used as judge
    judge_runner: Optional[str] = None  # If a CLI agent acted as judge

    # Scores (all metrics are -1.0 to 1.0)
    correctness: float = Field(ge=-1.0, le=1.0)
    completeness: float = Field(ge=-1.0, le=1.0)
    code_reuse: float = Field(ge=-1.0, le=1.0)
    best_practices: float = Field(ge=-1.0, le=1.0)
    unsolicited_docs: float = Field(ge=-1.0, le=1.0)
    matches_human: float = Field(ge=0.0, le=1.0)  # Overall similarity to human diff

    # Aggregate score (average of the 5 main metrics)
    aggregate: float = Field(ge=-1.0, le=1.0)

    # Explanation
    rationale: Optional[str] = None
    notes: Optional[str] = None  # Short notes about how submission compares to human diff

    # Metadata
    timestamp: str
    codebase_context_files: Optional[List[str]] = None


class PairwiseJudgeDecision(BaseModel):
    """Pairwise head-to-head judgment between two submissions on a PR.

    Submissions are identified by stable agent IDs (e.g. "runner:model:edit_run_id").

    DEPRECATED: This model is kept for backward compatibility but new evaluations
    should use AgentVsHumanDecision instead.
    """

    # Identity
    repo_url: str
    pr_number: int
    submission_a_id: str
    submission_b_id: str
    judge_model: Optional[str] = None  # LLM ID used as judge
    judge_runner: Optional[str] = None  # If a CLI agent acted as judge
    order_seed: Optional[int] = None  # Seed used when randomizing A/B order

    # Verdict
    winner: str  # "A" | "B" | "tie"
    correctness_preference: Optional[str] = None  # "A" | "B" | "tie"
    completeness_preference: Optional[str] = None  # "A" | "B" | "tie"
    code_quality_preference: Optional[str] = None  # "A" | "B" | "tie"
    integration_preference: Optional[str] = None  # "A" | "B" | "tie"
    raw_scores: Optional[dict[str, dict[str, float]]] = None  # Optional per-submission scores
    rationale: Optional[str] = None

    # Optional notes from the judge about how each submission compares to the human diff.
    # Keys are "A" and/or "B"; values are short free-form notes.
    comparison_to_human_notes: Optional[dict[str, str]] = None

    # Metadata
    timestamp: str
    codebase_context_files: Optional[List[str]] = None


class HeadToHeadAgentStats(BaseModel):
    """Per-agent head-to-head stats for a single PR."""

    agent_id: str  # runner:model:edit_run_id
    wins: int
    losses: int
    ties: int


class HeadToHeadPRResult(BaseModel):
    """Head-to-head comparison results for a single PR.

    This model now stores individual agent-vs-human evaluations and derives
    win/loss/tie statistics by comparing agent scores.
    """

    # PR/sample metadata
    repo_url: str
    pr_number: int
    base_commit: str
    head_commit: str
    task_instructions: str
    test_label: Optional[str] = None

    # Per-agent results and individual judgments against human
    agent_results: List[AgentResult]
    agent_decisions: List[AgentVsHumanDecision]  # Individual agent-vs-human evaluations
    agent_stats: List[HeadToHeadAgentStats]  # Win/loss/tie derived from score comparisons

    # Deprecated: kept for backward compatibility with old data
    pairwise_decisions: Optional[List[PairwiseJudgeDecision]] = None

    # Run metadata
    head_to_head_run_id: str
    timestamp: str


class HeadToHeadAgentSummary(BaseModel):
    """Cross-PR head-to-head summary for a single agent."""

    agent_id: str  # runner:model[:edit_run_id] identifier used in comparisons
    runner: str
    model: str
    test_label: Optional[str] = None

    wins: int
    losses: int
    ties: int
    matches: int
    win_rate: float

    elo_rating: float
    elo_uncertainty: Optional[float] = None


class HeadToHeadGlobalSummary(BaseModel):
    """Global head-to-head summary across PRs for a test label."""

    test_label: Optional[str] = None
    agents: List[HeadToHeadAgentSummary]
    # Optional nested matrix: [agent_id][opponent_id] -> {wins, losses, ties}
    head_to_head_matrix: Optional[dict[str, dict[str, dict[str, int]]]] = None
