"""Utilities for streaming subprocess output."""

import sys
import time
import subprocess
from pathlib import Path
from typing import List, Optional

from long_context_bench.runners.asciinema_utils import (
    is_asciinema_available,
    wrap_command_with_asciinema,
)


def run_with_streaming(
    cmd: List[str],
    cwd: str,
    env: dict,
    timeout: int,
    stream_output: bool = False,
    enable_asciinema: bool = False,
    asciinema_output: Optional[Path] = None,
) -> tuple[int, str]:
    """Run a subprocess with optional real-time output streaming and asciinema recording.

    Args:
        cmd: Command to run
        cwd: Working directory
        env: Environment variables
        timeout: Timeout in seconds
        stream_output: Whether to stream output to console
        enable_asciinema: Whether to record session with asciinema
        asciinema_output: Path to save asciinema recording (required if enable_asciinema=True)

    Returns:
        Tuple of (returncode, stdout)

    Raises:
        subprocess.TimeoutExpired: If timeout is exceeded
        ValueError: If enable_asciinema=True but asciinema_output is None
    """
    # Wrap command with asciinema if requested
    actual_cmd = cmd
    if enable_asciinema:
        if asciinema_output is None:
            raise ValueError("asciinema_output must be provided when enable_asciinema=True")

        if is_asciinema_available():
            actual_cmd = wrap_command_with_asciinema(cmd, asciinema_output, env)
        else:
            # Log warning but continue without recording
            from rich.console import Console
            console = Console()
            console.print("[yellow]Warning: asciinema not found, skipping session recording[/yellow]")

    if not stream_output:
        # Non-streaming mode: capture output
        result = subprocess.run(
            actual_cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            timeout=timeout,
            text=True,
        )
        return result.returncode, result.stdout
    
    # Streaming mode: stream output line by line
    from rich.console import Console
    console = Console()

    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
    console.print("[dim]" + "=" * 80 + "[/dim]")

    # Start process with pipes for streaming
    process = subprocess.Popen(
        actual_cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Merge stderr into stdout
        text=True,
        bufsize=1,  # Line buffered
    )
    
    # Collect output while streaming to console
    stdout_lines = []
    try:
        # Stream output line by line with timeout
        start = time.time()
        while True:
            # Check timeout
            if time.time() - start > timeout:
                process.kill()
                raise subprocess.TimeoutExpired(cmd, timeout)
            
            # Read line with timeout
            line = process.stdout.readline()
            if not line:
                # Process finished
                if process.poll() is not None:
                    break
                continue
            
            # Stream to console and collect
            sys.stdout.write(line)
            sys.stdout.flush()
            stdout_lines.append(line)
        
        # Wait for process to complete
        returncode = process.wait()
        
    except subprocess.TimeoutExpired:
        process.kill()
        raise

    stdout = "".join(stdout_lines)

    console.print("[dim]" + "=" * 80 + "[/dim]")

    # Note: When using asciinema, the stdout will contain asciinema's output wrapper
    # The actual agent output is recorded in the .cast file
    return returncode, stdout

