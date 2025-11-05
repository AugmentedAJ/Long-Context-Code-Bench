"""Auggie runner adapter."""

import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict

from long_context_bench.runners.base import RunnerAdapter, RunnerResult
from long_context_bench.runners.stream_utils import run_with_streaming
from long_context_bench.runners.asciinema_utils import get_recording_path


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

            # Determine asciinema recording path if enabled
            asciinema_output = None
            if self.enable_asciinema:
                asciinema_output = get_recording_path(logs_path)

            # Run agent with optional streaming and asciinema recording
            returncode, stdout = run_with_streaming(
                cmd=cmd,
                cwd=str(workspace_path),
                env=run_env,
                timeout=self.timeout,
                stream_output=self.stream_output,
                enable_asciinema=self.enable_asciinema,
                asciinema_output=asciinema_output,
            )

            # Write comprehensive logs
            with open(logs_path, "a") as f:
                log_entry = {
                    "timestamp": time.time(),
                    "event": "agent_run",
                    "stdout": stdout,
                    "stderr": "",  # Merged into stdout
                    "returncode": returncode,
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
                f.write(f"Return Code: {returncode}\n\n")
                f.write("=" * 80 + "\n")
                f.write("STDOUT\n")
                f.write("=" * 80 + "\n")
                f.write(stdout or "(empty)\n\n")

            elapsed_ms = int((time.time() - start_time) * 1000)

            if returncode == 0:
                status = "success"
            else:
                status = "error"
                errors.append(f"Agent exited with code {returncode}")
                # Extract error from stdout if present
                if "error" in stdout.lower() or "failed" in stdout.lower():
                    errors.append(stdout[-500:])  # Last 500 chars for context

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

