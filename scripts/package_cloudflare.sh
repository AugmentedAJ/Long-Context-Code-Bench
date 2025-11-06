#!/bin/bash
# Package Long-Context-Code-Bench results for Cloudflare Pages deployment
# Creates a static site package ready for drag-and-drop deployment

set -e

# Configuration
OUTPUT_DIR="${1:-output}"
PACKAGE_NAME="cloudflare-deploy"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PACKAGE_DIR="${PACKAGE_NAME}_${TIMESTAMP}"

echo "☁️  Packaging for Cloudflare Pages"
echo "===================================="
echo "Output directory: $OUTPUT_DIR"
echo "Package directory: $PACKAGE_DIR"
echo ""

# Create package directory
mkdir -p "$PACKAGE_DIR"

# Copy web app files (excluding node_modules and server.js)
echo "📋 Copying web app files..."
cp "$OUTPUT_DIR/web"/*.html "$PACKAGE_DIR/" 2>/dev/null || true
cp "$OUTPUT_DIR/web"/*.js "$PACKAGE_DIR/" 2>/dev/null || true
cp "$OUTPUT_DIR/web"/*.css "$PACKAGE_DIR/" 2>/dev/null || true
cp -r "$OUTPUT_DIR/web/lib" "$PACKAGE_DIR/" 2>/dev/null || true

# Remove server.js (not needed for static hosting)
rm -f "$PACKAGE_DIR/server.js"

# Copy data files
echo "📊 Copying result data..."
cp "$OUTPUT_DIR/index.json" "$PACKAGE_DIR/"

# Copy summaries
echo "📁 Copying summaries..."
mkdir -p "$PACKAGE_DIR/summaries"
cp -r "$OUTPUT_DIR/summaries"/* "$PACKAGE_DIR/summaries/" 2>/dev/null || true

# Copy edit data (edit.json and logs.jsonl files only)
echo "📝 Copying edit data..."
if [ -d "$OUTPUT_DIR/edits" ]; then
    mkdir -p "$PACKAGE_DIR/edits"
    find "$OUTPUT_DIR/edits" \( -name "edit.json" -o -name "logs.jsonl" \) | while read -r file; do
        rel_path="${file#$OUTPUT_DIR/edits/}"
        target_dir="$PACKAGE_DIR/edits/$(dirname "$rel_path")"
        mkdir -p "$target_dir"
        cp "$file" "$target_dir/"
    done
fi

# Copy judge data
echo "⚖️  Copying judge data..."
if [ -d "$OUTPUT_DIR/judges" ]; then
    mkdir -p "$PACKAGE_DIR/judges"
    cp -r "$OUTPUT_DIR/judges"/* "$PACKAGE_DIR/judges/" 2>/dev/null || true
fi

# Copy sample data
echo "📋 Copying sample data..."
if [ -d "$OUTPUT_DIR/samples" ]; then
    mkdir -p "$PACKAGE_DIR/samples"
    cp -r "$OUTPUT_DIR/samples"/* "$PACKAGE_DIR/samples/" 2>/dev/null || true
fi

# Copy cross-agent analysis data
echo "🔄 Copying cross-agent analysis..."
if [ -d "$OUTPUT_DIR/cross_agent_analysis" ]; then
    mkdir -p "$PACKAGE_DIR/cross_agent_analysis"
    cp -r "$OUTPUT_DIR/cross_agent_analysis"/* "$PACKAGE_DIR/cross_agent_analysis/" 2>/dev/null || true
fi

# Create _headers file for Cloudflare Pages (optional, for CORS and caching)
echo "⚙️  Creating Cloudflare configuration..."
cat > "$PACKAGE_DIR/_headers" << 'EOF'
/*
  Access-Control-Allow-Origin: *
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin

/*.json
  Content-Type: application/json
  Cache-Control: public, max-age=300

/*.js
  Content-Type: application/javascript
  Cache-Control: public, max-age=3600

/*.css
  Content-Type: text/css
  Cache-Control: public, max-age=3600

/*.html
  Content-Type: text/html
  Cache-Control: public, max-age=300
EOF

# Create README
echo "📝 Creating README..."
cat > "$PACKAGE_DIR/README.md" << 'EOF'
# Long-Context-Code-Bench - Cloudflare Pages Deployment

This package is ready for deployment to Cloudflare Pages.

## Deployment Instructions

### Option 1: Drag & Drop (Easiest)

1. Go to https://pages.cloudflare.com/
2. Click "Create a project"
3. Click "Direct Upload"
4. Drag this entire folder to the upload area
5. Your site will be live at `https://your-project.pages.dev`

### Option 2: Wrangler CLI

```bash
npm install -g wrangler
wrangler pages deploy . --project-name=long-context-bench
```

### Option 3: Git Integration

1. Create a new GitHub repository
2. Push this folder to the repository
3. Connect the repository to Cloudflare Pages
4. Cloudflare will automatically deploy on every push

## What's Included

- ✅ All web dashboard files (HTML, CSS, JS)
- ✅ All benchmark results data (JSON)
- ✅ Cross-agent analysis data
- ✅ Judge evaluations
- ✅ Agent edit logs
- ✅ Cloudflare-optimized headers

## Notes

- No build step required - this is a fully static site
- All data is included in the package
- The site works entirely client-side (no server needed)
- CORS headers are configured for API access

## Size

Total package size: ~60-100MB (depending on number of results)

## Support

For issues or questions, visit:
https://github.com/AugmentedAJ/Long-Context-Code-Bench
EOF

# Calculate package size
PACKAGE_SIZE=$(du -sh "$PACKAGE_DIR" | cut -f1)

echo ""
echo "✅ Package created successfully!"
echo "================================"
echo "Package directory: $PACKAGE_DIR"
echo "Package size: $PACKAGE_SIZE"
echo ""
echo "📤 Deployment Options:"
echo ""
echo "1. Cloudflare Pages (Drag & Drop):"
echo "   - Go to https://pages.cloudflare.com/"
echo "   - Click 'Create a project' → 'Direct Upload'"
echo "   - Drag the '$PACKAGE_DIR' folder"
echo ""
echo "2. Wrangler CLI:"
echo "   cd $PACKAGE_DIR"
echo "   wrangler pages deploy . --project-name=long-context-bench"
echo ""
echo "3. Netlify Drop:"
echo "   - Go to https://app.netlify.com/drop"
echo "   - Drag the '$PACKAGE_DIR' folder"
echo ""
echo "4. Vercel:"
echo "   cd $PACKAGE_DIR"
echo "   vercel --prod"
echo ""
echo "The package is ready for deployment! 🚀"

