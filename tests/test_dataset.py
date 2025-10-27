"""Tests for dataset loading and filtering."""

import pytest
from pathlib import Path
from long_context_bench.pipeline import (
    get_dataset_path,
    load_pr_urls,
    filter_pr_urls,
)


def test_get_dataset_path():
    """Test getting dataset path."""
    path = get_dataset_path("v0")
    assert path.exists()
    assert path.name == "elasticsearch_prs_50.json"


def test_load_pr_urls():
    """Test loading PR URLs from built-in dataset."""
    urls = load_pr_urls("v0")
    assert len(urls) == 50
    assert all(url.startswith("https://github.com/elastic/elasticsearch/pull/") for url in urls)


def test_filter_pr_urls_by_numbers():
    """Test filtering PR URLs by PR numbers."""
    urls = load_pr_urls("v0")
    
    # Filter by single PR number
    filtered = filter_pr_urls(urls, pr_numbers="115001")
    assert len(filtered) == 1
    assert "115001" in filtered[0]
    
    # Filter by multiple PR numbers
    filtered = filter_pr_urls(urls, pr_numbers="115001,114998,114995")
    assert len(filtered) == 3
    assert all(any(num in url for num in ["115001", "114998", "114995"]) for url in filtered)


def test_filter_pr_urls_by_indices():
    """Test filtering PR URLs by indices."""
    urls = load_pr_urls("v0")
    
    # Filter by single index
    filtered = filter_pr_urls(urls, pr_indices="0")
    assert len(filtered) == 1
    assert filtered[0] == urls[0]
    
    # Filter by multiple indices
    filtered = filter_pr_urls(urls, pr_indices="0,1,2")
    assert len(filtered) == 3
    assert filtered == urls[0:3]


def test_filter_pr_urls_no_filter():
    """Test that no filter returns all URLs."""
    urls = load_pr_urls("v0")
    filtered = filter_pr_urls(urls)
    assert filtered == urls


def test_filter_pr_urls_invalid_index():
    """Test filtering with out-of-range index."""
    urls = load_pr_urls("v0")
    
    # Index out of range should be skipped
    filtered = filter_pr_urls(urls, pr_indices="0,999")
    assert len(filtered) == 1
    assert filtered[0] == urls[0]

