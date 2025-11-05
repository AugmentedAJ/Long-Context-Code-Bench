"""Utilities for recording agent sessions with asciinema."""

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional


def is_asciinema_available() -> bool:
    """Check if asciinema is installed and available.
    
    Returns:
        True if asciinema is available, False otherwise
    """
    return shutil.which("asciinema") is not None


def wrap_command_with_asciinema(
    cmd: List[str],
    output_file: Path,
    env: Optional[dict] = None,
) -> List[str]:
    """Wrap a command with asciinema recording.
    
    Args:
        cmd: Original command to wrap
        output_file: Path to save the recording (.cast file)
        env: Optional environment variables (passed through)
        
    Returns:
        New command list that wraps the original with asciinema rec
        
    Example:
        >>> wrap_command_with_asciinema(["auggie", "--print"], Path("session.cast"))
        ["asciinema", "rec", "-c", "auggie --print", "session.cast"]
    """
    # Convert command list to shell-escaped string
    # We need to properly quote arguments that contain spaces or special chars
    import shlex
    cmd_str = " ".join(shlex.quote(arg) for arg in cmd)
    
    # Build asciinema command
    # -c: command to record
    # --overwrite: overwrite existing file if present
    # --quiet: don't print recording info
    asciinema_cmd = [
        "asciinema",
        "rec",
        "--overwrite",
        "--quiet",
        "-c", cmd_str,
        str(output_file),
    ]
    
    return asciinema_cmd


def get_recording_path(logs_path: Path) -> Path:
    """Get the path for the asciinema recording file.
    
    The recording is stored alongside logs.jsonl in the same directory.
    
    Args:
        logs_path: Path to logs.jsonl file
        
    Returns:
        Path to session.cast file
        
    Example:
        >>> get_recording_path(Path("output/edits/auggie/model/run/pr/logs.jsonl"))
        Path("output/edits/auggie/model/run/pr/session.cast")
    """
    return logs_path.parent / "session.cast"

