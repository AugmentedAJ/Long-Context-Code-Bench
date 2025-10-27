"""Tests for utility functions."""

import pytest
from long_context_bench.utils import (
    stable_hash,
    get_shard_index,
    truncate_text,
)


def test_stable_hash():
    """Test stable hash generation."""
    repo_url = "https://github.com/elastic/elasticsearch"
    pr_number = 12345
    
    # Hash should be deterministic
    hash1 = stable_hash(repo_url, pr_number)
    hash2 = stable_hash(repo_url, pr_number)
    assert hash1 == hash2
    
    # Different inputs should produce different hashes
    hash3 = stable_hash(repo_url, 54321)
    assert hash1 != hash3


def test_get_shard_index():
    """Test shard index calculation."""
    repo_url = "https://github.com/elastic/elasticsearch"
    pr_number = 12345
    total_shards = 4
    
    # Shard index should be deterministic
    shard1 = get_shard_index(repo_url, pr_number, total_shards)
    shard2 = get_shard_index(repo_url, pr_number, total_shards)
    assert shard1 == shard2
    
    # Shard index should be in valid range
    assert 0 <= shard1 < total_shards


def test_truncate_text():
    """Test text truncation."""
    # Short text should not be truncated
    short_text = "Hello, world!"
    assert truncate_text(short_text, 100) == short_text
    
    # Long text should be truncated
    long_text = "a" * 1000
    truncated = truncate_text(long_text, 100)
    assert len(truncated) == 100 + len("[truncated]")
    assert truncated.endswith("[truncated]")
    
    # Custom marker
    truncated = truncate_text(long_text, 100, marker="...")
    assert truncated.endswith("...")

