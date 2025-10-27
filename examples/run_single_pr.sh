#!/bin/bash
# Example: Run benchmark on a single PR by number

set -e

# Check environment variables
if [ -z "$GITHUB_GIT_TOKEN" ]; then
    echo "Error: GITHUB_GIT_TOKEN environment variable is not set"
    exit 1
fi

# Configuration
PR_NUMBER="115001"
RUNNER="auggie"
MODEL="claude-sonnet-4"
OUTPUT_DIR="output"

echo "Running Long-Context-Bench on single PR"
echo "PR Number: $PR_NUMBER"
echo "Runner: $RUNNER"
echo "Model: $MODEL"
echo ""

# Run pipeline
long-context-bench pipeline \
    --runner "$RUNNER" \
    --model "$MODEL" \
    --output-dir "$OUTPUT_DIR" \
    --pr-numbers "$PR_NUMBER"

echo ""
echo "Pipeline complete! Results saved to $OUTPUT_DIR"
echo ""
echo "View statistics:"
echo "  long-context-bench stats $OUTPUT_DIR"

