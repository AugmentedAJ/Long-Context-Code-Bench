"""Base runner interface for CLI-based coding agents."""

import json
import logging
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from git import Repo

logger = logging.getLogger(__name__)


@dataclass
class RunnerResult:
    """Result from running an agent."""
    
    status: str  # success|timeout|error
    elapsed_ms: int
    patch_unified: str
    logs_path: str
    errors: Optional[list[str]] = None


class BaseRunner(ABC):
    """Base class for agent runners."""
    
    def __init__(self, config):
        """Initialize runner.
        
        Args:
            config: Benchmark configuration
        """
        self.config = config
    
    def prepare_workspace(
        self, 
        repo_url: str, 
        base_commit: str, 
        workspace_path: Path
    ) -> None:
        """Prepare a clean workspace at the base commit.
        
        Args:
            repo_url: Repository URL
            base_commit: Base commit hash
            workspace_path: Path to workspace directory
        """
        logger.info(f"Preparing workspace at {workspace_path}")
        
        # Clone repository
        repo = Repo.clone_from(repo_url, workspace_path)
        
        # Checkout base commit (detached HEAD)
        repo.git.checkout(base_commit)
        
        logger.info(f"Workspace ready at commit {base_commit}")
    
    def extract_diff(self, workspace_path: Path) -> str:
        """Extract unified diff from workspace.
        
        Args:
            workspace_path: Path to workspace directory
            
        Returns:
            Unified diff as string
        """
        repo = Repo(workspace_path)
        
        # Get diff against HEAD (base commit)
        diff = repo.git.diff('HEAD')
        
        return diff
    
    def write_logs(self, logs: list[dict], logs_path: Path) -> None:
        """Write structured logs to JSONL file.
        
        Args:
            logs: List of log entries
            logs_path: Path to logs file
        """
        logs_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(logs_path, 'w') as f:
            for log_entry in logs:
                f.write(json.dumps(log_entry) + '\n')
    
    @abstractmethod
    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
        logs_path: Path
    ) -> RunnerResult:
        """Run the agent on a task.
        
        Args:
            workspace_path: Path to prepared workspace
            task_instructions: Task instructions for the agent
            logs_path: Path to write logs
            
        Returns:
            RunnerResult with status and outputs
        """
        pass
    
    def execute_with_timeout(
        self,
        cmd: list[str],
        workspace_path: Path,
        timeout_s: int,
        env: Optional[dict] = None
    ) -> tuple[int, str, str, int]:
        """Execute a command with timeout.
        
        Args:
            cmd: Command and arguments
            workspace_path: Working directory
            timeout_s: Timeout in seconds
            env: Environment variables
            
        Returns:
            Tuple of (return_code, stdout, stderr, elapsed_ms)
        """
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=env
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            return result.returncode, result.stdout, result.stderr, elapsed_ms
            
        except subprocess.TimeoutExpired as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            stdout = e.stdout.decode() if e.stdout else ""
            stderr = e.stderr.decode() if e.stderr else ""
            return -1, stdout, stderr, elapsed_ms

