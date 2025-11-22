#!/usr/bin/env python3
"""Add ground_truth_patch field to existing judge.json files."""

import json
import sys
from pathlib import Path
import git
from rich.console import Console

console = Console()

def get_ground_truth_diff(repo_url: str, base_commit: str, head_commit: str, cache_dir: Path) -> str:
    """Get ground truth diff from base to head commit."""
    # Extract repo name from URL
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    owner = repo_url.rstrip("/").split("/")[-2]
    cache_path = cache_dir / f"{owner}_{repo_name}"
    
    if cache_path.exists():
        console.print(f"  Using cached repository")
        repo = git.Repo(cache_path)
        try:
            # Shallow fetch just the required commits
            repo.git.fetch("--no-tags", "--depth=1", "origin", base_commit)
            repo.git.fetch("--no-tags", "--depth=1", "origin", head_commit)
        except Exception as e:
            console.print(f"  [yellow]Warning: Failed to shallow-fetch commits: {e}[/yellow]")
    else:
        console.print(f"  Cloning repository...")
        cache_path.mkdir(parents=True, exist_ok=True)
        repo = git.Repo.clone_from(repo_url, cache_path)
        try:
            repo.git.fetch("origin", base_commit)
            repo.git.fetch("origin", head_commit)
        except Exception as e:
            console.print(f"  [yellow]Warning: Failed to fetch commits: {e}[/yellow]")
    
    diff = repo.git.diff(base_commit, head_commit, unified=True)
    return diff


def main():
    judge_run_dir = Path("output/judges/llm/claude-sonnet-4-5/b7f00db5")
    cache_dir = Path(".repo_cache")
    cache_dir.mkdir(exist_ok=True)
    
    if not judge_run_dir.exists():
        console.print(f"[red]Judge run directory not found: {judge_run_dir}[/red]")
        sys.exit(1)
    
    # Find all judge.json files
    judge_files = list(judge_run_dir.glob("*/judge.json"))
    console.print(f"[bold]Found {len(judge_files)} judge files to update[/bold]")
    
    updated = 0
    skipped = 0
    errors = 0
    
    for judge_file in judge_files:
        pr_id = judge_file.parent.name
        
        try:
            # Load existing judge data
            with open(judge_file) as f:
                judge_data = json.load(f)
            
            # Check if ground_truth_patch already exists
            if judge_data.get("ground_truth_patch") is not None:
                console.print(f"[yellow]⊙ Skipping {pr_id} (already has ground_truth_patch)[/yellow]")
                skipped += 1
                continue
            
            console.print(f"[cyan]Processing {pr_id}...[/cyan]")
            
            # Get ground truth diff
            ground_truth_diff = get_ground_truth_diff(
                judge_data["repo_url"],
                judge_data["base_commit"],
                judge_data["head_commit"],
                cache_dir
            )
            
            # Add ground_truth_patch field
            judge_data["ground_truth_patch"] = ground_truth_diff
            
            # Write updated judge.json
            with open(judge_file, "w") as f:
                json.dump(judge_data, f, indent=2)
            
            console.print(f"[green]✓ Updated {pr_id}[/green]")
            updated += 1
            
        except Exception as e:
            console.print(f"[red]✗ Failed to update {pr_id}: {e}[/red]")
            errors += 1
    
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Updated: {updated}")
    console.print(f"  Skipped: {skipped}")
    console.print(f"  Errors: {errors}")


if __name__ == "__main__":
    main()

