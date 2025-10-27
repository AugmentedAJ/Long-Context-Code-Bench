"""Base runner adapter interface."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RunnerConfig:
    """Configuration for a runner."""

    runner: str
    model: str
    agent_binary: Optional[str] = None
    timeout_s: int = 1800
    disable_retrieval: bool = False
    disable_shell: bool = False
    enable_mcp_codebase_qa: bool = False
    env: Optional[dict[str, str]] = None


@dataclass
class RunnerResult:
    """Result of running an agent."""

    status: str  # success, timeout, error
    elapsed_ms: int
    logs: list[str]
    errors: Optional[list[str]] = None


class RunnerAdapter(ABC):
    """Abstract base class for runner adapters.
    
    Each runner adapter implements the interface for a specific CLI-based coding agent.
    """

    def __init__(self, config: RunnerConfig):
        """Initialize runner adapter.
        
        Args:
            config: Runner configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def get_version(self) -> str:
        """Get the version of the agent.
        
        Returns:
            Version string
        """
        pass

    @abstractmethod
    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
    ) -> RunnerResult:
        """Run the agent on a task.
        
        Args:
            workspace_path: Path to workspace (checked out at base commit)
            task_instructions: Task instructions to pass to the agent
            
        Returns:
            RunnerResult with status, elapsed time, and logs
        """
        pass

    def validate_environment(self) -> None:
        """Validate that the environment is set up correctly for this runner.
        
        Raises:
            ValueError: If environment is not valid
        """
        pass

    def get_binary_path(self) -> str:
        """Get the path to the agent binary.
        
        Returns:
            Path to binary
            
        Raises:
            ValueError: If binary is not found
        """
        if self.config.agent_binary:
            binary_path = Path(self.config.agent_binary)
            if not binary_path.exists():
                raise ValueError(f"Agent binary not found: {self.config.agent_binary}")
            return str(binary_path)
        
        # Try to find in PATH
        import shutil
        
        binary_name = self.get_default_binary_name()
        binary_path = shutil.which(binary_name)
        
        if not binary_path:
            raise ValueError(
                f"Agent binary '{binary_name}' not found in PATH. "
                f"Please specify --agent-binary or add to PATH."
            )
        
        return binary_path

    @abstractmethod
    def get_default_binary_name(self) -> str:
        """Get the default binary name for this runner.
        
        Returns:
            Binary name (e.g., 'auggie')
        """
        pass

    def build_command(
        self,
        workspace_path: Path,
        task_instructions: str,
    ) -> list[str]:
        """Build the command to run the agent.
        
        Args:
            workspace_path: Path to workspace
            task_instructions: Task instructions
            
        Returns:
            Command as list of strings
        """
        raise NotImplementedError("Subclass must implement build_command")

    def parse_logs(self, stdout: str, stderr: str) -> list[str]:
        """Parse logs from agent output.
        
        Args:
            stdout: Standard output
            stderr: Standard error
            
        Returns:
            List of log lines
        """
        logs = []
        
        if stdout:
            logs.extend(stdout.splitlines())
        
        if stderr:
            logs.extend(stderr.splitlines())
        
        return logs

    def extract_errors(self, logs: list[str], returncode: int) -> Optional[list[str]]:
        """Extract error messages from logs.
        
        Args:
            logs: Log lines
            returncode: Process return code
            
        Returns:
            List of error messages or None
        """
        if returncode == 0:
            return None
        
        # Look for common error patterns
        errors = []
        for line in logs:
            line_lower = line.lower()
            if any(
                keyword in line_lower
                for keyword in ["error", "exception", "failed", "traceback"]
            ):
                errors.append(line)
        
        if not errors:
            errors = [f"Process exited with code {returncode}"]
        
        return errors

