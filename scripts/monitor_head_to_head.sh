#!/bin/bash
# Monitor head-to-head regeneration progress

OUTPUT_DIR="output"

echo "=== Head-to-Head Regeneration Monitor ==="
echo ""

# Count completed PRs
COMPLETED=$(ls ${OUTPUT_DIR}/head_to_head/*.json 2>/dev/null | wc -l | tr -d ' ')
TOTAL=40

echo "Progress: $COMPLETED / $TOTAL PRs completed"
echo ""

# Show recent completions
if [ $COMPLETED -gt 0 ]; then
    echo "Recent completions:"
    ls -lt ${OUTPUT_DIR}/head_to_head/*.json 2>/dev/null | head -5 | awk '{print "  " $9}' | xargs -I {} basename {}
    echo ""
fi

# Check if process is running
if ps aux | grep -q "[l]ong-context-bench head-to-head"; then
    echo "Status: ✓ Running"
    CURRENT_PR=$(ps aux | grep "[l]ong-context-bench head-to-head" | grep -o "pr-number [0-9]*" | awk '{print $2}' | head -1)
    if [ -n "$CURRENT_PR" ]; then
        echo "Current PR: $CURRENT_PR"
    fi
else
    echo "Status: ✗ Not running"
fi

echo ""

# Estimate time remaining
if [ $COMPLETED -gt 0 ]; then
    REMAINING=$((TOTAL - COMPLETED))
    # Rough estimate: 5 minutes per PR (3 agents × 3 pairs × 30 seconds)
    EST_MINUTES=$((REMAINING * 5))
    EST_HOURS=$((EST_MINUTES / 60))
    EST_MINS=$((EST_MINUTES % 60))
    echo "Estimated time remaining: ${EST_HOURS}h ${EST_MINS}m"
fi

echo ""
echo "To watch live progress:"
echo "  tail -f output/head_to_head/logs/pr*/logs_readable.txt"

