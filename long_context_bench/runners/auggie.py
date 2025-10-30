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
            "--print",  # One-shot mode (non-interactive, auto-skips indexing confirmation)
            "--model", self.model,
            "--workspace-root", str(workspace_path),
            "--instruction-file", str(task_file),
            "--retry-timeout", str(retry_timeout_s),  # Timeout for rate-limit retries
        ]

        if self.disable_retrieval:
            cmd.append("--ask")  # Ask mode disables non-retrieval tools

        # Prepare environment
        run_env = env.copy() if env else {}
        # Harden against unintended Git network prompts during agent execution
        run_env.setdefault("GIT_TERMINAL_PROMPT", "0")  # disable interactive prompts
        run_env.setdefault("GIT_ASKPASS", "true")       # non-interactive askpass

        try:
            # Write command info to logs first
            with open(logs_path, "w") as f:
                log_entry = {
                    "timestamp": time.time(),
                    "event": "agent_start",
                    "runner": "auggie",
                    "model": self.model,
                    "command": cmd,
                    "workspace": str(workspace_path),
                    "timeout_s": self.timeout,
                }
                f.write(json.dumps(log_entry) + "\n")

            # Run agent with timeout
            result = subprocess.run(
                cmd,
                cwd=workspace_path,
                env=run_env,
                capture_output=True,
                timeout=self.timeout,
                text=True,
            )

            # Write comprehensive logs
            with open(logs_path, "a") as f:
                log_entry = {
                    "timestamp": time.time(),
                    "event": "agent_run",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                }
                f.write(json.dumps(log_entry) + "\n")

            # Also write human-readable logs
            readable_log_path = logs_path.parent / "logs_readable.txt"
            with open(readable_log_path, "w") as f:
                f.write("=" * 80 + "\n")
                f.write("AUGGIE RUN LOG\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Model: {self.model}\n")
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"Workspace: {workspace_path}\n")
                f.write(f"Timeout: {self.timeout}s\n")
                f.write(f"Return Code: {result.returncode}\n\n")
                f.write("=" * 80 + "\n")
                f.write("STDOUT\n")
                f.write("=" * 80 + "\n")
                f.write(result.stdout or "(empty)\n\n")
                f.write("=" * 80 + "\n")
                f.write("STDERR\n")
                f.write("=" * 80 + "\n")
                f.write(result.stderr or "(empty)\n")
            
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

