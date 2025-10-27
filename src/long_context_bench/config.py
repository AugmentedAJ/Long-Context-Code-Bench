"""Configuration management for the benchmark."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel


class BenchmarkConfig(BaseModel):
    """Global configuration for benchmark runs."""
    
    # Dataset
    dataset_version: str = "v0"
    
    # Paths
    output_root: Path = Path("output")
    samples_dir: Path = Path("output/samples")
    edits_dir: Path = Path("output/edits")
    judges_dir: Path = Path("output/judges")
    summaries_dir: Path = Path("output/summaries")
    
    # Runner settings
    runner: str = "auggie"
    model: str = "claude-sonnet-4"
    agent_binary: Optional[str] = None
    timeout: int = 1800  # 30 minutes default
    concurrency: int = 1
    
    # Sharding
    total_shards: int = 1
    shard_index: int = 0
    
    # Judge settings
    judge_mode: str = "deterministic"  # deterministic|llm
    judge_model: Optional[str] = None
    
    # Retry settings
    max_retries: int = 2
    retry_backoff_base: float = 2.0
    retry_jitter: float = 0.1
    
    # Feature flags
    disable_retrieval: bool = False
    disable_shell: bool = False
    enable_mcp_codebase_qa: bool = False
    
    # Environment
    github_token: Optional[str] = None
    augment_api_token: Optional[str] = None
    
    def __init__(self, **data):
        """Initialize config with environment variable overrides."""
        super().__init__(**data)
        
        # Override with environment variables if present
        if not self.github_token:
            self.github_token = os.getenv("GITHUB_GIT_TOKEN")
        if not self.augment_api_token:
            self.augment_api_token = os.getenv("AUGMENT_API_TOKEN")
    
    def ensure_directories(self) -> None:
        """Create output directories if they don't exist."""
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.samples_dir.mkdir(parents=True, exist_ok=True)
        self.edits_dir.mkdir(parents=True, exist_ok=True)
        self.judges_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
    
    def get_sample_path(self, pr_id: str) -> Path:
        """Get path for sample artifact."""
        return self.samples_dir / self.dataset_version / pr_id / "sample.json"
    
    def get_edit_path(self, pr_id: str, run_id: str) -> Path:
        """Get path for edit artifact."""
        return self.edits_dir / self.runner / self.model / run_id / pr_id / "edit.json"
    
    def get_judge_path(self, pr_id: str, run_id: str) -> Path:
        """Get path for judge artifact."""
        judge_model = self.judge_model or "none"
        return self.judges_dir / self.judge_mode / judge_model / run_id / pr_id / "judge.json"
    
    def get_summary_path(self, run_id: str) -> Path:
        """Get path for summary artifacts."""
        return self.summaries_dir / run_id

