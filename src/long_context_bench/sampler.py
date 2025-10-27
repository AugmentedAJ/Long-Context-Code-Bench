"""Sampler stage: Extract PR metadata and create sample artifacts."""

import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import requests
from git import Repo

from .config import BenchmarkConfig
from .schemas import Sample, SampleStats, get_pr_id
from .utils import save_json, truncate_text

logger = logging.getLogger(__name__)


class PRSampler:
    """Sampler for creating benchmark samples from GitHub PRs."""
    
    def __init__(self, config: BenchmarkConfig):
        """Initialize sampler.
        
        Args:
            config: Benchmark configuration
        """
        self.config = config
        self.session = requests.Session()
        if config.github_token:
            self.session.headers['Authorization'] = f'token {config.github_token}'
    
    def parse_pr_url(self, pr_url: str) -> tuple[str, str, int]:
        """Parse GitHub PR URL into components.
        
        Args:
            pr_url: GitHub PR URL
            
        Returns:
            Tuple of (owner, repo, pr_number)
            
        Raises:
            ValueError: If URL format is invalid
        """
        # Match: https://github.com/owner/repo/pull/123
        pattern = r'https://github\.com/([^/]+)/([^/]+)/pull/(\d+)'
        match = re.match(pattern, pr_url)
        if not match:
            raise ValueError(f"Invalid PR URL format: {pr_url}")
        
        owner, repo, pr_number = match.groups()
        return owner, repo, int(pr_number)
    
    def fetch_pr_metadata(self, owner: str, repo: str, pr_number: int) -> dict:
        """Fetch PR metadata from GitHub API.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            
        Returns:
            PR metadata dictionary
            
        Raises:
            requests.HTTPError: If API request fails
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def extract_task_instructions(self, pr_data: dict) -> str:
        """Extract task instructions from PR metadata.
        
        Args:
            pr_data: PR metadata from GitHub API
            
        Returns:
            Task instructions (title + body, truncated to 10k chars)
        """
        title = pr_data.get('title', '')
        body = pr_data.get('body') or ''
        
        # Combine title and body
        instructions = f"{title}\n\n{body}"
        
        # Truncate to 10,000 characters
        return truncate_text(instructions, 10000, "\n[truncated]")
    
    def compute_diff_stats(
        self, 
        repo_path: Path, 
        base_commit: str, 
        head_commit: str
    ) -> SampleStats:
        """Compute statistics about the PR diff.
        
        Args:
            repo_path: Path to git repository
            base_commit: Base commit hash
            head_commit: Head commit hash
            
        Returns:
            Sample statistics
        """
        repo = Repo(repo_path)
        
        # Get diff between base and head
        diff_output = repo.git.diff(
            base_commit, 
            head_commit, 
            numstat=True
        )
        
        # Parse numstat output
        files_changed = 0
        lines_added = 0
        lines_deleted = 0
        
        for line in diff_output.strip().split('\n'):
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 2:
                try:
                    added = int(parts[0]) if parts[0] != '-' else 0
                    deleted = int(parts[1]) if parts[1] != '-' else 0
                    lines_added += added
                    lines_deleted += deleted
                    files_changed += 1
                except ValueError:
                    continue
        
        # Count diff hunks
        diff_text = repo.git.diff(base_commit, head_commit)
        total_diff_hunks = diff_text.count('\n@@')
        
        # Compute context size (sum of file sizes at base commit)
        context_size_bytes = 0
        truncated = False
        max_context_size = 20 * 1024 * 1024  # 20 MB
        
        # Get list of changed files
        changed_files = repo.git.diff(
            base_commit, 
            head_commit, 
            name_only=True
        ).strip().split('\n')
        
        for file_path in changed_files:
            if not file_path:
                continue
            try:
                # Get file size at base commit
                file_content = repo.git.show(f"{base_commit}:{file_path}")
                file_size = len(file_content.encode('utf-8'))
                
                if context_size_bytes + file_size > max_context_size:
                    truncated = True
                    break
                
                context_size_bytes += file_size
            except Exception as e:
                logger.warning(f"Could not get size for {file_path}: {e}")
                continue
        
        return SampleStats(
            files_changed=files_changed,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            total_diff_hunks=total_diff_hunks,
            context_size_bytes=context_size_bytes,
            truncated=truncated
        )
    
    def sample_pr(self, pr_url: str) -> Optional[Sample]:
        """Create a sample from a PR URL.
        
        Args:
            pr_url: GitHub PR URL
            
        Returns:
            Sample object, or None if sampling failed
        """
        try:
            # Parse URL
            owner, repo, pr_number = self.parse_pr_url(pr_url)
            repo_url = f"https://github.com/{owner}/{repo}"
            
            logger.info(f"Sampling PR: {owner}/{repo}#{pr_number}")
            
            # Fetch PR metadata
            pr_data = self.fetch_pr_metadata(owner, repo, pr_number)
            
            base_commit = pr_data['base']['sha']
            head_commit = pr_data['head']['sha']
            
            # Clone repository to temporary directory
            with tempfile.TemporaryDirectory() as tmpdir:
                repo_path = Path(tmpdir) / repo
                logger.info(f"Cloning repository to {repo_path}")
                
                Repo.clone_from(
                    repo_url,
                    repo_path,
                    depth=1,
                    branch=pr_data['base']['ref']
                )
                
                # Fetch PR commits
                repo_obj = Repo(repo_path)
                repo_obj.git.fetch('origin', f"pull/{pr_number}/head:pr-{pr_number}")
                
                # Compute statistics
                stats = self.compute_diff_stats(repo_path, base_commit, head_commit)
            
            # Extract task instructions
            task_instructions = self.extract_task_instructions(pr_data)
            
            # Create sample
            sample = Sample(
                dataset_version=self.config.dataset_version,
                repo_url=repo_url,
                pr_number=pr_number,
                base_commit=base_commit,
                head_commit=head_commit,
                task_instructions=task_instructions,
                stats=stats
            )
            
            # Save sample
            pr_id = get_pr_id(repo_url, pr_number)
            sample_path = self.config.get_sample_path(pr_id)
            save_json(sample.model_dump(), sample_path)
            
            logger.info(f"Sample saved to {sample_path}")
            return sample
            
        except Exception as e:
            logger.error(f"Failed to sample PR {pr_url}: {e}", exc_info=True)
            return None

