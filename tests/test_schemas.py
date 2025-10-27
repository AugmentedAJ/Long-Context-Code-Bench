"""Tests for schema definitions."""

import pytest
from long_context_bench.schemas import (
    Sample,
    SampleStats,
    Edit,
    Judge,
    Scores,
    get_pr_id,
)


def test_get_pr_id():
    """Test PR ID generation."""
    repo_url = "https://github.com/elastic/elasticsearch"
    pr_number = 12345
    
    pr_id = get_pr_id(repo_url, pr_number)
    assert pr_id == "elastic_elasticsearch_pr12345"
    
    # Test with .git suffix
    repo_url_git = "https://github.com/elastic/elasticsearch.git"
    pr_id_git = get_pr_id(repo_url_git, pr_number)
    assert pr_id_git == "elastic_elasticsearch_pr12345"


def test_sample_stats():
    """Test SampleStats model."""
    stats = SampleStats(
        files_changed=5,
        lines_added=100,
        lines_deleted=50,
        total_diff_hunks=10,
        context_size_bytes=50000,
        truncated=False
    )
    
    assert stats.files_changed == 5
    assert stats.lines_added == 100
    assert stats.lines_deleted == 50
    assert stats.total_diff_hunks == 10
    assert stats.context_size_bytes == 50000
    assert stats.truncated is False


def test_scores_validation():
    """Test Scores validation."""
    # Valid scores
    scores = Scores(
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.5,
        best_practices=0.7,
        unsolicited_docs=-0.2
    )
    assert scores.correctness == 0.8
    
    # Invalid scores (out of range) should raise validation error
    with pytest.raises(Exception):  # Pydantic ValidationError
        Scores(
            correctness=1.5,  # Out of range
            completeness=0.9,
            code_reuse=0.5,
            best_practices=0.7,
            unsolicited_docs=0.0
        )

