#!/bin/bash
# Regenerate head-to-head evaluation data for all PRs

set -e

# Configuration
TEST_LABEL="v0"
JUDGE_MODEL="openai/claude-sonnet-4-5-20250929"
OUTPUT_DIR="output"

echo "=== Regenerating Head-to-Head Data ==="
echo "Test label: $TEST_LABEL"
echo "Judge model: $JUDGE_MODEL"
echo ""

# Get list of all PR numbers from cross-agent analysis
PR_NUMBERS=$(ls ${OUTPUT_DIR}/cross_agent_analysis/ | grep -o 'pr[0-9]*' | sed 's/pr//' | sort -u)
TOTAL_PRS=$(echo "$PR_NUMBERS" | wc -l | tr -d ' ')

echo "Found $TOTAL_PRS PRs to process"
echo ""

# Counter
COUNT=0

# Process each PR
for PR_NUM in $PR_NUMBERS; do
    COUNT=$((COUNT + 1))
    echo "[$COUNT/$TOTAL_PRS] Processing PR $PR_NUM..."
    
    # Run head-to-head evaluation
    long-context-bench head-to-head-pr \
        --pr-number "$PR_NUM" \
        --test-label "$TEST_LABEL" \
        --judge-model "$JUDGE_MODEL" \
        --output-dir "$OUTPUT_DIR" \
        --cache-dir ".repo_cache" \
        2>&1 | grep -E "✓|⊙|Warning|Error|Found|Judging" || true
    
    echo ""
done

echo "=== Head-to-Head Regeneration Complete ==="
echo ""
echo "Summary:"
echo "  Total PRs processed: $TOTAL_PRS"
echo "  Output directory: ${OUTPUT_DIR}/head_to_head/"
echo ""

# Count results
RESULT_COUNT=$(ls ${OUTPUT_DIR}/head_to_head/*.json 2>/dev/null | wc -l | tr -d ' ')
echo "  Head-to-head results generated: $RESULT_COUNT"
echo ""

