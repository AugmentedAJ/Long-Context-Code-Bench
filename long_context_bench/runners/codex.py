"""Codex CLI runner adapter."""

import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict

from long_context_bench.runners.base import RunnerAdapter, RunnerResult


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

        # Codex CLI uses `codex exec` or `codex -p` for non-interactive execution
        # Using `exec` for headless mode
        cmd = [
            self.agent_binary or "codex",
            "exec",  # Non-interactive execution mode
            task_instructions,  # Task prompt
            "--output-format", "stream-json",  # Structured JSON output
        ]

        # Add model if specified
        if self.model:
            cmd.extend(["--model", self.model])

        # Add allowed tools for non-interactive execution
        # This allows file edits and shell commands without prompts
        cmd.extend([
            "--allowedTools", "Edit",  # Allow file edits
            "--allowedTools", "Bash",  # Allow shell commands
        ])

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

