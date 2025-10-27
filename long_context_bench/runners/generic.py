"""Generic runner adapter for CLI agents."""

import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict

from long_context_bench.runners.base import RunnerAdapter, RunnerResult


class GenericAdapter(RunnerAdapter):
    """Generic adapter for CLI agents.
    
    Assumes the agent accepts task instructions via stdin or a file.
    """
    
    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
        logs_path: Path,
        env: Optional[Dict[str, str]] = None,
    ) -> RunnerResult:
        """Run generic CLI agent on a task.
        
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
        
        if not self.agent_binary:
            return RunnerResult(
                status="error",
                elapsed_ms=0,
                errors=["agent_binary is required for generic runner"],
            )
        
        # Prepare command
        cmd = [self.agent_binary]
        
        # Prepare environment
        run_env = env.copy() if env else {}
        
        try:
            # Run agent with task instructions via stdin
            result = subprocess.run(
                cmd,
                cwd=workspace_path,
                env=run_env,
                input=task_instructions,
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

