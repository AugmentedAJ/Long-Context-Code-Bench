#!/usr/bin/env python3
"""
Pre-flight check for Long-Context-Bench runs.

Verifies:
- Dataset is valid and accessible
- Agent binaries are installed and working
- Authentication is configured
- Output directories are writable
"""

import json
import subprocess
import sys
from pathlib import Path


def check_dataset(dataset_path: Path) -> bool:
    """Check if dataset exists and is valid."""
    print(f"\n📊 Checking dataset: {dataset_path}")
    
    if not dataset_path.exists():
        print(f"  ❌ Dataset not found: {dataset_path}")
        return False
    
    try:
        with open(dataset_path) as f:
            urls = json.load(f)
        
        if not isinstance(urls, list):
            print(f"  ❌ Dataset is not a list")
            return False
        
        if len(urls) == 0:
            print(f"  ❌ Dataset is empty")
            return False
        
        print(f"  ✅ Dataset valid: {len(urls)} PRs")
        return True
    except Exception as e:
        print(f"  ❌ Failed to load dataset: {e}")
        return False


def check_agent(agent_name: str, version_flag: str = "--version") -> tuple[bool, str]:
    """Check if agent binary is installed and get version."""
    print(f"\n🤖 Checking agent: {agent_name}")
    
    try:
        result = subprocess.run(
            [agent_name, version_flag],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"  ✅ {agent_name} installed: {version}")
            return True, version
        else:
            print(f"  ❌ {agent_name} returned error code {result.returncode}")
            return False, ""
    except FileNotFoundError:
        print(f"  ❌ {agent_name} not found in PATH")
        return False, ""
    except Exception as e:
        print(f"  ❌ Failed to check {agent_name}: {e}")
        return False, ""


def check_auth_auggie() -> bool:
    """Check Auggie authentication."""
    print(f"\n🔐 Checking Auggie authentication")
    
    # Check if AUGMENT_API_TOKEN is set
    import os
    if os.environ.get("AUGMENT_API_TOKEN"):
        print(f"  ✅ AUGMENT_API_TOKEN is set")
        return True
    
    # Try to run a simple command to check OAuth
    try:
        result = subprocess.run(
            ["auggie", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            print(f"  ✅ Auggie OAuth appears to be configured")
            return True
        else:
            print(f"  ⚠️  Auggie may not be authenticated (run 'auggie login')")
            return False
    except Exception as e:
        print(f"  ❌ Failed to check Auggie auth: {e}")
        return False


def check_auth_claude() -> bool:
    """Check Claude Code authentication."""
    print(f"\n🔐 Checking Claude Code authentication")
    
    # Check if ANTHROPIC_API_KEY is set
    import os
    api_key_present = bool(os.environ.get("ANTHROPIC_API_KEY"))
    
    if api_key_present:
        print(f"  ✅ ANTHROPIC_API_KEY is set")
        return True
    
    # Try to run a simple command to check OAuth
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            print(f"  ✅ Claude Code OAuth appears to be configured")
            return True
        else:
            print(f"  ⚠️  Claude Code may not be authenticated (run 'claude setup-token')")
            return False
    except Exception as e:
        print(f"  ❌ Failed to check Claude Code auth: {e}")
        return False


def check_output_dir(output_dir: Path) -> bool:
    """Check if output directory is writable."""
    print(f"\n📁 Checking output directory: {output_dir}")
    
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        test_file = output_dir / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        print(f"  ✅ Output directory is writable")
        return True
    except Exception as e:
        print(f"  ❌ Output directory is not writable: {e}")
        return False


def main():
    print("=" * 80)
    print("Long-Context-Bench Pre-Flight Check")
    print("=" * 80)
    
    # Get repo root
    repo_root = Path(__file__).parent.parent
    
    # Check dataset
    dataset_path = repo_root / "data" / "elasticsearch_prs_50.json"
    dataset_ok = check_dataset(dataset_path)
    
    # Check agents
    auggie_ok, auggie_version = check_agent("auggie")
    claude_ok, claude_version = check_agent("claude")
    
    # Check authentication
    auggie_auth_ok = check_auth_auggie() if auggie_ok else False
    claude_auth_ok = check_auth_claude() if claude_ok else False
    
    # Check output directory
    output_dir = repo_root / "output"
    output_ok = check_output_dir(output_dir)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    all_ok = True
    
    print(f"\n📊 Dataset: {'✅' if dataset_ok else '❌'}")
    if not dataset_ok:
        all_ok = False
    
    print(f"\n🤖 Agents:")
    print(f"  Auggie: {'✅' if auggie_ok else '❌'} {auggie_version if auggie_ok else ''}")
    print(f"  Claude Code: {'✅' if claude_ok else '❌'} {claude_version if claude_ok else ''}")
    
    if not auggie_ok and not claude_ok:
        all_ok = False
        print(f"  ❌ No agents available")
    
    print(f"\n🔐 Authentication:")
    print(f"  Auggie: {'✅' if auggie_auth_ok else '⚠️ '}")
    print(f"  Claude Code: {'✅' if claude_auth_ok else '⚠️ '}")
    
    print(f"\n📁 Output: {'✅' if output_ok else '❌'}")
    if not output_ok:
        all_ok = False
    
    if all_ok:
        print("\n✅ All checks passed! Ready to run benchmark.")
        print("\nExample test run (1 PR):")
        print("  long-context-bench pipeline \\")
        print("    --pr-indices 0 \\")
        print("    --runner auggie \\")
        print("    --model claude-sonnet-4-20250514 \\")
        print("    --test-label v0-test")
        return 0
    else:
        print("\n❌ Some checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

