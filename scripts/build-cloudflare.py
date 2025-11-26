#!/usr/bin/env python3
"""
Build script for Cloudflare Pages deployment.

This script creates a static build of the Long-Context-Bench web UI
that can be deployed to Cloudflare Pages or any static hosting service.

Usage:
    python scripts/build-cloudflare.py output dist
    
    # Or via CLI:
    long-context-bench build-static output dist

The output directory structure:
    dist/
    ├── index.html
    ├── app.js
    ├── data-loader.js
    ├── charts.js
    ├── styles.css
    ├── index.json
    ├── summaries/
    │   └── {run_id}/summary.json
    ├── judges/
    │   └── llm/{model}/{judge_run_id}/{edit_run_id}/{pr_id}/judge.json
    ├── edits/
    │   └── {runner}/{model}/{edit_run_id}/{pr_id}/
    │       ├── edit_summary.json
    │       ├── edit.patch
    │       └── logs.jsonl
    └── samples/
        └── v1/{pr_id}/sample.json
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


def build_static(output_dir: Path, dist_dir: Path, verbose: bool = True) -> None:
    """Build static site for Cloudflare Pages deployment."""
    
    if not output_dir.exists():
        print(f"Error: Output directory '{output_dir}' does not exist")
        sys.exit(1)
    
    # Clean and create dist directory
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)
    
    if verbose:
        print(f"Building static site from '{output_dir}' to '{dist_dir}'...")
    
    # 1. Copy web static files (HTML, JS, CSS)
    web_src = output_dir / "web"
    if not web_src.exists():
        # Try the source web directory
        web_src = Path(__file__).parent.parent / "long_context_bench" / "web"
    
    static_files = ["index.html", "app.js", "data-loader.js", "charts.js", "styles.css"]
    for fname in static_files:
        src = web_src / fname
        if src.exists():
            shutil.copy2(src, dist_dir / fname)
            if verbose:
                print(f"  Copied {fname}")
    
    # 2. Copy index.json
    index_file = output_dir / "index.json"
    if index_file.exists():
        shutil.copy2(index_file, dist_dir / "index.json")
        if verbose:
            print(f"  Copied index.json")
    
    # 3. Copy summaries
    summaries_src = output_dir / "summaries"
    if summaries_src.exists():
        summaries_dst = dist_dir / "summaries"
        copy_tree_selective(summaries_src, summaries_dst, ["summary.json", "run_manifest.json"], verbose)
    
    # 4. Copy judges
    judges_src = output_dir / "judges"
    if judges_src.exists():
        judges_dst = dist_dir / "judges"
        copy_tree_selective(judges_src, judges_dst, ["judge.json", "judge_run_manifest.json"], verbose)
    
    # 5. Copy edits (summary, patch, logs)
    edits_src = output_dir / "edits"
    if edits_src.exists():
        edits_dst = dist_dir / "edits"
        copy_tree_selective(edits_src, edits_dst, 
                           ["edit_summary.json", "edit.patch", "logs.jsonl", "edit_run_manifest.json"], 
                           verbose)
    
    # 6. Copy samples
    samples_src = output_dir / "samples"
    if samples_src.exists():
        samples_dst = dist_dir / "samples"
        copy_tree_selective(samples_src, samples_dst, ["sample.json"], verbose)
    
    # Also check data/samples for v1 dataset
    data_samples = Path("data/samples")
    if data_samples.exists():
        samples_dst = dist_dir / "samples"
        copy_tree_selective(data_samples, samples_dst, ["sample.json"], verbose)
    
    # 7. Create _headers file for Cloudflare Pages (CORS, caching)
    headers_content = """/*
  Access-Control-Allow-Origin: *
  Cache-Control: public, max-age=3600

/*.json
  Content-Type: application/json
  Cache-Control: public, max-age=300

/*.jsonl
  Content-Type: application/x-ndjson
  Cache-Control: public, max-age=300
"""
    (dist_dir / "_headers").write_text(headers_content)
    if verbose:
        print(f"  Created _headers")
    
    # Count files
    file_count = sum(1 for _ in dist_dir.rglob("*") if _.is_file())
    if verbose:
        print(f"\n✓ Static build complete: {file_count} files in '{dist_dir}'")
        print(f"\nTo deploy to Cloudflare Pages:")
        print(f"  1. Push to GitHub and connect repo to Cloudflare Pages")
        print(f"  2. Set build command: python scripts/build-cloudflare.py output dist")
        print(f"  3. Set output directory: dist")
        print(f"\nOr deploy directly with Wrangler:")
        print(f"  npx wrangler pages deploy {dist_dir}")


def copy_tree_selective(src: Path, dst: Path, patterns: list, verbose: bool) -> None:
    """Copy directory tree, only including files matching patterns."""
    copied = 0
    for src_file in src.rglob("*"):
        if src_file.is_file() and src_file.name in patterns:
            rel_path = src_file.relative_to(src)
            dst_file = dst / rel_path
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            copied += 1
    if verbose and copied > 0:
        print(f"  Copied {copied} files from {src.name}/")


def main():
    parser = argparse.ArgumentParser(description="Build static site for Cloudflare Pages")
    parser.add_argument("output_dir", type=Path, help="Source output directory (e.g., 'output')")
    parser.add_argument("dist_dir", type=Path, nargs="?", default=Path("dist"), 
                        help="Destination directory (default: 'dist')")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")
    
    args = parser.parse_args()
    build_static(args.output_dir, args.dist_dir, verbose=not args.quiet)


if __name__ == "__main__":
    main()

