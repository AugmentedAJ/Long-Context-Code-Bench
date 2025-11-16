"""Tests for stream_utils helper functions.

These tests only exercise basic behavior (successful execution and
output capture). They do not depend on any external CLIs like Claude.
"""

import os
import sys
from pathlib import Path

from long_context_bench.runners.stream_utils import run_with_streaming, run_with_pty


def _python_echo_command(message: str) -> list[str]:
    """Build a cross-platform python -c command that prints a message."""

    return [
        sys.executable,
        "-c",
        f"print({message!r})",
    ]


def test_run_with_streaming_basic_capture(tmp_path: Path) -> None:
    cmd = _python_echo_command("hello-stream")
    code, out = run_with_streaming(
        cmd=cmd,
        cwd=str(tmp_path),
        env=os.environ.copy(),
        timeout=10,
        stream_output=False,
    )
    assert code == 0
    assert "hello-stream" in out


def test_run_with_pty_basic_capture(tmp_path: Path) -> None:
    cmd = _python_echo_command("hello-pty")
    code, out = run_with_pty(
        cmd=cmd,
        cwd=str(tmp_path),
        env=os.environ.copy(),
        timeout=10,
        stream_output=False,
    )
    # On platforms without PTY support, run_with_pty falls back to
    # run_with_streaming, so we only assert general behavior.
    assert code == 0
    assert "hello-pty" in out

