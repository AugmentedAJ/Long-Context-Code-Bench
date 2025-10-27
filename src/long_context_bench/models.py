"""Data models for Long-Context-Bench artifacts."""

from typing import Optional

from pydantic import BaseModel, Field


class SampleStats(BaseModel):
    """Statistics about a PR sample."""

    files_changed: int = Field(description="Number of files changed in the PR")
    lines_added: int = Field(description="Number of lines added")
    lines_deleted: int = Field(description="Number of lines deleted")
    total_diff_hunks: int = Field(description="Total number of diff hunks")
    context_size_bytes: int = Field(
        description="Sum of byte sizes of all files touched at base commit"
    )
    truncated: bool = Field(
        description="Whether context_size_bytes was capped at 20MB"
    )


class Sample(BaseModel):
    """A benchmark sample representing a PR task."""

    dataset_version: str = Field(description="Dataset version (e.g., 'v0')")
    repo_url: str = Field(description="GitHub repository URL")
    pr_number: int = Field(description="Pull request number")
    base_commit: str = Field(description="Base commit SHA")
    head_commit: str = Field(description="Head commit SHA (PR tip)")
    task_instructions: str = Field(
        description="Task instructions derived from PR title and body"
    )
    stats: SampleStats = Field(description="Statistics about the PR")


class EditResult(BaseModel):
    """Result of running an agent on a sample."""

    repo_url: str = Field(description="GitHub repository URL")
    pr_number: int = Field(description="Pull request number")
    base_commit: str = Field(description="Base commit SHA")
    runner: str = Field(description="Agent runner name")
    model: str = Field(description="Model name")
    timeout_s: int = Field(description="Timeout in seconds")
    status: str = Field(
        description="Execution status: success, timeout, or error"
    )
    elapsed_ms: int = Field(description="Elapsed time in milliseconds")
    patch_unified: str = Field(
        description="Unified diff produced by the agent (may be empty on failure)"
    )
    logs_path: str = Field(description="Relative path to logs file")
    errors: Optional[list[str]] = Field(
        default=None, description="Error messages if status is error"
    )


class JudgeScores(BaseModel):
    """Scores for the five primary metrics."""

    correctness: float = Field(
        ge=-1.0, le=1.0, description="Does the change implement the intended behavior?"
    )
    completeness: float = Field(
        ge=-1.0,
        le=1.0,
        description="Does it achieve all requested changes and nothing extra?",
    )
    code_reuse: float = Field(
        ge=-1.0,
        le=1.0,
        description="Preference for leveraging existing code over duplication",
    )
    best_practices: float = Field(
        ge=-1.0,
        le=1.0,
        description="Style, structure, and idiomatic usage",
    )
    unsolicited_docs: float = Field(
        ge=-1.0,
        le=1.0,
        description="Penalty for documentation added when not requested",
    )


class JudgeResult(BaseModel):
    """Result of judging an agent's edit."""

    repo_url: str = Field(description="GitHub repository URL")
    pr_number: int = Field(description="Pull request number")
    base_commit: str = Field(description="Base commit SHA")
    head_commit: str = Field(description="Head commit SHA (ground truth)")
    judge_mode: str = Field(description="Judge mode: deterministic or llm")
    judge_model: Optional[str] = Field(
        default=None, description="Judge model (for llm mode)"
    )
    scores: JudgeScores = Field(description="Scores for the five primary metrics")
    aggregate: float = Field(
        ge=-1.0,
        le=1.0,
        description="Aggregate score (unweighted average of five metrics)",
    )
    rationale: Optional[str] = Field(
        default=None, description="Explanation of scores (optional)"
    )


class RunManifest(BaseModel):
    """Manifest recording all provenance for a benchmark run."""

    dataset_version: str
    harness_version: str
    runner: str
    runner_version: Optional[str] = None
    model: str
    judge_mode: str
    judge_model: Optional[str] = None
    os: str
    python_version: str
    git_version: str
    seed: Optional[int] = None
    flags: dict[str, any]
    timestamp_start: str
    timestamp_end: Optional[str] = None
    total_samples: int
    successful_samples: int
    failed_samples: int
    skipped_samples: int


class AggregateSummary(BaseModel):
    """Aggregate summary statistics for a run."""

    total_samples: int
    successful_samples: int
    failed_samples: int
    skipped_samples: int
    success_rate: float
    mean_correctness: float
    mean_completeness: float
    mean_code_reuse: float
    mean_best_practices: float
    mean_unsolicited_docs: float
    mean_aggregate: float
    std_correctness: float
    std_completeness: float
    std_code_reuse: float
    std_best_practices: float
    std_unsolicited_docs: float
    std_aggregate: float
    mean_elapsed_ms: float
    median_elapsed_ms: float
    p95_elapsed_ms: float

