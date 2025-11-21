"""Sample stage: Extract PR metadata and create sample.json files."""

import json
import random
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
from long_context_bench.synthesis import (
    synthesize_task_instructions,
    synthesize_with_auggie,
    get_synthesis_timestamp,
)

console = Console()

# Load synthesized prompts mapping
_SYNTHESIZED_PROMPTS_CACHE = None

def _load_synthesized_prompts() -> dict:
    """Load synthesized prompts from the mapping file.

    Returns:
        Dictionary mapping PR number (str) to list of prompt variants
    """
    global _SYNTHESIZED_PROMPTS_CACHE

    if _SYNTHESIZED_PROMPTS_CACHE is not None:
        return _SYNTHESIZED_PROMPTS_CACHE

    # Try to load from the prompt_dataset directory
    mapping_file = Path(__file__).parent.parent.parent / "prompt_dataset" / "synthesized_prompts_mapping.json"

    if mapping_file.exists():
        with open(mapping_file) as f:
            _SYNTHESIZED_PROMPTS_CACHE = json.load(f)
            console.print(f"[dim]Loaded synthesized prompts for {len(_SYNTHESIZED_PROMPTS_CACHE)} PRs[/dim]")
    else:
        console.print(f"[yellow]Warning: Synthesized prompts mapping not found at {mapping_file}[/yellow]")
        _SYNTHESIZED_PROMPTS_CACHE = {}

    return _SYNTHESIZED_PROMPTS_CACHE


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


def create_task_instructions(pr_metadata: dict, pr_number: Optional[int] = None, variant: Optional[int] = None) -> str:
    """Create task instructions from PR metadata.

    This function now uses synthesized prompts from the prompt_dataset when available.
    Falls back to the template-based approach if no synthesized prompt is found.

    Args:
        pr_metadata: PR metadata from GitHub API
        pr_number: Optional PR number to look up synthesized prompt
        variant: Optional variant number (0-4) to select specific prompt. If None, randomly selects one.

    Returns:
        Task instructions string
    """
    # Try to use synthesized prompt if PR number is provided
    if pr_number is not None:
        prompts_map = _load_synthesized_prompts()
        pr_key = str(pr_number)

        if pr_key in prompts_map:
            variants = prompts_map[pr_key]

            if variants:
                # Select variant
                if variant is not None and 0 <= variant < len(variants):
                    selected_variant = variants[variant]
                else:
                    # Randomly select a variant
                    selected_variant = random.choice(variants)

                prompt = selected_variant["prompt"]
                console.print(f"[dim]Using synthesized prompt (variant {selected_variant['rollout']}) for PR {pr_number}[/dim]")
                return prompt
            else:
                console.print(f"[yellow]Warning: No variants found for PR {pr_number}, falling back to template[/yellow]")
        else:
            console.print(f"[yellow]Warning: No synthesized prompt found for PR {pr_number}, falling back to template[/yellow]")

    # Fallback to template-based approach
    title = pr_metadata.get("title", "")
    body = pr_metadata.get("body") or ""

    # Build the core task description
    task_description = f"{title}\n\n{body}" if body else title

    # Wrap with context to make it clear this is a code editing task
    instructions = f"""You are working on a codebase. Your task is to make the necessary code changes to accomplish the following:

{task_description}

Please make all necessary code changes to complete this task."""

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
    force: bool = False,
    synthesize: bool = False,
    synthesis_model: str = "claude-3-7-sonnet-20250219",
) -> Optional[Sample]:
    """Sample a single PR and create sample.json.

    Args:
        pr_url: GitHub PR URL
        output_dir: Output directory for samples
        dataset_version: Dataset version string
        github_token: Optional GitHub token
        cache_dir: Optional cache directory for repositories
        force: If True, re-sample even if sample.json already exists
        synthesize: If True, generate synthesized task instructions using LLM
        synthesis_model: LiteLLM model identifier for synthesis

    Returns:
        Sample object if successful, None if failed
    """
    try:
        owner, repo, pr_number = parse_pr_url(pr_url)
        pr_id = get_pr_id(owner, repo, pr_number)

        # Check if sample already exists
        sample_dir = output_dir / dataset_version / pr_id
        sample_file = sample_dir / "sample.json"

        if sample_file.exists() and not force:
            console.print(f"[yellow]⊙ Skipping {pr_id} (already sampled)[/yellow]")
            # Load and return existing sample
            with open(sample_file) as f:
                sample_data = json.load(f)
                return Sample(**sample_data)

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

        # Create task instructions (uses synthesized prompts when available)
        task_instructions = create_task_instructions(pr_metadata, pr_number=pr_number)

        # Optionally synthesize task instructions using LLM
        synthesized_instructions = None
        synthesis_model_used = None
        synthesis_ts = None

        if synthesize:
            console.print(f"  Synthesizing task instructions...")
            # Get PR diff for synthesis
            pr_diff = git_repo.git.diff(base_sha, head_sha)

            # Choose synthesis method based on model
            if synthesis_model.startswith("auggie/"):
                # Use Auggie CLI for synthesis
                auggie_model = synthesis_model.replace("auggie/", "")
                synthesized_instructions = synthesize_with_auggie(
                    pr_title=pr_metadata.get("title", ""),
                    pr_body=pr_metadata.get("body") or "",
                    pr_diff=pr_diff,
                    model=auggie_model,
                )
            else:
                # Use LiteLLM for synthesis
                synthesized_instructions = synthesize_task_instructions(
                    pr_title=pr_metadata.get("title", ""),
                    pr_body=pr_metadata.get("body") or "",
                    pr_diff=pr_diff,
                    model=synthesis_model,
                )

            if synthesized_instructions:
                synthesis_model_used = synthesis_model
                synthesis_ts = get_synthesis_timestamp()

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
            synthesized_task_instructions=synthesized_instructions,
            synthesis_model=synthesis_model_used,
            synthesis_timestamp=synthesis_ts,
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
    force: bool = False,
    synthesize: bool = False,
    synthesis_model: str = "claude-3-7-sonnet-20250219",
    cache_dir: Optional[Path] = None,
) -> None:
    """Run the sample stage.

    Args:
        input_path: PR URL, JSON file with URLs, or directory of samples
        output_dir: Output directory for samples
        dataset_version: Dataset version
        github_token: Optional GitHub token
        force: If True, re-sample even if sample.json already exists
        synthesize: If True, generate synthesized task instructions using LLM
        synthesis_model: LiteLLM model identifier for synthesis
        cache_dir: Optional cache directory for repositories
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
    skipped = 0

    for pr_url in pr_urls:
        result = sample_pr(
            pr_url,
            output_dir,
            dataset_version,
            github_token,
            cache_dir=cache_dir,
            force=force,
            synthesize=synthesize,
            synthesis_model=synthesis_model,
        )
        if result:
            # Check if it was skipped (file existed before)
            owner, repo, pr_number = parse_pr_url(pr_url)
            pr_id = get_pr_id(owner, repo, pr_number)
            sample_file = output_dir / dataset_version / pr_id / "sample.json"
            # If force=False and file existed, it was loaded (not re-sampled)
            # We can't easily distinguish, so just count as successful
            successful += 1
        else:
            failed += 1

    console.print(f"\n[bold]Sample stage complete:[/bold]")
    console.print(f"  Successful: {successful}")
    console.print(f"  Failed: {failed}")

