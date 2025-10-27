"""JSON schemas and data models for the benchmark."""

from typing import Optional
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
    errors: Optional[list[str]] = None


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
    aggregate: float
    rationale: Optional[str] = None


class RunManifest(BaseModel):
    """Manifest recording all run metadata for reproducibility."""
    
    dataset_version: str
    harness_version: str
    runner: str
    runner_version: Optional[str] = None
    model: str
    judge_mode: str
    judge_model: Optional[str] = None
    os: str
    python_version: str
    flags: dict[str, any]
    timestamp: str
    total_samples: int
    successful_samples: int
    failed_samples: int
    skipped_samples: int


def get_pr_id(repo_url: str, pr_number: int) -> str:
    """Generate a stable PR identifier from repo URL and PR number.
    
    Args:
        repo_url: GitHub repository URL
        pr_number: Pull request number
        
    Returns:
        PR identifier in format: owner_repo_pr{number}
    """
    # Extract owner and repo from URL
    # e.g., https://github.com/elastic/elasticsearch -> elastic_elasticsearch
    parts = repo_url.rstrip('/').split('/')
    owner = parts[-2]
    repo = parts[-1].replace('.git', '')
    return f"{owner}_{repo}_pr{pr_number}"

