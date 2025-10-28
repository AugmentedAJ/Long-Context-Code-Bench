"""Auggie runner adapter."""

import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict

from long_context_bench.runners.base import RunnerAdapter, RunnerResult


class AuggieAdapter(RunnerAdapter):
    """Adapter for Auggie CLI agent."""
    
    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
        logs_path: Path,
        env: Optional[Dict[str, str]] = None,
    ) -> RunnerResult:
        """Run Auggie on a task.

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

        # Write task instructions to temp file
        task_file = workspace_path / ".auggie_task.txt"
        task_file.write_text(task_instructions)

        # Prepare command using correct auggie flags
        # Use the configured timeout for retry-timeout (in seconds)
        retry_timeout_s = self.timeout

        cmd = [
            self.agent_binary or "auggie",
            "--print",  # One-shot mode (non-interactive)
            "--allow-indexing",  # Skip indexing confirmation prompt
            "--model", self.model,
            "--workspace-root", str(workspace_path),
            "--instruction-file", str(task_file),
            "--retry-timeout", str(retry_timeout_s),  # Timeout for rate-limit retries
        ]

        if self.disable_retrieval:
            cmd.append("--ask")  # Ask mode disables non-retrieval tools

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
            
            # Write logs
            with open(logs_path, "w") as f:
                log_entry = {
                    "timestamp": time.time(),
                    "event": "agent_run",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                }
                f.write(json.dumps(log_entry) + "\n")
            
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
        finally:
            # Clean up task file
            if task_file.exists():
                task_file.unlink()
    
    def get_version(self) -> Optional[str]:
        """Get Auggie version."""
        try:
            result = subprocess.run(
                [self.agent_binary or "auggie", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

