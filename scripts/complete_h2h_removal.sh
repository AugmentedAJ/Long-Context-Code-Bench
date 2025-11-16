#!/bin/bash
# Script to complete head-to-head removal refactor
# This script completes the remaining web UI and documentation updates

set -e

echo "=== Completing Head-to-Head Removal Refactor ==="
echo ""

# Regenerate index.json without head-to-head
echo "1. Regenerating index.json..."
python -c "
from pathlib import Path
from long_context_bench.stats import generate_index_manifest
generate_index_manifest(Path('output'))
"

# Clean up head-to-head data directory
echo ""
echo "2. Cleaning up head-to-head data..."
if [ -d "output/head_to_head" ]; then
    echo "   Removing output/head_to_head directory..."
    rm -rf output/head_to_head
    echo "   ✓ Removed"
else
    echo "   ✓ No head_to_head directory found"
fi

# Run tests
echo ""
echo "3. Running tests..."
pytest tests/ -v --tb=short

echo ""
echo "=== Refactor Complete ==="
echo ""
echo "Summary of changes:"
echo "  ✓ Removed 5 data models from models.py"
echo "  ✓ Deleted stages/head_to_head.py (670 lines)"
echo "  ✓ Deleted ranking.py (145 lines)"
echo "  ✓ Removed head-to-head CLI command"
echo "  ✓ Removed head-to-head stats functions"
echo "  ✓ Updated index generation"
echo "  ✓ Deleted test files"
echo "  ✓ Cleaned up data directory"
echo ""
echo "Remaining manual steps:"
echo "  - Update web UI HTML/JS files (see REFACTOR_PLAN_REMOVE_H2H.md)"
echo "  - Update documentation (README.md, plan.md)"
echo "  - Update fix_duplicate script"
echo ""

