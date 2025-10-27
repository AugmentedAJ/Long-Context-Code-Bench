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
    task_instructions: str
    stats: SampleStats


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
    errors: Optional[List[str]] = None


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
    judge_mode: str  # deterministic|llm
    judge_model: Optional[str] = None
    scores: Scores
    aggregate: float = Field(ge=-1.0, le=1.0)
    rationale: Optional[str] = None


class RunManifest(BaseModel):
    """Manifest recording full provenance of a benchmark run."""
    dataset_version: str
    harness_version: str
    runner: str
    runner_version: Optional[str] = None
    model: str
    judge_mode: str
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


class AggregateSummary(BaseModel):
    """Aggregate summary statistics across all samples."""
    run_id: str
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
    std_aggregate: float
    mean_elapsed_ms: float
    tasks_per_hour: float

