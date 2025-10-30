#!/bin/bash
# Run v0 benchmark: Auggie vs Claude Code, both using Sonnet 4.5
# This script runs the full v0 dataset (40 PRs with pre-synthesized prompts) with both agents
# Results are tagged with test_label="v0" and viewable in the web dashboard

set -e

# Configuration
AGENTS="auggie:sonnet4.5,claude-code:claude-sonnet-4-5"
TEST_LABEL="v0"
TIMEOUT=1200

echo "=========================================="
echo "Long-Context-Code-Bench v0 Comparison"
echo "=========================================="
echo ""
echo "Agents: Auggie (sonnet4.5) vs Claude Code (claude-sonnet-4-5)"
echo "Dataset: v0 (40 PRs with pre-synthesized prompts)"
echo "Test Label: $TEST_LABEL"
echo "Timeout: ${TIMEOUT}s per PR"
echo ""
echo "This will run both agents in parallel on all PRs."
echo "The pipeline will automatically use pre-synthesized prompts from data/samples/v0/"
echo "Results will be saved to output/ and viewable in the web dashboard."
echo ""

# Run the pipeline
python -m long_context_bench.cli pipeline-parallel \
    --agents "$AGENTS" \
    --test-label "$TEST_LABEL" \
    --timeout "$TIMEOUT"

echo ""
echo "=========================================="
echo "v0 Benchmark Complete!"
echo "=========================================="
echo ""
echo "To view results in the web dashboard:"
echo "  1. cd output/web"
echo "  2. npm install  (first time only)"
echo "  3. npm start"
echo "  4. Open http://localhost:3000 in your browser"
echo "  5. Filter by test label: $TEST_LABEL"
echo ""

