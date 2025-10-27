#!/bin/bash
# Example: Run benchmark on full v0 dataset with sharding

set -e

# Check environment variables
if [ -z "$GITHUB_GIT_TOKEN" ]; then
    echo "Error: GITHUB_GIT_TOKEN environment variable is not set"
    exit 1
fi

# Configuration
RUNNER="auggie"
MODEL="claude-sonnet-4"
OUTPUT_DIR="output"
TOTAL_SHARDS=4
CONCURRENCY=2
TIMEOUT=1800

echo "Running Long-Context-Bench on full dataset (v0)"
echo "Runner: $RUNNER"
echo "Model: $MODEL"
echo "Shards: $TOTAL_SHARDS"
echo "Concurrency: $CONCURRENCY"
echo ""

# Run all shards in parallel
for shard in $(seq 0 $((TOTAL_SHARDS - 1))); do
    echo "Starting shard $((shard + 1))/$TOTAL_SHARDS..."

    long-context-bench pipeline \
        --runner "$RUNNER" \
        --model "$MODEL" \
        --output-dir "$OUTPUT_DIR" \
        --timeout "$TIMEOUT" \
        --concurrency "$CONCURRENCY" \
        --total-shards "$TOTAL_SHARDS" \
        --shard-index "$shard" &
done

# Wait for all shards to complete
wait

echo ""
echo "All shards complete! Results saved to $OUTPUT_DIR"
echo ""
echo "View aggregate statistics:"
echo "  long-context-bench stats $OUTPUT_DIR"

