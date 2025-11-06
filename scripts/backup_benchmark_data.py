#!/usr/bin/env python3
"""
Backup all benchmark data to a zip file.

This script packages:
- All sample data (data/samples/)
- All edit runs (output/edits/)
- All judge results (output/judges/)
- All summaries (output/summaries/)
- Cross-agent analysis results (output/cross_agent_analysis/)
- Web dashboard files (output/web/)
- Index manifest (output/index.json)
"""

import argparse
import zipfile
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()


def get_all_files(directory: Path) -> list[Path]:
    """Recursively get all files in a directory."""
    files = []
    if not directory.exists():
        return files
    
    for item in directory.rglob("*"):
        if item.is_file():
            # Skip node_modules and other large dependencies
            if "node_modules" in item.parts:
                continue
            files.append(item)
    
    return files


def create_backup(
    output_dir: Path,
    data_dir: Path,
    backup_file: Path,
    include_web: bool = True,
) -> None:
    """Create a backup zip file of all benchmark data.
    
    Args:
        output_dir: Output directory containing results (e.g., 'output/')
        data_dir: Data directory containing samples (e.g., 'data/')
        backup_file: Path to the backup zip file
        include_web: Whether to include web dashboard files
    """
    console.print(f"[cyan]Creating backup: {backup_file}[/cyan]")
    
    # Collect all files to backup
    files_to_backup = []
    
    # Samples
    samples_dir = data_dir / "samples"
    if samples_dir.exists():
        console.print(f"[cyan]Collecting samples from {samples_dir}...[/cyan]")
        files_to_backup.extend(get_all_files(samples_dir))
    
    # Output directory contents
    if output_dir.exists():
        # Edits
        edits_dir = output_dir / "edits"
        if edits_dir.exists():
            console.print(f"[cyan]Collecting edits from {edits_dir}...[/cyan]")
            files_to_backup.extend(get_all_files(edits_dir))
        
        # Judges
        judges_dir = output_dir / "judges"
        if judges_dir.exists():
            console.print(f"[cyan]Collecting judges from {judges_dir}...[/cyan]")
            files_to_backup.extend(get_all_files(judges_dir))
        
        # Summaries
        summaries_dir = output_dir / "summaries"
        if summaries_dir.exists():
            console.print(f"[cyan]Collecting summaries from {summaries_dir}...[/cyan]")
            files_to_backup.extend(get_all_files(summaries_dir))
        
        # Cross-agent analysis
        cross_agent_dir = output_dir / "cross_agent_analysis"
        if cross_agent_dir.exists():
            console.print(f"[cyan]Collecting cross-agent analysis from {cross_agent_dir}...[/cyan]")
            files_to_backup.extend(get_all_files(cross_agent_dir))
        
        # Samples (output/samples/ - symlinks or copies)
        output_samples_dir = output_dir / "samples"
        if output_samples_dir.exists():
            console.print(f"[cyan]Collecting output samples from {output_samples_dir}...[/cyan]")
            files_to_backup.extend(get_all_files(output_samples_dir))
        
        # Index manifest
        index_file = output_dir / "index.json"
        if index_file.exists():
            files_to_backup.append(index_file)
        
        # Web dashboard
        if include_web:
            web_dir = output_dir / "web"
            if web_dir.exists():
                console.print(f"[cyan]Collecting web dashboard from {web_dir}...[/cyan]")
                web_files = get_all_files(web_dir)
                # Filter out node_modules (already done in get_all_files)
                files_to_backup.extend(web_files)
    
    # Remove duplicates
    files_to_backup = list(set(files_to_backup))
    
    console.print(f"[green]Found {len(files_to_backup)} files to backup[/green]")
    
    # Create zip file
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Creating backup...", total=len(files_to_backup))
        
        with zipfile.ZipFile(backup_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in files_to_backup:
                # Determine archive name (relative to workspace root)
                if file_path.is_relative_to(output_dir):
                    arcname = f"output/{file_path.relative_to(output_dir)}"
                elif file_path.is_relative_to(data_dir):
                    arcname = f"data/{file_path.relative_to(data_dir)}"
                else:
                    arcname = str(file_path)
                
                zf.write(file_path, arcname)
                progress.advance(task)
    
    # Get file size
    size_mb = backup_file.stat().st_size / (1024 * 1024)
    console.print(f"[green]✓ Backup created: {backup_file} ({size_mb:.1f} MB)[/green]")


def main():
    parser = argparse.ArgumentParser(
        description="Backup all benchmark data to a zip file"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Output directory containing results (default: output/)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Data directory containing samples (default: data/)",
    )
    parser.add_argument(
        "--backup-file",
        type=Path,
        help="Path to backup zip file (default: long-context-bench-backup-YYYYMMDD_HHMMSS.zip)",
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Exclude web dashboard files from backup",
    )
    
    args = parser.parse_args()
    
    # Generate default backup filename if not provided
    if args.backup_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.backup_file = Path(f"long-context-bench-backup-{timestamp}.zip")
    
    create_backup(
        output_dir=args.output_dir,
        data_dir=args.data_dir,
        backup_file=args.backup_file,
        include_web=not args.no_web,
    )


if __name__ == "__main__":
    main()

