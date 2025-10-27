"""Auggie runner adapter."""

import os
import subprocess
import time
from pathlib import Path

from long_context_bench.runners.base import RunnerAdapter, RunnerResult


class AuggieAdapter(RunnerAdapter):
    """Adapter for Auggie CLI agent."""

    def get_default_binary_name(self) -> str:
        """Get the default binary name for Auggie."""
        return "auggie"

    def get_version(self) -> str:
        """Get Auggie version."""
        try:
            binary = self.get_binary_path()
            result = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip()
        except Exception as e:
            self.logger.warning(f"Failed to get Auggie version: {e}")
            return "unknown"

    def validate_environment(self) -> None:
        """Validate Auggie environment."""
        # Check for AUGMENT_API_TOKEN
        if not os.getenv("AUGMENT_API_TOKEN"):
            raise ValueError(
                "AUGMENT_API_TOKEN environment variable is required for Auggie"
            )

    def build_command(
        self,
        workspace_path: Path,
        task_instructions: str,
    ) -> list[str]:
        """Build Auggie command.
        
        Args:
            workspace_path: Path to workspace
            task_instructions: Task instructions
            
        Returns:
            Command as list of strings
        """
        binary = self.get_binary_path()
        
        cmd = [
            binary,
            "--model", self.config.model,
            "--workspace", str(workspace_path),
        ]
        
        # Add optional flags
        if self.config.disable_retrieval:
            cmd.append("--disable-retrieval")
        
        if self.config.disable_shell:
            cmd.append("--disable-shell")
        
        if self.config.enable_mcp_codebase_qa:
            cmd.append("--enable-mcp-codebase-qa")
        
        # Add task instructions as the last argument
        cmd.append(task_instructions)
        
        return cmd

    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
    ) -> RunnerResult:
        """Run Auggie on a task.
        
        Args:
            workspace_path: Path to workspace
            task_instructions: Task instructions
            
        Returns:
            RunnerResult
        """
        self.validate_environment()
        
        cmd = self.build_command(workspace_path, task_instructions)
        
        self.logger.info(f"Running command: {' '.join(cmd)}")
        
        start_time = time.time()
        
        try:
            # Prepare environment
            env = os.environ.copy()
            if self.config.env:
                env.update(self.config.env)
            
            # Run the command
            result = subprocess.run(
                cmd,
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_s,
                env=env,
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Parse logs
            logs = self.parse_logs(result.stdout, result.stderr)
            
            # Determine status
            if result.returncode == 0:
                status = "success"
                errors = None
            else:
                status = "error"
                errors = self.extract_errors(logs, result.returncode)
            
            return RunnerResult(
                status=status,
                elapsed_ms=elapsed_ms,
                logs=logs,
                errors=errors,
            )
            
        except subprocess.TimeoutExpired as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            logs = []
            if e.stdout:
                logs.extend(e.stdout.decode().splitlines())
            if e.stderr:
                logs.extend(e.stderr.decode().splitlines())
            
            return RunnerResult(
                status="timeout",
                elapsed_ms=elapsed_ms,
                logs=logs,
                errors=[f"Timeout after {self.config.timeout_s}s"],
            )
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            return RunnerResult(
                status="error",
                elapsed_ms=elapsed_ms,
                logs=[],
                errors=[str(e)],
            )

