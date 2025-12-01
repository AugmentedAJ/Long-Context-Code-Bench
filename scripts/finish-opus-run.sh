#!/bin/bash
# Finish the opus4.5 run by completing the 4 missing PRs

set -e

FIRST_RUN="6a6b1b4b"
SECOND_RUN="87030b08"
OUTPUT_DIR="output/auggie/opus4.5"

# Delete the duplicate second run
echo "Deleting duplicate run $SECOND_RUN..."
rm -rf "$OUTPUT_DIR/$SECOND_RUN"

# Missing PRs
MISSING_PRS=(
  elastic_elasticsearch_pr134428
  elastic_elasticsearch_pr4229
  elastic_elasticsearch_pr4422
  elastic_elasticsearch_pr4425
)

echo "Running ${#MISSING_PRS[@]} missing PRs..."

for pr in "${MISSING_PRS[@]}"; do
  echo ""
  echo "=== Running $pr ==="
  
  # Run the edit
  long-context-bench edit "data/samples/v1/$pr" \
    --runner auggie \
    --model opus4.5 \
    --output-dir output
  
  # Find the new run directory (most recent one that's not the first run)
  NEW_RUN=$(ls -t "$OUTPUT_DIR" | grep -v "$FIRST_RUN" | head -1)
  
  if [ -n "$NEW_RUN" ] && [ -d "$OUTPUT_DIR/$NEW_RUN/$pr" ]; then
    echo "Moving $pr from $NEW_RUN to $FIRST_RUN..."
    mv "$OUTPUT_DIR/$NEW_RUN/$pr" "$OUTPUT_DIR/$FIRST_RUN/"
    
    # Clean up the empty run directory
    rmdir "$OUTPUT_DIR/$NEW_RUN" 2>/dev/null || rm -rf "$OUTPUT_DIR/$NEW_RUN"
  fi
done

echo ""
echo "=== Done! ==="
echo "Total PRs in $FIRST_RUN: $(ls "$OUTPUT_DIR/$FIRST_RUN" | grep -c elastic)"

