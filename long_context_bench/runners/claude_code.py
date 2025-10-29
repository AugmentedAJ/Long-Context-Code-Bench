"""Claude Code runner adapter."""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict

from long_context_bench.runners.base import RunnerAdapter, RunnerResult


class ClaudeCodeAdapter(RunnerAdapter):
    """Adapter for Claude Code CLI agent.
    
    Claude Code is Anthropic's command-line coding agent.
    Docs: https://www.anthropic.com/engineering/claude-code-best-practices
    """
    
    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
        logs_path: Path,
        env: Optional[Dict[str, str]] = None,
    ) -> RunnerResult:
        """Run Claude Code on a task.

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

        # Claude Code uses `claude` command with -p flag for headless mode
        cmd = [
            self.agent_binary or "claude",
            "-p",  # Print mode (non-interactive)
            task_instructions,  # Task prompt
            "--output-format", "stream-json",  # Structured JSON output
            "--verbose",  # Required when using stream-json with -p
        ]

        # Add model if specified
        if self.model:
            cmd.extend(["--model", self.model])

        # Add allowed tools for non-interactive execution
        # This allows file edits and git commits without prompts
        cmd.extend([
            "--allowedTools", "Edit Bash(git:*)",  # Allow file edits and git commands
        ])

        # Prepare environment
        run_env = env.copy() if env else {}

        # Determine auth mode for Claude Code
        # LCB_CLAUDE_AUTH can be: 'auto' (default), 'subscription', or 'api-key'
        auth_mode = (run_env.get("LCB_CLAUDE_AUTH") or os.environ.get("LCB_CLAUDE_AUTH") or "auto").strip().lower()
        if auth_mode not in {"auto", "subscription", "api-key"}:
            auth_mode = "auto"

        api_key_present = bool(run_env.get("ANTHROPIC_API_KEY"))
        used_auth = "api-key" if (auth_mode == "api-key" or (auth_mode == "auto" and api_key_present)) else "subscription"

        # Enforce selected auth mode by shaping environment
        if used_auth == "subscription":
            # Remove Anthropic API env vars to force Claude subscription token usage
            for k in list(run_env.keys()):
                if k.upper().startswith("ANTHROPIC_"):
                    run_env.pop(k, None)
        else:
            # api-key path: leave env as-is; optionally warn if key missing
            if not api_key_present:
                print("  [warning] LCB_CLAUDE_AUTH=api-key but ANTHROPIC_API_KEY is not set; attempting run which will likely fail")

        # Emit a clear stdout line and write an auth_info record into logs
        print(f"  Claude auth: {used_auth} (mode={auth_mode}, ANTHROPIC_API_KEY={'present' if api_key_present else 'absent'})")
        try:
            # Write auth info early
            with open(logs_path, "a") as f:
                f.write(json.dumps({
                    "timestamp": time.time(),
                    "event": "auth_info",
                    "auth_mode": auth_mode,
                    "used_auth": used_auth,
                    "anthropic_api_key_present": api_key_present,
                }) + "\n")

            # Run agent with timeout
            result = subprocess.run(
                cmd,
                cwd=workspace_path,
                env=run_env,
                capture_output=True,
                timeout=self.timeout,
                text=True,
            )

            # Write run logs
            with open(logs_path, "a") as f:
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
        """Get Claude Code version."""
        try:
            result = subprocess.run(
                [self.agent_binary or "claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

