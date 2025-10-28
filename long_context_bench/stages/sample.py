"""Sample stage: Extract PR metadata and create sample.json files."""

import json
import re
import tempfile
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse

import git
import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from long_context_bench.models import Sample, SampleStats

console = Console()


def parse_pr_url(url: str) -> tuple[str, str, int]:
    """Parse GitHub PR URL into owner, repo, and PR number.
    
    Args:
        url: GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)
        
    Returns:
        Tuple of (owner, repo, pr_number)
    """
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", url)
    if not match:
        raise ValueError(f"Invalid GitHub PR URL: {url}")
    owner, repo, pr_num = match.groups()
    return owner, repo, int(pr_num)


def get_pr_id(owner: str, repo: str, pr_number: int) -> str:
    """Generate PR ID for file naming.
    
    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        
    Returns:
        PR ID string (e.g., "elastic_elasticsearch_pr115001")
    """
    return f"{owner}_{repo}_pr{pr_number}"


def fetch_pr_metadata(
    owner: str, repo: str, pr_number: int, github_token: Optional[str] = None
) -> dict:
    """Fetch PR metadata from GitHub API.
    
    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number
        github_token: Optional GitHub token for authentication
        
    Returns:
        PR metadata dictionary
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def create_task_instructions(pr_metadata: dict) -> str:
    """Create task instructions from PR metadata.
    
    Per R-3.4: Use PR title followed by PR body, truncated to 10,000 characters.
    
    Args:
        pr_metadata: PR metadata from GitHub API
        
    Returns:
        Task instructions string
    """
    title = pr_metadata.get("title", "")
    body = pr_metadata.get("body") or ""
    
    instructions = f"{title}\n\n{body}"
    
    if len(instructions) > 10000:
        instructions = instructions[:10000] + "\n[truncated]"
    
    return instructions


def compute_diff_stats(repo: git.Repo, base_commit: str, head_commit: str) -> tuple[int, int, int, int]:
    """Compute diff statistics between two commits.
    
    Args:
        repo: Git repository
        base_commit: Base commit hash
        head_commit: Head commit hash
        
    Returns:
        Tuple of (files_changed, lines_added, lines_deleted, total_diff_hunks)
    """
    diff = repo.git.diff(base_commit, head_commit, numstat=True)
    
    files_changed = 0
    lines_added = 0
    lines_deleted = 0
    
    for line in diff.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            try:
                added = int(parts[0]) if parts[0] != "-" else 0
                deleted = int(parts[1]) if parts[1] != "-" else 0
                lines_added += added
                lines_deleted += deleted
                files_changed += 1
            except ValueError:
                continue
    
    # Count diff hunks
    unified_diff = repo.git.diff(base_commit, head_commit)
    total_diff_hunks = unified_diff.count("@@")
    
    return files_changed, lines_added, lines_deleted, total_diff_hunks


def compute_context_size(repo: git.Repo, base_commit: str, head_commit: str) -> tuple[int, bool]:
    """Compute context size (sum of file sizes at base commit).
    
    Per R-2.9: Sum of byte sizes of all files touched, capped at 20 MB.
    
    Args:
        repo: Git repository
        base_commit: Base commit hash
        head_commit: Head commit hash
        
    Returns:
        Tuple of (context_size_bytes, truncated)
    """
    # Get list of changed files
    diff_files = repo.git.diff(base_commit, head_commit, name_only=True).split("\n")
    
    total_size = 0
    max_size = 20 * 1024 * 1024  # 20 MB
    truncated = False
    
    repo.git.checkout(base_commit)
    
    for file_path in diff_files:
        if not file_path.strip():
            continue
        try:
            file_full_path = Path(repo.working_dir) / file_path
            if file_full_path.exists() and file_full_path.is_file():
                size = file_full_path.stat().st_size
                if total_size + size > max_size:
                    truncated = True
                    break
                total_size += size
        except Exception:
            continue
    
    return min(total_size, max_size), truncated


def get_or_clone_repo(repo_url: str, cache_dir: Optional[Path] = None) -> git.Repo:
    """Get repository from cache or clone it.

    Args:
        repo_url: Repository URL
        cache_dir: Optional cache directory for repositories

    Returns:
        Git repository object
    """
    if cache_dir:
        # Extract repo name from URL
        repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        owner = repo_url.rstrip("/").split("/")[-2]
        cache_path = cache_dir / f"{owner}_{repo_name}"

        if cache_path.exists():
            console.print(f"  Using cached repository at {cache_path}")
            repo = git.Repo(cache_path)
            # Fetch latest changes
            try:
                repo.git.fetch("--all")
            except Exception as e:
                console.print(f"  [yellow]Warning: Failed to fetch updates: {e}[/yellow]")
            return repo
        else:
            console.print(f"  Cloning repository to cache...")
            cache_path.mkdir(parents=True, exist_ok=True)
            return git.Repo.clone_from(repo_url, cache_path)
    else:
        # No cache, use temp directory
        tmpdir = tempfile.mkdtemp()
        console.print(f"  Cloning repository...")
        return git.Repo.clone_from(repo_url, tmpdir)


def sample_pr(
    pr_url: str,
    output_dir: Path,
    dataset_version: str,
    github_token: Optional[str] = None,
    cache_dir: Optional[Path] = None,
) -> Optional[Sample]:
    """Sample a single PR and create sample.json.

    Args:
        pr_url: GitHub PR URL
        output_dir: Output directory for samples
        dataset_version: Dataset version string
        github_token: Optional GitHub token
        cache_dir: Optional cache directory for repositories

    Returns:
        Sample object if successful, None if failed
    """
    try:
        owner, repo, pr_number = parse_pr_url(pr_url)
        pr_id = get_pr_id(owner, repo, pr_number)

        console.print(f"[cyan]Sampling {pr_id}...[/cyan]")

        # Fetch PR metadata
        pr_metadata = fetch_pr_metadata(owner, repo, pr_number, github_token)

        base_sha = pr_metadata["base"]["sha"]
        head_sha = pr_metadata["head"]["sha"]
        repo_url = pr_metadata["base"]["repo"]["clone_url"]

        # Get or clone repository
        git_repo = get_or_clone_repo(repo_url, cache_dir)

        # Fetch commits (shallow, no tags) to minimize history exposure and bandwidth
        git_repo.git.fetch("--no-tags", "--depth=1", "origin", base_sha)
        git_repo.git.fetch("--no-tags", "--depth=1", "origin", head_sha)

        # Compute statistics
        console.print(f"  Computing statistics...")
        files_changed, lines_added, lines_deleted, total_diff_hunks = compute_diff_stats(
            git_repo, base_sha, head_sha
        )
        context_size_bytes, truncated = compute_context_size(git_repo, base_sha, head_sha)

        # Create task instructions
        task_instructions = create_task_instructions(pr_metadata)

        # Create sample
        stats = SampleStats(
            files_changed=files_changed,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            total_diff_hunks=total_diff_hunks,
            context_size_bytes=context_size_bytes,
            truncated=truncated,
        )

        sample = Sample(
            dataset_version=dataset_version,
            repo_url=repo_url,
            pr_number=pr_number,
            base_commit=base_sha,
            head_commit=head_sha,
            task_instructions=task_instructions,
            stats=stats,
        )

        # Write sample.json
        sample_dir = output_dir / dataset_version / pr_id
        sample_dir.mkdir(parents=True, exist_ok=True)

        sample_file = sample_dir / "sample.json"
        with open(sample_file, "w") as f:
            f.write(sample.model_dump_json(indent=2))

        console.print(f"[green]✓ Sampled {pr_id}[/green]")
        return sample
            
    except Exception as e:
        console.print(f"[red]✗ Failed to sample {pr_url}: {e}[/red]")
        return None


def run_sample_stage(
    input_path: str,
    output_dir: Path,
    dataset_version: str,
    github_token: Optional[str] = None,
) -> None:
    """Run the sample stage.
    
    Args:
        input_path: PR URL, JSON file with URLs, or directory of samples
        output_dir: Output directory for samples
        dataset_version: Dataset version
        github_token: Optional GitHub token
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine input type
    pr_urls: List[str] = []
    
    if input_path.startswith("http"):
        # Single PR URL
        pr_urls = [input_path]
    elif Path(input_path).is_file():
        # JSON file with PR URLs
        with open(input_path) as f:
            pr_urls = json.load(f)
    else:
        console.print(f"[red]Invalid input: {input_path}[/red]")
        return
    
    console.print(f"[bold]Sampling {len(pr_urls)} PRs...[/bold]")
    
    successful = 0
    failed = 0
    
    for pr_url in pr_urls:
        result = sample_pr(pr_url, output_dir, dataset_version, github_token)
        if result:
            successful += 1
        else:
            failed += 1
    
    console.print(f"\n[bold]Sample stage complete:[/bold]")
    console.print(f"  Successful: {successful}")
    console.print(f"  Failed: {failed}")

