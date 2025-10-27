"""Base runner adapter interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class RunnerResult:
    """Result from running an agent."""
    status: str  # success|timeout|error
    elapsed_ms: int
    errors: Optional[list[str]] = None


class RunnerAdapter(ABC):
    """Abstract base class for agent runner adapters.
    
    Per R-4.4-4.7: Adapters provide a common contract for running CLI agents.
    """
    
    def __init__(
        self,
        model: str,
        agent_binary: Optional[str] = None,
        timeout: int = 1800,
        disable_retrieval: bool = False,
        disable_shell: bool = False,
        enable_mcp_codebase_qa: bool = False,
        **kwargs: Any,
    ):
        """Initialize runner adapter.
        
        Args:
            model: Model name to use
            agent_binary: Optional path to agent binary
            timeout: Timeout in seconds
            disable_retrieval: Disable retrieval features
            disable_shell: Disable shell access
            enable_mcp_codebase_qa: Enable MCP codebase QA
            **kwargs: Additional adapter-specific arguments
        """
        self.model = model
        self.agent_binary = agent_binary
        self.timeout = timeout
        self.disable_retrieval = disable_retrieval
        self.disable_shell = disable_shell
        self.enable_mcp_codebase_qa = enable_mcp_codebase_qa
        self.extra_kwargs = kwargs
    
    @abstractmethod
    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
        logs_path: Path,
        env: Optional[Dict[str, str]] = None,
    ) -> RunnerResult:
        """Run the agent on a task.
        
        Args:
            workspace_path: Path to workspace (checked out at base commit)
            task_instructions: Task instructions string
            logs_path: Path to write structured logs (JSONL)
            env: Optional environment variables
            
        Returns:
            RunnerResult with status, elapsed time, and optional errors
        """
        pass
    
    def get_version(self) -> Optional[str]:
        """Get runner version.
        
        Returns:
            Version string if available, None otherwise
        """
        return None

