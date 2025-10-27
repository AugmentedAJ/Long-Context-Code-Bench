"""Tests for utility functions."""

import pytest

from long_context_bench.utils import (
    compute_shard_assignment,
    get_pr_id,
    truncate_text,
)


def test_get_pr_id():
    """Test PR ID generation."""
    # HTTPS URL
    pr_id = get_pr_id("https://github.com/elastic/elasticsearch", 12345)
    assert pr_id == "elastic_elasticsearch_pr12345"
    
    # HTTPS URL with trailing slash
    pr_id = get_pr_id("https://github.com/elastic/elasticsearch/", 12345)
    assert pr_id == "elastic_elasticsearch_pr12345"
    
    # HTTPS URL with .git suffix
    pr_id = get_pr_id("https://github.com/elastic/elasticsearch.git", 12345)
    assert pr_id == "elastic_elasticsearch_pr12345"
    
    # SSH URL
    pr_id = get_pr_id("git@github.com:elastic/elasticsearch.git", 12345)
    assert pr_id == "elastic_elasticsearch_pr12345"


def test_get_pr_id_invalid():
    """Test PR ID generation with invalid URLs."""
    with pytest.raises(ValueError):
        get_pr_id("invalid-url", 12345)
    
    with pytest.raises(ValueError):
        get_pr_id("https://example.com/repo", 12345)


def test_compute_shard_assignment():
    """Test shard assignment."""
    # Single shard - everything belongs
    assert compute_shard_assignment("test_pr1", 1, 0) is True
    
    # Multiple shards - deterministic assignment
    pr_ids = [f"test_pr{i}" for i in range(100)]
    
    # Each PR should belong to exactly one shard
    for pr_id in pr_ids:
        assignments = [
            compute_shard_assignment(pr_id, 4, i) for i in range(4)
        ]
        assert sum(assignments) == 1, f"PR {pr_id} assigned to multiple shards"
    
    # Distribution should be roughly even
    shard_counts = [0, 0, 0, 0]
    for pr_id in pr_ids:
        for i in range(4):
            if compute_shard_assignment(pr_id, 4, i):
                shard_counts[i] += 1
    
    # Each shard should have between 15 and 35 PRs (roughly 25 ± 10)
    for count in shard_counts:
        assert 15 <= count <= 35, f"Uneven distribution: {shard_counts}"


def test_truncate_text():
    """Test text truncation."""
    # No truncation needed
    text = "Hello, world!"
    assert truncate_text(text, 100) == text
    
    # Truncation needed
    text = "A" * 100
    truncated = truncate_text(text, 50)
    assert len(truncated) == 50
    assert truncated.endswith("[truncated]")
    assert truncated.startswith("A")
    
    # Custom suffix
    truncated = truncate_text(text, 50, suffix="...")
    assert len(truncated) == 50
    assert truncated.endswith("...")


def test_truncate_text_edge_cases():
    """Test text truncation edge cases."""
    # Empty text
    assert truncate_text("", 10) == ""
    
    # Text shorter than suffix
    text = "Hi"
    truncated = truncate_text(text, 5, suffix="[truncated]")
    assert truncated == "[truncated]"
    
    # Max length equals text length
    text = "Hello"
    assert truncate_text(text, 5) == text

