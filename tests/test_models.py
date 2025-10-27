"""Tests for data models."""

import pytest
from long_context_bench.models import Sample, SampleStats, Edit, Judge, Scores


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
        pr_number=115001,
        base_commit="abc123",
        head_commit="def456",
        task_instructions="Fix bug in search",
        stats=stats,
    )
    
    assert sample.dataset_version == "v0"
    assert sample.pr_number == 115001
    assert sample.stats.files_changed == 5


def test_edit():
    """Test Edit model."""
    edit = Edit(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=115001,
        base_commit="abc123",
        runner="auggie",
        model="claude-sonnet-4",
        timeout_s=1800,
        status="success",
        elapsed_ms=30000,
        patch_unified="diff --git a/file.py b/file.py\n...",
        logs_path="logs.jsonl",
        errors=None,
    )
    
    assert edit.status == "success"
    assert edit.elapsed_ms == 30000
    assert edit.errors is None


def test_scores():
    """Test Scores model."""
    scores = Scores(
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
    )
    
    assert scores.correctness == 0.8
    assert scores.completeness == 0.9
    
    # Test bounds
    with pytest.raises(ValueError):
        Scores(
            correctness=1.5,  # Out of bounds
            completeness=0.9,
            code_reuse=0.7,
            best_practices=0.85,
            unsolicited_docs=1.0,
        )


def test_judge():
    """Test Judge model."""
    scores = Scores(
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
    )
    
    judge = Judge(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=115001,
        base_commit="abc123",
        head_commit="def456",
        judge_mode="deterministic",
        judge_model=None,
        scores=scores,
        aggregate=0.85,
        rationale=None,
    )
    
    assert judge.judge_mode == "deterministic"
    assert judge.aggregate == 0.85
    assert judge.scores.correctness == 0.8

