"""Utility functions for Long-Context-Bench."""

import hashlib
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Optional

import git
from rich.console import Console
from rich.logging import RichHandler

console = Console()


def setup_logging(verbose: bool = False, quiet: bool = False) -> logging.Logger:
    """Set up logging with rich formatting."""
    level = logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )
    
    return logging.getLogger("long_context_bench")


def get_pr_id(repo_url: str, pr_number: int) -> str:
    """Generate a stable PR ID from repo URL and PR number.
    
    Format: {owner}_{repo}_pr{number}
    Example: elastic_elasticsearch_pr12345
    """
    # Extract owner and repo from URL
    # Handle both https://github.com/owner/repo and git@github.com:owner/repo.git
    if "github.com/" in repo_url:
        parts = repo_url.split("github.com/")[1].rstrip("/").rstrip(".git").split("/")
    elif "github.com:" in repo_url:
        parts = repo_url.split("github.com:")[1].rstrip(".git").split("/")
    else:
        raise ValueError(f"Invalid GitHub URL: {repo_url}")
    
    if len(parts) < 2:
        raise ValueError(f"Invalid GitHub URL format: {repo_url}")
    
    owner, repo = parts[0], parts[1]
    return f"{owner}_{repo}_pr{pr_number}"


def compute_shard_assignment(
    pr_id: str, total_shards: int, shard_index: int
) -> bool:
    """Determine if a PR belongs to a given shard using stable hashing.
    
    Args:
        pr_id: PR identifier
        total_shards: Total number of shards
        shard_index: Current shard index (0-based)
        
    Returns:
        True if the PR belongs to this shard
    """
    if total_shards == 1:
        return True
    
    # Use SHA256 for stable hashing
    hash_bytes = hashlib.sha256(pr_id.encode()).digest()
    hash_int = int.from_bytes(hash_bytes[:8], byteorder="big")
    assigned_shard = hash_int % total_shards
    
    return assigned_shard == shard_index


def save_json(data: Any, path: Path, pretty: bool = True) -> None:
    """Save data to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w") as f:
        if pretty:
            json.dump(data, f, indent=2, sort_keys=True)
        else:
            json.dump(data, f)


def load_json(path: Path) -> Any:
    """Load data from JSON file."""
    with open(path, "r") as f:
        return json.load(f)


def run_git_command(
    args: list[str],
    cwd: Optional[Path] = None,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    cmd = ["git"] + args
    
    result = subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=capture_output,
        text=True,
    )
    
    return result


def clone_repo(
    repo_url: str,
    target_dir: Path,
    commit: Optional[str] = None,
    depth: Optional[int] = None,
) -> git.Repo:
    """Clone a repository and optionally checkout a specific commit.
    
    Args:
        repo_url: Repository URL
        target_dir: Target directory for clone
        commit: Optional commit to checkout
        depth: Optional depth for shallow clone
        
    Returns:
        GitPython Repo object
    """
    clone_args = {}
    if depth:
        clone_args["depth"] = depth
    
    repo = git.Repo.clone_from(repo_url, target_dir, **clone_args)
    
    if commit:
        # Fetch the specific commit if it's not available
        try:
            repo.git.checkout(commit)
        except git.GitCommandError:
            # Commit might not be in shallow clone, fetch it
            repo.git.fetch("origin", commit, depth=1)
            repo.git.checkout(commit)
    
    return repo


def get_unified_diff(repo: git.Repo, base: str, head: str) -> str:
    """Get unified diff between two commits.
    
    Args:
        repo: GitPython Repo object
        base: Base commit SHA
        head: Head commit SHA
        
    Returns:
        Unified diff as string
    """
    return repo.git.diff(base, head, unified=3)


def get_file_list_at_commit(repo: git.Repo, commit: str) -> list[str]:
    """Get list of all files at a specific commit.
    
    Args:
        repo: GitPython Repo object
        commit: Commit SHA
        
    Returns:
        List of file paths
    """
    return repo.git.ls_tree("-r", "--name-only", commit).splitlines()


def get_file_size_at_commit(
    repo: git.Repo, commit: str, file_path: str
) -> int:
    """Get size of a file at a specific commit.
    
    Args:
        repo: GitPython Repo object
        commit: Commit SHA
        file_path: Path to file
        
    Returns:
        File size in bytes
    """
    try:
        blob = repo.git.cat_file("-s", f"{commit}:{file_path}")
        return int(blob)
    except git.GitCommandError:
        return 0


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_env_var(name: str, required: bool = False) -> Optional[str]:
    """Get environment variable with optional requirement check."""
    value = os.getenv(name)
    
    if required and not value:
        raise ValueError(f"Required environment variable {name} is not set")
    
    return value


def truncate_text(text: str, max_length: int, suffix: str = "[truncated]") -> str:
    """Truncate text to maximum length with suffix."""
    if len(text) <= max_length:
        return text
    
    return text[: max_length - len(suffix)] + suffix


def format_elapsed_time(ms: int) -> str:
    """Format elapsed time in milliseconds to human-readable string."""
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    elif ms < 3600000:
        return f"{ms / 60000:.1f}m"
    else:
        return f"{ms / 3600000:.1f}h"

