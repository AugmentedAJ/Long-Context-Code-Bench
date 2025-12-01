"""Factory CLI (droid) runner adapter."""

import json
import shutil
import subprocess
import tempfile
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

    def _setup_mcp_config(self, mcp_config_path: str) -> Optional[Path]:
        """Setup MCP configuration for Factory Droid.

        Factory Droid reads MCP configuration from ~/.factory/mcp.json.
        This method backs up the existing config (if any) and installs
        the provided config file.

        Args:
            mcp_config_path: Path to the MCP configuration file

        Returns:
            Path to the backup file if one was created, None otherwise
        """
        factory_config_dir = Path.home() / ".factory"
        factory_mcp_config = factory_config_dir / "mcp.json"
        backup_path = None

        # Create .factory directory if it doesn't exist
        factory_config_dir.mkdir(parents=True, exist_ok=True)

        # Backup existing config if present
        if factory_mcp_config.exists():
            backup_path = factory_config_dir / f"mcp.json.backup.{int(time.time())}"
            shutil.copy2(factory_mcp_config, backup_path)

        # Copy the provided MCP config
        shutil.copy2(mcp_config_path, factory_mcp_config)

        return backup_path

    def _restore_mcp_config(self, backup_path: Optional[Path]) -> None:
        """Restore the original MCP configuration.

        Args:
            backup_path: Path to the backup file, or None if no backup exists
        """
        factory_mcp_config = Path.home() / ".factory" / "mcp.json"

        if backup_path and backup_path.exists():
            # Restore from backup
            shutil.copy2(backup_path, factory_mcp_config)
            backup_path.unlink()  # Remove backup file
        elif factory_mcp_config.exists():
            # No backup means we created the config, so remove it
            factory_mcp_config.unlink()

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
        mcp_backup_path = None

        # Setup MCP configuration if provided
        if self.mcp_config_path:
            try:
                mcp_backup_path = self._setup_mcp_config(self.mcp_config_path)
            except Exception as e:
                errors.append(f"Failed to setup MCP config: {e}")
                return RunnerResult(
                    status="error",
                    elapsed_ms=int((time.time() - start_time) * 1000),
                    errors=errors,
                )

        try:
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
                    "mcp_config": self.mcp_config_path,
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
                if self.mcp_config_path:
                    f.write(f"MCP Config: {self.mcp_config_path}\n")
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
        finally:
            # Always restore the original MCP config
            if self.mcp_config_path:
                try:
                    self._restore_mcp_config(mcp_backup_path)
                except Exception as e:
                    # Log but don't fail the run if restore fails
                    print(f"Warning: Failed to restore MCP config: {e}")
    
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

