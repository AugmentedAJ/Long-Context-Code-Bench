#!/usr/bin/env python3
"""
Create a 'v0_valid' dataset by removing known issue numbers that 404 when treated as PRs.
This avoids GitHub API calls and lets main continue using v0 methodology.

Known issue numbers (from earlier curation):
  114968, 114962, 114956, 114947, 114941, 114926, 114902, 114893

Usage:
  python scripts/make_v0_valid_from_known_issues.py \
    --input data/elasticsearch_prs_50.json \
    --out data/elasticsearch_prs_50_v0_valid.json
"""

import argparse
import json
from pathlib import Path

KNOWN_ISSUES = {114968, 114962, 114956, 114947, 114941, 114926, 114902, 114893}

def parse_pr_number(url: str) -> int:
    return int(url.rstrip('/').split('/')[-1])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    inp = Path(args.input)
    out = Path(args.out)

    with open(inp) as f:
        urls = json.load(f)

    filtered = [u for u in urls if parse_pr_number(u) not in KNOWN_ISSUES]

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(filtered, f, indent=2)

    print(f"Input URLs:     {len(urls)}")
    print(f"Filtered URLs:  {len(filtered)}")
    removed = [n for n in (parse_pr_number(u) for u in urls) if n in KNOWN_ISSUES]
    print(f"Removed numbers: {sorted(set(removed))}")

if __name__ == '__main__':
    main()

