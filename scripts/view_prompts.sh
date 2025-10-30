#!/bin/bash
# View and compare template-based vs synthesized prompts

set -e

SAMPLES_DIR="${1:-output/samples/v0}"

if [ ! -d "$SAMPLES_DIR" ]; then
    echo "Error: Directory not found: $SAMPLES_DIR"
    echo "Usage: $0 [SAMPLES_DIR]"
    exit 1
fi

echo "================================================================================"
echo "PROMPT COMPARISON VIEWER"
echo "================================================================================"
echo "Samples directory: $SAMPLES_DIR"
echo ""

# Find all sample.json files
SAMPLES=$(find "$SAMPLES_DIR" -name "sample.json" | sort)
TOTAL=$(echo "$SAMPLES" | wc -l | tr -d ' ')

if [ -z "$SAMPLES" ]; then
    echo "No samples found in $SAMPLES_DIR"
    exit 1
fi

echo "Found $TOTAL samples"
echo ""

# Count how many have synthesized prompts
SYNTHESIZED_COUNT=0
for sample in $SAMPLES; do
    if jq -e '.synthesized_task_instructions != null' "$sample" > /dev/null 2>&1; then
        SYNTHESIZED_COUNT=$((SYNTHESIZED_COUNT + 1))
    fi
done

echo "Samples with synthesized prompts: $SYNTHESIZED_COUNT / $TOTAL"
echo ""

# Show first few samples
echo "================================================================================"
echo "SAMPLE PROMPTS (showing first 5)"
echo "================================================================================"
echo ""

COUNT=0
for sample in $SAMPLES; do
    COUNT=$((COUNT + 1))
    if [ $COUNT -gt 5 ]; then
        break
    fi
    
    PR_NUMBER=$(jq -r '.pr_number' "$sample")
    REPO=$(jq -r '.repo_url' "$sample" | sed 's|https://github.com/||' | sed 's|.git||')
    
    echo "--------------------------------------------------------------------------------"
    echo "[$COUNT] $REPO#$PR_NUMBER"
    echo "--------------------------------------------------------------------------------"
    
    # Template-based
    echo ""
    echo "📝 TEMPLATE-BASED:"
    TEMPLATE=$(jq -r '.task_instructions' "$sample")
    TEMPLATE_LEN=${#TEMPLATE}
    echo "$TEMPLATE"
    echo ""
    echo "Length: $TEMPLATE_LEN characters"
    
    # Synthesized (if available)
    if jq -e '.synthesized_task_instructions != null' "$sample" > /dev/null 2>&1; then
        echo ""
        echo "✨ SYNTHESIZED:"
        SYNTHESIZED=$(jq -r '.synthesized_task_instructions' "$sample")
        SYNTHESIZED_LEN=${#SYNTHESIZED}
        MODEL=$(jq -r '.synthesis_model' "$sample")
        echo "$SYNTHESIZED"
        echo ""
        echo "Length: $SYNTHESIZED_LEN characters"
        echo "Model: $MODEL"
        
        # Calculate reduction
        REDUCTION=$(echo "scale=1; 100 * (1 - $SYNTHESIZED_LEN / $TEMPLATE_LEN)" | bc)
        echo "Reduction: ${REDUCTION}%"
    else
        echo ""
        echo "⚠️  No synthesized prompt available"
        echo "   Run: long-context-bench sample --synthesize --force"
    fi
    
    echo ""
done

if [ $TOTAL -gt 5 ]; then
    echo "... and $((TOTAL - 5)) more samples"
    echo ""
fi

echo "================================================================================"
echo "SUMMARY"
echo "================================================================================"
echo "Total samples: $TOTAL"
echo "With synthesized prompts: $SYNTHESIZED_COUNT"
echo "Without synthesized prompts: $((TOTAL - SYNTHESIZED_COUNT))"
echo ""

if [ $SYNTHESIZED_COUNT -eq 0 ]; then
    echo "💡 To generate synthesized prompts, run:"
    echo "   long-context-bench sample $SAMPLES_DIR --synthesize --force"
    echo ""
fi

