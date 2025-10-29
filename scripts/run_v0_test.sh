#!/bin/bash
# Test run for v0 benchmark: 1 PR with both Auggie and Claude Code (Sonnet 4.5)

set -e  # Exit on error

echo "=========================================="
echo "Long-Context-Bench v0 Test Run"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Dataset: v0 (42 validated PRs)"
echo "  Test PRs: 1 (index 0)"
echo "  Agents: Auggie + Claude Code"
echo "  Model: Claude Sonnet 4.5"
echo "  Test Label: v0-test"
echo ""

# Check for GitHub token
if [ -z "$GITHUB_GIT_TOKEN" ]; then
    echo "⚠️  WARNING: GITHUB_GIT_TOKEN is not set!"
    echo "   You may hit GitHub API rate limits (60 requests/hour)."
    echo "   Set GITHUB_GIT_TOKEN to get 5,000 requests/hour."
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting. Please set GITHUB_GIT_TOKEN and try again."
        exit 1
    fi
else
    echo "✅ GITHUB_GIT_TOKEN is set"
fi
echo ""

# Run pre-flight check
echo "Running pre-flight check..."
python scripts/preflight_check.py
if [ $? -ne 0 ]; then
    echo "Pre-flight check failed. Exiting."
    exit 1
fi

echo ""
echo "=========================================="
echo "Test 1: Auggie with Sonnet 4.5"
echo "=========================================="
echo ""

long-context-bench pipeline \
  --pr-indices 0 \
  --runner auggie \
  --model sonnet4.5 \
  --test-label v0-test \
  --timeout 1800

echo ""
echo "=========================================="
echo "Test 2: Claude Code with Sonnet 4.5"
echo "=========================================="
echo ""

long-context-bench pipeline \
  --pr-indices 0 \
  --runner claude-code \
  --model claude-sonnet-4-20250514 \
  --test-label v0-test \
  --timeout 1800

echo ""
echo "=========================================="
echo "Test Complete!"
echo "=========================================="
echo ""
echo "Results saved to:"
echo "  output/edits/auggie/sonnet4.5/"
echo "  output/edits/claude-code/claude-sonnet-4-20250514/"
echo ""
echo "Logs available at:"
echo "  output/edits/auggie/sonnet4.5/*/elastic_elasticsearch_pr*/logs.jsonl"
echo "  output/edits/auggie/sonnet4.5/*/elastic_elasticsearch_pr*/logs_readable.txt"
echo "  output/edits/claude-code/claude-sonnet-4-20250514/*/elastic_elasticsearch_pr*/logs.jsonl"
echo "  output/edits/claude-code/claude-sonnet-4-20250514/*/elastic_elasticsearch_pr*/logs_readable.txt"
echo ""
echo "To view results:"
echo "  cat output/edits/auggie/sonnet4.5/*/elastic_elasticsearch_pr*/edit_summary.json"
echo "  cat output/edits/claude-code/claude-sonnet-4-20250514/*/elastic_elasticsearch_pr*/edit_summary.json"

