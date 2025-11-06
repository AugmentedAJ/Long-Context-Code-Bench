#!/bin/bash
# Package Long-Context-Code-Bench results for sharing
# Creates a lightweight archive with web UI and results data

set -e

# Configuration
OUTPUT_DIR="${1:-output}"
PACKAGE_NAME="${2:-long-context-bench-v0-results}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PACKAGE_DIR="${PACKAGE_NAME}_${TIMESTAMP}"

echo "📦 Packaging Long-Context-Code-Bench Results"
echo "=============================================="
echo "Output directory: $OUTPUT_DIR"
echo "Package name: $PACKAGE_DIR"
echo ""

# Create package directory
mkdir -p "$PACKAGE_DIR"

# Copy web app files (excluding node_modules)
echo "📋 Copying web app files..."
mkdir -p "$PACKAGE_DIR/web"
cp "$OUTPUT_DIR/web"/*.html "$PACKAGE_DIR/web/" 2>/dev/null || true
cp "$OUTPUT_DIR/web"/*.js "$PACKAGE_DIR/web/" 2>/dev/null || true
cp "$OUTPUT_DIR/web"/*.css "$PACKAGE_DIR/web/" 2>/dev/null || true
cp "$OUTPUT_DIR/web/package.json" "$PACKAGE_DIR/web/" 2>/dev/null || true
cp -r "$OUTPUT_DIR/web/lib" "$PACKAGE_DIR/web/" 2>/dev/null || true

# Copy data files
echo "📊 Copying result data..."
cp "$OUTPUT_DIR/index.json" "$PACKAGE_DIR/web/"

# Copy summaries
mkdir -p "$PACKAGE_DIR/web/summaries"
cp -r "$OUTPUT_DIR/summaries"/* "$PACKAGE_DIR/web/summaries/"

# Copy edit data (only edit.json files, not logs or patches to save space)
echo "📝 Copying edit data..."
if [ -d "$OUTPUT_DIR/edits" ]; then
    mkdir -p "$PACKAGE_DIR/web/edits"
    # Copy directory structure and edit.json files only
    find "$OUTPUT_DIR/edits" -name "edit.json" | while read -r edit_file; do
        # Get relative path from output/edits/
        rel_path="${edit_file#$OUTPUT_DIR/edits/}"
        target_dir="$PACKAGE_DIR/web/edits/$(dirname "$rel_path")"
        mkdir -p "$target_dir"
        cp "$edit_file" "$target_dir/"
    done
fi

# Copy judge data
echo "⚖️  Copying judge data..."
if [ -d "$OUTPUT_DIR/judges" ]; then
    mkdir -p "$PACKAGE_DIR/web/judges"
    cp -r "$OUTPUT_DIR/judges"/* "$PACKAGE_DIR/web/judges/"
fi

# Copy sample data (if exists)
echo "📋 Copying sample data..."
if [ -d "$OUTPUT_DIR/samples" ]; then
    mkdir -p "$PACKAGE_DIR/web/samples"
    cp -r "$OUTPUT_DIR/samples"/* "$PACKAGE_DIR/web/samples/"
fi

# Create README
echo "📝 Creating README..."
cat > "$PACKAGE_DIR/README.md" << 'EOF'
# Long-Context-Code-Bench v0 Results

This package contains the results from the v0 benchmark comparing three AI coding agents:
- **Auggie** (sonnet4.5)
- **Claude Code** (claude-sonnet-4-5)
- **Factory** (claude-sonnet-4-5-20250929)

## Quick Start

### Option 1: One-Click Launcher (Easiest)

```bash
./start.sh    # Mac/Linux
start.bat     # Windows
```

This automatically installs dependencies and starts the server at http://localhost:3000

### Option 2: Static Hosting (Cloudflare Pages, Netlify, etc.)

The `web/` directory is a fully static site - just drag and drop to:
- **Cloudflare Pages**: https://pages.cloudflare.com/ (drag `web/` folder)
- **Netlify Drop**: https://app.netlify.com/drop (drag `web/` folder)
- **Vercel**: `cd web && vercel --prod`
- **GitHub Pages**: Push `web/` to a gh-pages branch

**IMPORTANT**: Deploy the `web/` folder from THIS package, not from `output/web/`!
The `output/web/` folder uses symlinks which don't work on static hosting platforms.
This packaged version contains actual copies of all data files.

No build step required! All data is included (~4MB).

### Option 3: Local Python Server (No Node.js required)

```bash
cd web
python3 -m http.server 8000
```

Then open http://localhost:8000 in your browser.

### Option 4: Node.js Server (Best Performance)

```bash
cd web
npm install
npm start
```

Then open http://localhost:3000 in your browser.

## What's Included

- `web/` - Interactive web dashboard
  - `index.html` - Main leaderboard page
  - `comparison.html` - Agent comparison charts
  - `summary.html` - Individual run summaries
  - `task.html` - Per-task detailed results
  - `index.json` - Results index
  - `summaries/` - Detailed result data

## Results Summary

| Agent | Model | Aggregate Score | Success Rate | Tasks/Hour |
|-------|-------|----------------|--------------|------------|
| Factory | claude-sonnet-4-5-20250929 | 0.274 | 100.0% | 8.31 |
| Auggie | sonnet4.5 | 0.234 | 97.5% | 6.08 |
| Claude Code | claude-sonnet-4-5 | 0.042 | 97.5% | 14.57 |

## Metrics Explained

- **Aggregate Score**: Combined score from all metrics (-1.0 to 1.0, higher is better)
- **Correctness**: How accurately the changes match the ground truth
- **Completeness**: How complete the implementation is
- **Code Reuse**: How well the agent reuses existing code patterns
- **Best Practices**: Adherence to coding best practices
- **Unsolicited Docs**: Penalty for creating unnecessary documentation

## Dataset

- **Repository**: elastic/elasticsearch
- **PRs**: 40 real-world pull requests
- **Test Label**: v0
- **Evaluation**: Deterministic judge mode

## More Information

For more details about the benchmark methodology and setup, see:
https://github.com/AugmentedAJ/Long-Context-Code-Bench

EOF

# Create a simple launcher script
echo "🚀 Creating launcher script..."
cat > "$PACKAGE_DIR/start.sh" << 'EOF'
#!/bin/bash
# Quick launcher for the web dashboard

echo "Starting Long-Context-Code-Bench Dashboard..."
echo ""

cd web

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies (first time only)..."
    npm install
    echo ""
fi

echo "Starting server..."
echo "Dashboard will be available at: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

npm start
EOF

chmod +x "$PACKAGE_DIR/start.sh"

# Create Windows launcher
cat > "$PACKAGE_DIR/start.bat" << 'EOF'
@echo off
echo Starting Long-Context-Code-Bench Dashboard...
echo.

cd web

if not exist "node_modules" (
    echo Installing dependencies (first time only)...
    call npm install
    echo.
)

echo Starting server...
echo Dashboard will be available at: http://localhost:3000
echo.
echo Press Ctrl+C to stop the server
echo.

call npm start
EOF

# Create analysis documents package
if [ -d "analysis" ]; then
    echo "📄 Copying analysis documents..."
    mkdir -p "$PACKAGE_DIR/analysis"
    cp analysis/v0_*.md "$PACKAGE_DIR/analysis/" 2>/dev/null || true
fi

# Calculate sizes
WEB_SIZE=$(du -sh "$PACKAGE_DIR/web" | cut -f1)
TOTAL_SIZE=$(du -sh "$PACKAGE_DIR" | cut -f1)

echo ""
echo "✅ Package created successfully!"
echo "=============================================="
echo "Location: $PACKAGE_DIR/"
echo "Web app size: $WEB_SIZE"
echo "Total size: $TOTAL_SIZE"
echo ""

# Create archive
echo "📦 Creating archive..."
tar -czf "${PACKAGE_DIR}.tar.gz" "$PACKAGE_DIR"
ARCHIVE_SIZE=$(du -sh "${PACKAGE_DIR}.tar.gz" | cut -f1)

echo "✅ Archive created: ${PACKAGE_DIR}.tar.gz ($ARCHIVE_SIZE)"
echo ""
echo "📤 Sharing Options:"
echo "=============================================="
echo ""
echo "1. Share the archive file:"
echo "   ${PACKAGE_DIR}.tar.gz"
echo ""
echo "2. Upload to GitHub Releases:"
echo "   gh release create v0-results ${PACKAGE_DIR}.tar.gz"
echo ""
echo "3. Deploy to GitHub Pages:"
echo "   cd $PACKAGE_DIR/web"
echo "   git init && git add . && git commit -m 'v0 results'"
echo "   gh repo create && git push"
echo ""
echo "4. Deploy to Netlify/Vercel:"
echo "   - Drag and drop $PACKAGE_DIR/web/ to netlify.com/drop"
echo "   - Or: cd $PACKAGE_DIR/web && vercel"
echo ""
echo "5. Share via cloud storage:"
echo "   - Upload ${PACKAGE_DIR}.tar.gz to Google Drive/Dropbox"
echo "   - Recipients extract and run ./start.sh"
echo ""

# Create deployment instructions
cat > "$PACKAGE_DIR/DEPLOYMENT.md" << 'EOF'
# Deployment Options

## Option 1: GitHub Pages (Free, Public)

```bash
cd web
git init
git add .
git commit -m "Deploy v0 results"
gh repo create long-context-bench-results --public --source=. --remote=origin --push
gh pages deploy --branch gh-pages --dir .
```

Your dashboard will be live at: `https://<username>.github.io/long-context-bench-results`

## Option 2: Netlify (Free, Easy)

### Via Drag & Drop:
1. Go to https://app.netlify.com/drop
2. Drag the `web/` folder
3. Get instant URL like `https://random-name.netlify.app`

### Via CLI:
```bash
npm install -g netlify-cli
cd web
netlify deploy --prod
```

## Option 3: Vercel (Free, Fast)

```bash
npm install -g vercel
cd web
vercel --prod
```

## Option 4: AWS S3 + CloudFront (Scalable)

```bash
cd web
aws s3 sync . s3://your-bucket-name --acl public-read
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

## Option 5: Self-Hosted Server

### Using Docker:
```bash
cd web
docker run -d -p 80:80 -v $(pwd):/usr/share/nginx/html nginx:alpine
```

### Using Node.js:
```bash
cd web
npm install
npm start
```

## Option 6: Share Archive File

Share the `.tar.gz` file via:
- GitHub Releases
- Google Drive / Dropbox
- Email (if small enough)
- Internal file server

Recipients can extract and run:
```bash
tar -xzf long-context-bench-v0-results_*.tar.gz
cd long-context-bench-v0-results_*/
./start.sh  # or start.bat on Windows
```

## Security Considerations

- **Public deployment**: Remove any sensitive data from summaries
- **Private deployment**: Use authentication (Netlify password protection, AWS Cognito, etc.)
- **CORS**: Already configured for local and deployed environments

## Custom Domain

Most platforms support custom domains:
- **GitHub Pages**: Settings → Pages → Custom domain
- **Netlify**: Site settings → Domain management
- **Vercel**: Project settings → Domains

EOF

echo "📖 Deployment instructions: $PACKAGE_DIR/DEPLOYMENT.md"
echo ""
echo "⚠️  IMPORTANT: Deploy $PACKAGE_DIR/web/, NOT output/web/"
echo "   The output/web/ folder uses symlinks which don't work on static hosts."
echo "   This packaged version has actual data files."
echo ""
echo "🎉 Done! Package is ready to share."

