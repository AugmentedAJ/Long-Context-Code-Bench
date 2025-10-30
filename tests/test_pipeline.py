"""Tests for pipeline utilities."""

import pytest
from long_context_bench.pipeline import compute_shard_hash, should_process_in_shard, _run_single_agent


def test_compute_shard_hash():
    """Test shard hash computation."""
    hash1 = compute_shard_hash("https://github.com/elastic/elasticsearch", 115001)
    hash2 = compute_shard_hash("https://github.com/elastic/elasticsearch", 115001)
    hash3 = compute_shard_hash("https://github.com/elastic/elasticsearch", 115002)
    
    # Same inputs should produce same hash
    assert hash1 == hash2
    
    # Different inputs should produce different hash
    assert hash1 != hash3


def test_should_process_in_shard():
    """Test shard assignment."""
    repo_url = "https://github.com/elastic/elasticsearch"
    
    # Single shard should process everything
    assert should_process_in_shard(repo_url, 115001, 1, 0) is True
    
    # Multiple shards should partition
    total_shards = 4
    pr_numbers = list(range(115001, 115051))
    
    # Each PR should be assigned to exactly one shard
    for pr_number in pr_numbers:
        assigned_shards = [
            shard for shard in range(total_shards)
            if should_process_in_shard(repo_url, pr_number, total_shards, shard)
        ]
        assert len(assigned_shards) == 1
    
    # Distribution should be relatively even
    shard_counts = [0] * total_shards
    for pr_number in pr_numbers:
        for shard in range(total_shards):
            if should_process_in_shard(repo_url, pr_number, total_shards, shard):
                shard_counts[shard] += 1
    
    # Each shard should have at least some PRs
    assert all(count > 0 for count in shard_counts)
    
    # No shard should have more than 2x the average
    avg = len(pr_numbers) / total_shards
    assert all(count < 2 * avg for count in shard_counts)


def test_agent_config_parsing():
    """Test agent configuration parsing for parallel execution."""
    # Test single agent config
    agent_configs = [{
        "runner": "auggie",
        "model": "claude-sonnet-4.5",
    }]
    assert len(agent_configs) == 1
    assert agent_configs[0]["runner"] == "auggie"
    assert agent_configs[0]["model"] == "claude-sonnet-4.5"

    # Test multiple agent configs
    agent_configs = [
        {"runner": "auggie", "model": "claude-sonnet-4.5"},
        {"runner": "claude-code", "model": "claude-sonnet-4.5"},
    ]
    assert len(agent_configs) == 2
    assert agent_configs[0]["runner"] == "auggie"
    assert agent_configs[1]["runner"] == "claude-code"

    # Test with custom binary
    agent_configs = [{
        "runner": "auggie",
        "model": "claude-sonnet-4.5",
        "agent_binary": "/usr/local/bin/auggie",
    }]
    assert agent_configs[0]["agent_binary"] == "/usr/local/bin/auggie"

