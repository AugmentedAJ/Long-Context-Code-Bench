"""Factory CLI (droid) runner adapter."""

import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict

from long_context_bench.runners.base import RunnerAdapter, RunnerResult
from long_context_bench.runners.stream_utils import run_with_streaming


class FactoryAdapter(RunnerAdapter):
    """Adapter for Factory CLI (droid) agent.

    Factory CLI (droid) is Factory.ai's command-line coding agent.
    Install: npm install -g @factory-ai/droid
    Docs: https://docs.factory.ai/cli/
    """

    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
        logs_path: Path,
        env: Optional[Dict[str, str]] = None,
    ) -> RunnerResult:
        """Run Factory CLI (droid) on a task.

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

        # Factory CLI uses `droid exec` for non-interactive execution
        # Use --skip-permissions-unsafe for benchmark (isolated workspace)
        cmd = [
            self.agent_binary or "droid",
            "exec",  # Non-interactive execution mode (headless)
            "--skip-permissions-unsafe",  # Allow all operations in isolated workspace
            task_instructions,  # Task prompt
            "--output-format", "stream-json",  # Enable streaming JSON output
        ]

        # Add model if specified
        if self.model:
            cmd.extend(["--model", self.model])

        # Prepare environment
        run_env = env.copy() if env else {}
        
        # Set FACTORY_API_KEY if provided in environment
        # This allows the benchmark to use a specific API key
        if "FACTORY_API_KEY" not in run_env:
            # Try to get from system environment
            import os
            if "FACTORY_API_KEY" in os.environ:
                run_env["FACTORY_API_KEY"] = os.environ["FACTORY_API_KEY"]

        try:
            # Write command info to logs first
            with open(logs_path, "w") as f:
                log_entry = {
                    "timestamp": time.time(),
                    "event": "agent_start",
                    "runner": "factory",
                    "model": self.model or "default (from config)",
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

            # Also write human-readable logs
            readable_log_path = logs_path.parent / "logs_readable.txt"
            with open(readable_log_path, "w") as f:
                f.write("=" * 80 + "\n")
                f.write("FACTORY (DROID) RUN LOG\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Model: {self.model or 'default (from config)'}\n")
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"Workspace: {workspace_path}\n")
                f.write(f"Timeout: {self.timeout}s\n")
                f.write(f"Return Code: {returncode}\n\n")
                f.write("=" * 80 + "\n")
                f.write("STDOUT (stream-json format)\n")
                f.write("=" * 80 + "\n")
                f.write(stdout or "(empty)\n\n")

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
        """Get Factory CLI (droid) version."""
        try:
            result = subprocess.run(
                [self.agent_binary or "droid", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

