"""Tests for data models."""

import pytest
from pydantic import ValidationError

from long_context_bench.models import (
    EditResult,
    JudgeResult,
    JudgeScores,
    Sample,
    SampleStats,
)


def test_sample_stats():
    """Test SampleStats model."""
    stats = SampleStats(
        files_changed=5,
        lines_added=100,
        lines_deleted=50,
        total_diff_hunks=10,
        context_size_bytes=10000,
        truncated=False,
    )
    
    assert stats.files_changed == 5
    assert stats.lines_added == 100
    assert stats.lines_deleted == 50
    assert stats.total_diff_hunks == 10
    assert stats.context_size_bytes == 10000
    assert stats.truncated is False


def test_sample():
    """Test Sample model."""
    stats = SampleStats(
        files_changed=5,
        lines_added=100,
        lines_deleted=50,
        total_diff_hunks=10,
        context_size_bytes=10000,
        truncated=False,
    )
    
    sample = Sample(
        dataset_version="v0",
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=12345,
        base_commit="abc123",
        head_commit="def456",
        task_instructions="Fix bug in search",
        stats=stats,
    )
    
    assert sample.dataset_version == "v0"
    assert sample.repo_url == "https://github.com/elastic/elasticsearch"
    assert sample.pr_number == 12345
    assert sample.base_commit == "abc123"
    assert sample.head_commit == "def456"
    assert sample.task_instructions == "Fix bug in search"
    assert sample.stats == stats


def test_edit_result():
    """Test EditResult model."""
    result = EditResult(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=12345,
        base_commit="abc123",
        runner="auggie",
        model="claude-sonnet-4",
        timeout_s=1800,
        status="success",
        elapsed_ms=5000,
        patch_unified="diff --git a/file.py b/file.py\n...",
        logs_path="logs.jsonl",
        errors=None,
    )
    
    assert result.status == "success"
    assert result.elapsed_ms == 5000
    assert result.errors is None


def test_edit_result_with_errors():
    """Test EditResult model with errors."""
    result = EditResult(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=12345,
        base_commit="abc123",
        runner="auggie",
        model="claude-sonnet-4",
        timeout_s=1800,
        status="error",
        elapsed_ms=1000,
        patch_unified="",
        logs_path="logs.jsonl",
        errors=["Connection timeout", "Failed to connect"],
    )
    
    assert result.status == "error"
    assert len(result.errors) == 2


def test_judge_scores():
    """Test JudgeScores model."""
    scores = JudgeScores(
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
    )
    
    assert scores.correctness == 0.8
    assert scores.completeness == 0.9
    assert scores.code_reuse == 0.7
    assert scores.best_practices == 0.85
    assert scores.unsolicited_docs == 1.0


def test_judge_scores_validation():
    """Test JudgeScores validation."""
    # Scores must be in range [-1.0, 1.0]
    with pytest.raises(ValidationError):
        JudgeScores(
            correctness=1.5,  # Invalid: > 1.0
            completeness=0.9,
            code_reuse=0.7,
            best_practices=0.85,
            unsolicited_docs=1.0,
        )
    
    with pytest.raises(ValidationError):
        JudgeScores(
            correctness=0.8,
            completeness=-1.5,  # Invalid: < -1.0
            code_reuse=0.7,
            best_practices=0.85,
            unsolicited_docs=1.0,
        )


def test_judge_result():
    """Test JudgeResult model."""
    scores = JudgeScores(
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
    )
    
    result = JudgeResult(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=12345,
        base_commit="abc123",
        head_commit="def456",
        judge_mode="deterministic",
        judge_model=None,
        scores=scores,
        aggregate=0.85,
        rationale=None,
    )
    
    assert result.judge_mode == "deterministic"
    assert result.judge_model is None
    assert result.aggregate == 0.85
    assert result.rationale is None


def test_judge_result_with_llm():
    """Test JudgeResult model with LLM judge."""
    scores = JudgeScores(
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
    )
    
    result = JudgeResult(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=12345,
        base_commit="abc123",
        head_commit="def456",
        judge_mode="llm",
        judge_model="gpt-4",
        scores=scores,
        aggregate=0.85,
        rationale="The implementation is correct and follows best practices.",
    )
    
    assert result.judge_mode == "llm"
    assert result.judge_model == "gpt-4"
    assert result.rationale is not None

