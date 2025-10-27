"""Sample stage: Extract PR metadata and generate task instructions."""

import logging
import tempfile
from pathlib import Path
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from long_context_bench.models import Sample, SampleStats
from long_context_bench.utils import (
    clone_repo,
    get_env_var,
    get_file_list_at_commit,
    get_file_size_at_commit,
    get_pr_id,
    get_unified_diff,
    save_json,
    truncate_text,
)

logger = logging.getLogger(__name__)

MAX_TASK_INSTRUCTIONS_LENGTH = 10000
MAX_CONTEXT_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


class PRSampler:
    """Sampler for extracting PR metadata and generating samples."""

    def __init__(self, dataset_version: str = "v0", github_token: Optional[str] = None):
        """Initialize sampler.
        
        Args:
            dataset_version: Dataset version identifier
            github_token: GitHub API token (or from GITHUB_GIT_TOKEN env var)
        """
        self.dataset_version = dataset_version
        self.github_token = github_token or get_env_var("GITHUB_GIT_TOKEN", required=True)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        })

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=10),
        reraise=True,
    )
    def fetch_pr_metadata(self, repo_url: str, pr_number: int) -> dict:
        """Fetch PR metadata from GitHub API.
        
        Args:
            repo_url: Repository URL
            pr_number: PR number
            
        Returns:
            PR metadata dict
        """
        # Extract owner and repo from URL
        if "github.com/" in repo_url:
            parts = repo_url.split("github.com/")[1].rstrip("/").rstrip(".git").split("/")
        else:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")
        
        owner, repo = parts[0], parts[1]
        
        api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        logger.info(f"Fetching PR metadata from {api_url}")
        
        response = self.session.get(api_url)
        response.raise_for_status()
        
        return response.json()

    def extract_task_instructions(self, pr_metadata: dict) -> str:
        """Extract task instructions from PR metadata.
        
        Uses PR title followed by PR body, truncated to MAX_TASK_INSTRUCTIONS_LENGTH.
        
        Args:
            pr_metadata: PR metadata from GitHub API
            
        Returns:
            Task instructions string
        """
        title = pr_metadata.get("title", "")
        body = pr_metadata.get("body") or ""
        
        # Combine title and body
        instructions = f"{title}\n\n{body}".strip()
        
        # Truncate if needed
        instructions = truncate_text(
            instructions, MAX_TASK_INSTRUCTIONS_LENGTH, "[truncated]"
        )
        
        return instructions

    def compute_stats(
        self, repo_path: Path, base_commit: str, head_commit: str
    ) -> SampleStats:
        """Compute statistics for a PR.
        
        Args:
            repo_path: Path to cloned repository
            base_commit: Base commit SHA
            head_commit: Head commit SHA
            
        Returns:
            SampleStats object
        """
        from git import Repo
        
        repo = Repo(repo_path)
        
        # Get diff stats
        diff = repo.git.diff(base_commit, head_commit, numstat=True)
        
        files_changed = 0
        lines_added = 0
        lines_deleted = 0
        
        for line in diff.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                added, deleted = parts[0], parts[1]
                if added != "-" and deleted != "-":
                    files_changed += 1
                    lines_added += int(added)
                    lines_deleted += int(deleted)
        
        # Count diff hunks
        unified_diff = get_unified_diff(repo, base_commit, head_commit)
        total_diff_hunks = unified_diff.count("\n@@")
        
        # Compute context size (sum of file sizes at base commit)
        changed_files = repo.git.diff(
            base_commit, head_commit, name_only=True
        ).splitlines()
        
        context_size_bytes = 0
        truncated = False
        
        for file_path in changed_files:
            file_size = get_file_size_at_commit(repo, base_commit, file_path)
            context_size_bytes += file_size
            
            if context_size_bytes > MAX_CONTEXT_SIZE_BYTES:
                context_size_bytes = MAX_CONTEXT_SIZE_BYTES
                truncated = True
                break
        
        return SampleStats(
            files_changed=files_changed,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            total_diff_hunks=total_diff_hunks,
            context_size_bytes=context_size_bytes,
            truncated=truncated,
        )

    def sample_pr(
        self, repo_url: str, pr_number: int, output_dir: Path
    ) -> Optional[Sample]:
        """Sample a single PR and generate artifacts.
        
        Args:
            repo_url: Repository URL
            pr_number: PR number
            output_dir: Output directory for artifacts
            
        Returns:
            Sample object or None if sampling failed
        """
        pr_id = get_pr_id(repo_url, pr_number)
        logger.info(f"Sampling PR: {pr_id}")
        
        try:
            # Fetch PR metadata
            pr_metadata = self.fetch_pr_metadata(repo_url, pr_number)
            
            # Check if PR is merged
            if not pr_metadata.get("merged"):
                logger.warning(f"PR {pr_id} is not merged, skipping")
                return None
            
            # Extract commits
            base_commit = pr_metadata["base"]["sha"]
            head_commit = pr_metadata["head"]["sha"]
            
            logger.info(f"Base commit: {base_commit}")
            logger.info(f"Head commit: {head_commit}")
            
            # Clone repo to temporary directory
            with tempfile.TemporaryDirectory() as tmpdir:
                repo_path = Path(tmpdir) / "repo"
                logger.info(f"Cloning repository to {repo_path}")
                
                clone_repo(repo_url, repo_path)
                
                # Compute stats
                logger.info("Computing statistics")
                stats = self.compute_stats(repo_path, base_commit, head_commit)
            
            # Extract task instructions
            task_instructions = self.extract_task_instructions(pr_metadata)
            
            # Create sample
            sample = Sample(
                dataset_version=self.dataset_version,
                repo_url=repo_url,
                pr_number=pr_number,
                base_commit=base_commit,
                head_commit=head_commit,
                task_instructions=task_instructions,
                stats=stats,
            )
            
            # Save sample
            sample_dir = output_dir / "samples" / self.dataset_version / pr_id
            sample_dir.mkdir(parents=True, exist_ok=True)
            
            sample_path = sample_dir / "sample.json"
            save_json(sample.model_dump(), sample_path)
            
            logger.info(f"Sample saved to {sample_path}")
            
            return sample
            
        except Exception as e:
            logger.error(f"Failed to sample PR {pr_id}: {e}", exc_info=True)
            return None

    def sample_from_url_list(
        self, url_list: list[str], output_dir: Path
    ) -> list[Sample]:
        """Sample multiple PRs from a list of URLs.
        
        Args:
            url_list: List of PR URLs
            output_dir: Output directory for artifacts
            
        Returns:
            List of successfully sampled Samples
        """
        samples = []
        
        for url in url_list:
            # Parse URL to extract repo and PR number
            # Format: https://github.com/owner/repo/pull/number
            if "/pull/" not in url:
                logger.warning(f"Invalid PR URL format: {url}")
                continue
            
            parts = url.rstrip("/").split("/")
            pr_number = int(parts[-1])
            repo_url = "/".join(parts[:-2])
            
            sample = self.sample_pr(repo_url, pr_number, output_dir)
            if sample:
                samples.append(sample)
        
        return samples

