"""Codex CLI runner adapter."""

import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict

from long_context_bench.runners.base import RunnerAdapter, RunnerResult
from long_context_bench.runners.stream_utils import run_with_streaming


class CodexAdapter(RunnerAdapter):
    """Adapter for OpenAI Codex CLI agent.

    Codex CLI is OpenAI's command-line coding agent.
    Install: npm install -g @openai/codex
    Docs: https://developers.openai.com/codex/cli/
    """


    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
        logs_path: Path,
        env: Optional[Dict[str, str]] = None,
    ) -> RunnerResult:
        """Run Codex CLI on a task.

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

        # Codex CLI uses `codex exec` for non-interactive execution
        # Use --json for JSONL output, --full-auto for automatic execution
        cmd = [
            self.agent_binary or "codex",
            "exec",  # Non-interactive execution mode
            task_instructions,  # Task prompt
            "--json",  # Output events as JSONL
            "--full-auto",  # Auto-approve all actions (sandboxed)
            "--skip-git-repo-check",  # Allow running in any directory
        ]

        # Add model if specified
        if self.model:
            cmd.extend(["-m", self.model])

        # Prepare environment
        run_env = env.copy() if env else {}

        try:
            # Write command info to logs first
            with open(logs_path, "w") as f:
                log_entry = {
                    "timestamp": time.time(),
                    "event": "agent_start",
                    "runner": "codex",
                    "model": self.model,
                    "command": cmd,
                    "workspace": str(workspace_path),
                    "timeout_s": self.timeout,
                }
                f.write(json.dumps(log_entry) + "\n")

            # Run agent with optional streaming
            returncode, stdout = run_with_streaming(
                cmd=cmd,
                cwd=str(workspace_path),
                env=run_env,
                timeout=self.timeout,
                stream_output=self.stream_output,
            )

            # Write comprehensive run logs
            with open(logs_path, "a") as f:
                log_entry = {
                    "timestamp": time.time(),
                    "event": "agent_run",
                    "stdout": stdout,
                    "stderr": "",  # Merged into stdout when streaming
                    "returncode": returncode,
                }
                f.write(json.dumps(log_entry) + "\n")

            elapsed_ms = int((time.time() - start_time) * 1000)

            if returncode == 0:
                status = "success"
            else:
                status = "error"
                errors.append(f"Agent exited with code {returncode}")
                if stdout and "error" in stdout.lower():
                    errors.append("Check logs for error details")

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
        """Get Codex CLI version."""
        try:
            result = subprocess.run(
                [self.agent_binary or "codex", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

