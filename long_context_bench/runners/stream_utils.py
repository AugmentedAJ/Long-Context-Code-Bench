"""Utilities for streaming subprocess output.

This module provides helpers for running subprocesses in both regular
pipe-based mode and in a pseudo-terminal (PTY).
"""

import os
import select
import sys
import time
import subprocess
from typing import List


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
    # Always capture stdout for logging purposes, even when streaming
    stdout_lines: List[str] = []
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

            # Always collect output for logs
            stdout_lines.append(line)

            # Stream to console if enabled
            if stream_output:
                sys.stdout.write(line)
                sys.stdout.flush()

        # Wait for process to complete
        returncode = process.wait()

    except subprocess.TimeoutExpired:
        process.kill()
        raise

    stdout = "".join(stdout_lines)

    console.print("[dim]" + "=" * 80 + "[/dim]")

    return returncode, stdout

def run_with_pty(
    cmd: List[str],
    cwd: str,
    env: dict,
    timeout: int,
    stream_output: bool = False,
) -> tuple[int, str]:
    """Run a subprocess attached to a pseudo-terminal (PTY).

    This is primarily used for tools like Claude Code that expect a real TTY
    and may enable raw mode on stdin. By running the subprocess under a PTY,
    we present a TTY-like interface while still capturing all output.

    On non-Unix platforms where PTY support is unavailable, this function
    transparently falls back to :func:`run_with_streaming`.
    """
    try:
        import pty  # type: ignore
    except ImportError:
        # PTY not available (e.g., Windows); fall back to regular execution.
        return run_with_streaming(
            cmd=cmd,
            cwd=cwd,
            env=env,
            timeout=timeout,
            stream_output=stream_output,
        )

    master_fd, slave_fd = pty.openpty()
    # Always capture stdout for logging purposes, even when streaming
    stdout_chunks: List[str] = []
    start = time.time()

    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            text=False,  # We read and decode manually from the PTY
            bufsize=0,
            close_fds=True,
        )
        os.close(slave_fd)

        while True:
            # Timeout check
            if time.time() - start > timeout:
                process.kill()
                raise subprocess.TimeoutExpired(cmd, timeout)

            # Wait for data or process exit
            rlist, _, _ = select.select([master_fd], [], [], 0.1)
            if master_fd in rlist:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    break
                if not data:
                    # EOF from child
                    break
                text = data.decode("utf-8", errors="ignore")
                # Always collect output for logs
                stdout_chunks.append(text)
                # Stream to console if enabled
                if stream_output:
                    sys.stdout.write(text)
                    sys.stdout.flush()

            if process.poll() is not None:
                # Child has exited; drain any remaining data
                while True:
                    try:
                        data = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if not data:
                        break
                    text = data.decode("utf-8", errors="ignore")
                    # Always collect output for logs
                    stdout_chunks.append(text)
                    # Stream to console if enabled
                    if stream_output:
                        sys.stdout.write(text)
                        sys.stdout.flush()
                break

        returncode = process.wait()

    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass

    stdout = "".join(stdout_chunks)
    return returncode, stdout

