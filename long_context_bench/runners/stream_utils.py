"""Utilities for streaming subprocess output."""

import sys
import time
import subprocess
from typing import List, Optional


def run_with_streaming(
    cmd: List[str],
    cwd: str,
    env: dict,
    timeout: int,
    stream_output: bool = False,
) -> tuple[int, str]:
    """Run a subprocess with optional real-time output streaming.
    
    Args:
        cmd: Command to run
        cwd: Working directory
        env: Environment variables
        timeout: Timeout in seconds
        stream_output: Whether to stream output to console
        
    Returns:
        Tuple of (returncode, stdout)
        
    Raises:
        subprocess.TimeoutExpired: If timeout is exceeded
    """
    if not stream_output:
        # Non-streaming mode: capture output
        result = subprocess.run(
            cmd,
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
        cmd,
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
    
    return returncode, stdout

