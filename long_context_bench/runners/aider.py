"""Aider runner adapter."""

import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict

from long_context_bench.runners.base import RunnerAdapter, RunnerResult


class AiderAdapter(RunnerAdapter):
    """Adapter for Aider CLI agent.
    
    Aider is a popular open-source AI pair programming tool.
    Install: pip install aider-chat
    Docs: https://aider.chat/docs/
    """
    
    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
        logs_path: Path,
        env: Optional[Dict[str, str]] = None,
    ) -> RunnerResult:
        """Run Aider on a task.

        Args:
            workspace_path: Path to workspace
            task_instructions: Task instructions
            logs_path: Path to write logs
            env: Optional environment variables

        Returns:
            RunnerResult
        """
        start_time = time.time()
        errors = []

        # Aider uses --message for non-interactive execution
        cmd = [
            self.agent_binary or "aider",
            "--message", task_instructions,  # Non-interactive mode with message
            "--yes-always",  # Auto-accept all prompts
            "--auto-commits",  # Auto-commit changes
        ]

        # Add model if specified
        if self.model:
            cmd.extend(["--model", self.model])

        # Add LLM history file for logging
        llm_history = workspace_path / ".aider.llm.history"
        cmd.extend(["--llm-history-file", str(llm_history)])

        # Disable features based on adapter settings
        if self.disable_retrieval:
            cmd.append("--map-tokens=0")  # Disable repo map
        
        if self.disable_shell:
            cmd.append("--no-suggest-shell-commands")

        # Prepare environment
        run_env = env.copy() if env else {}

        try:
            # Run agent with timeout
            result = subprocess.run(
                cmd,
                cwd=workspace_path,
                env=run_env,
                capture_output=True,
                timeout=self.timeout,
                text=True,
            )
            
            # Write logs - combine stdout/stderr and LLM history
            with open(logs_path, "w") as f:
                log_entry = {
                    "timestamp": time.time(),
                    "event": "agent_run",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                }
                f.write(json.dumps(log_entry) + "\n")
                
                # Append LLM history if it exists
                if llm_history.exists():
                    with open(llm_history, "r") as llm_f:
                        for line in llm_f:
                            f.write(line)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            if result.returncode == 0:
                status = "success"
            else:
                status = "error"
                errors.append(f"Agent exited with code {result.returncode}")
                if result.stderr:
                    errors.append(result.stderr)
            
            return RunnerResult(
                status=status,
                elapsed_ms=elapsed_ms,
                errors=errors if errors else None,
            )
            
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return RunnerResult(
                status="timeout",
                elapsed_ms=elapsed_ms,
                errors=["Agent execution timed out"],
            )
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return RunnerResult(
                status="error",
                elapsed_ms=elapsed_ms,
                errors=[str(e)],
            )
    
    def get_version(self) -> Optional[str]:
        """Get Aider version."""
        try:
            result = subprocess.run(
                [self.agent_binary or "aider", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

