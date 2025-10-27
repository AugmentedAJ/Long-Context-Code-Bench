"""Common utilities for the benchmark."""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def stable_hash(repo_url: str, pr_number: int) -> int:
    """Generate a stable hash for sharding.
    
    Args:
        repo_url: Repository URL
        pr_number: PR number
        
    Returns:
        Integer hash value
    """
    key = f"{repo_url}:{pr_number}"
    return int(hashlib.sha256(key.encode()).hexdigest(), 16)


def get_shard_index(repo_url: str, pr_number: int, total_shards: int) -> int:
    """Determine which shard a PR belongs to.
    
    Args:
        repo_url: Repository URL
        pr_number: PR number
        total_shards: Total number of shards
        
    Returns:
        Shard index (0-based)
    """
    return stable_hash(repo_url, pr_number) % total_shards


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON from file.
    
    Args:
        path: Path to JSON file
        
    Returns:
        Parsed JSON data
    """
    with open(path, 'r') as f:
        return json.load(f)


def save_json(data: Any, path: Path, indent: int = 2) -> None:
    """Save data to JSON file.
    
    Args:
        data: Data to save (must be JSON serializable)
        path: Path to save to
        indent: JSON indentation level
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=indent, default=str)


def truncate_text(text: str, max_length: int, marker: str = "[truncated]") -> str:
    """Truncate text to maximum length with marker.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        marker: Truncation marker to append
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + marker


def retry_with_backoff(
    func,
    max_retries: int = 2,
    backoff_base: float = 2.0,
    jitter: float = 0.1,
    retryable_exceptions: tuple = (Exception,)
):
    """Retry a function with exponential backoff and jitter.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retries
        backoff_base: Base for exponential backoff
        jitter: Jitter factor (±percentage)
        retryable_exceptions: Tuple of exceptions to retry on
        
    Returns:
        Function result
        
    Raises:
        Last exception if all retries fail
    """
    import random
    
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return func()
        except retryable_exceptions as e:
            last_exception = e
            if attempt < max_retries:
                # Calculate backoff with jitter
                backoff = backoff_base ** attempt
                jitter_amount = backoff * jitter * (2 * random.random() - 1)
                sleep_time = backoff + jitter_amount
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {sleep_time:.2f}s..."
                )
                time.sleep(sleep_time)
            else:
                logger.error(f"All {max_retries + 1} attempts failed")
    
    raise last_exception


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

