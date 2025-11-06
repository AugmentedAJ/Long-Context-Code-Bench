#!/bin/bash
# Archive the full output directory with logs for team debugging
# Creates a compressed archive suitable for sharing via S3/Drive/Dropbox

set -e

# Configuration
OUTPUT_DIR="${1:-output}"
ARCHIVE_NAME="${2:-long-context-bench-v0-full-output}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE_FILE="${ARCHIVE_NAME}_${TIMESTAMP}.tar.gz"

echo "📦 Archiving Full Output Directory"
echo "=============================================="
echo "Output directory: $OUTPUT_DIR"
echo "Archive name: $ARCHIVE_FILE"
echo ""

# Check if output directory exists
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "❌ Error: Output directory '$OUTPUT_DIR' not found"
    exit 1
fi

# Calculate size before compression
echo "📊 Calculating directory size..."
OUTPUT_SIZE=$(du -sh "$OUTPUT_DIR" | cut -f1)
echo "Output directory size: $OUTPUT_SIZE"
echo ""

# Create archive
echo "🗜️  Creating compressed archive..."
echo "This may take a few minutes for large datasets..."
tar -czf "$ARCHIVE_FILE" "$OUTPUT_DIR/"

# Calculate archive size
ARCHIVE_SIZE=$(du -sh "$ARCHIVE_FILE" | cut -f1)
COMPRESSION_RATIO=$(echo "scale=1; $(du -sk "$ARCHIVE_FILE" | cut -f1) * 100 / $(du -sk "$OUTPUT_DIR" | cut -f1)" | bc)

echo ""
echo "✅ Archive created successfully!"
echo "=============================================="
echo "Archive file: $ARCHIVE_FILE"
echo "Original size: $OUTPUT_SIZE"
echo "Compressed size: $ARCHIVE_SIZE"
echo "Compression ratio: ${COMPRESSION_RATIO}%"
echo ""

# Count files
EDIT_COUNT=$(find "$OUTPUT_DIR/edits" -name "edit.json" 2>/dev/null | wc -l | tr -d ' ')
JUDGE_COUNT=$(find "$OUTPUT_DIR/judges" -name "judge.json" 2>/dev/null | wc -l | tr -d ' ')
SAMPLE_COUNT=$(find "$OUTPUT_DIR/samples" -name "sample.json" 2>/dev/null | wc -l | tr -d ' ')
LOG_COUNT=$(find "$OUTPUT_DIR/edits" -name "logs.jsonl" 2>/dev/null | wc -l | tr -d ' ')

echo "📊 Contents:"
echo "  - Edit results: $EDIT_COUNT"
echo "  - Judge evaluations: $JUDGE_COUNT"
echo "  - Sample tasks: $SAMPLE_COUNT"
echo "  - Log files: $LOG_COUNT"
echo ""

# Provide sharing instructions
echo "📤 Sharing Options:"
echo "=============================================="
echo ""
echo "Option 1: AWS S3 (Recommended for teams)"
echo "  aws s3 cp $ARCHIVE_FILE s3://your-bucket/benchmarks/"
echo "  aws s3 presign s3://your-bucket/benchmarks/$ARCHIVE_FILE --expires-in 604800"
echo ""
echo "Option 2: Google Drive"
echo "  # Install gdrive: https://github.com/prasmussen/gdrive"
echo "  gdrive upload $ARCHIVE_FILE"
echo ""
echo "Option 3: Dropbox"
echo "  # Install Dropbox CLI: https://www.dropbox.com/install-linux"
echo "  dropbox upload $ARCHIVE_FILE"
echo ""
echo "Option 4: GitHub Release"
echo "  gh release create v0-full-results $ARCHIVE_FILE \\"
echo "    --title 'v0 Full Results with Logs' \\"
echo "    --notes 'For team debugging. Includes full agent logs.'"
echo ""
echo "Option 5: Internal file server"
echo "  cp $ARCHIVE_FILE /mnt/shared/benchmarks/"
echo ""

# Create extraction instructions
INSTRUCTIONS_FILE="${ARCHIVE_NAME}_${TIMESTAMP}_INSTRUCTIONS.txt"
cat > "$INSTRUCTIONS_FILE" << EOF
Long-Context-Code-Bench v0 - Full Results with Logs
====================================================

Archive: $ARCHIVE_FILE
Created: $(date)
Size: $ARCHIVE_SIZE (compressed from $OUTPUT_SIZE)

Contents:
- $EDIT_COUNT edit results
- $JUDGE_COUNT judge evaluations
- $SAMPLE_COUNT sample tasks
- $LOG_COUNT log files

Quick Start
-----------

1. Clone the benchmark repository:
   git clone git@github.com:AugmentedAJ/Long-Context-Code-Bench.git
   cd Long-Context-Code-Bench

2. Download this archive to the repository root

3. Extract the archive:
   tar -xzf $ARCHIVE_FILE

4. Start the web dashboard:
   cd output/web
   npm install
   npm start

5. Open in browser:
   http://localhost:3000

Features
--------

✅ Full agent logs for every task
✅ Complete diffs (ground truth vs agent)
✅ Judge evaluations and rationale
✅ Interactive web dashboard
✅ Downloadable logs per task
✅ Side-by-side diff comparison

Debugging Tips
--------------

- Click any task in the results table to see details
- Use "Download Logs" button to save logs locally
- Filter logs by stdout/stderr using checkboxes
- Compare diffs side-by-side
- Check judge rationale for scoring details

File Structure
--------------

output/
├── web/              # Web dashboard (start here)
├── edits/            # Agent submissions with logs
├── judges/           # Judge evaluations
├── samples/          # Task descriptions
├── summaries/        # Aggregate statistics
└── index.json        # Master index

Need Help?
----------

- Documentation: See DISTRIBUTION.md in the repo
- Issues: https://github.com/AugmentedAJ/Long-Context-Code-Bench/issues
- Contact: [Your contact info]

EOF

echo "📝 Created extraction instructions: $INSTRUCTIONS_FILE"
echo ""
echo "🎉 Done! Archive is ready to share with your team."
echo ""
echo "⚠️  Security Note:"
echo "This archive contains full agent logs which may include:"
echo "  - Internal file paths"
echo "  - Error messages and stack traces"
echo "  - Agent reasoning and prompts"
echo ""
echo "Share only with trusted team members via secure channels."
echo ""

