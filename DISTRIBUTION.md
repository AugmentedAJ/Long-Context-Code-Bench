# Distribution Guide for Long-Context-Code-Bench Results

This guide explains how to share benchmark results with your team for debugging and analysis.

## Two Distribution Methods

### Method 1: Public Results (Lightweight, No Logs)
**Best for:** Sharing results publicly, quick demos, stakeholder reviews

**Size:** ~4MB (444KB compressed)

**What's included:**
- Web dashboard (all HTML/JS/CSS)
- Aggregate scores and metrics
- Judge evaluations and rationale
- Code diffs (ground truth vs agent submissions)
- Sample task descriptions
- ❌ No agent logs (stdout/stderr)

**How to share:**
```bash
# Package the results
./scripts/package_results.sh

# Share the archive
# Upload long-context-bench-v0-results_*.tar.gz to:
# - GitHub Releases
# - Google Drive / Dropbox
# - Email (small enough!)
# - Slack / Teams

# Or deploy to static hosting
# Drag and drop the web/ folder to:
# - Cloudflare Pages: https://pages.cloudflare.com/
# - Netlify: https://app.netlify.com/drop
```

**Recipients:**
```bash
# Extract and run
tar -xzf long-context-bench-v0-results_*.tar.gz
cd long-context-bench-v0-results_*/
./start.sh  # Opens dashboard at http://localhost:3000
```

---

### Method 2: Full Results with Logs (For Team Debugging)
**Best for:** Internal team debugging, detailed analysis, reproducing issues

**Size:** ~2-4GB (depends on log verbosity)

**What's included:**
- Everything from Method 1
- ✅ Full agent logs (stdout/stderr) for every task
- ✅ Raw edit outputs
- ✅ Complete execution traces

**How to share:**

#### Step 1: Archive the output directory
```bash
# From the benchmark root directory
tar -czf long-context-bench-v0-full-output.tar.gz output/

# Check the size
ls -lh long-context-bench-v0-full-output.tar.gz
```

#### Step 2: Upload to shared storage
Choose one:

**Option A: AWS S3 (Recommended for teams)**
```bash
# Upload
aws s3 cp long-context-bench-v0-full-output.tar.gz s3://your-bucket/benchmarks/

# Generate presigned URL (expires in 7 days)
aws s3 presign s3://your-bucket/benchmarks/long-context-bench-v0-full-output.tar.gz --expires-in 604800
```

**Option B: Google Drive**
```bash
# Install gdrive CLI: https://github.com/prasmussen/gdrive
gdrive upload long-context-bench-v0-full-output.tar.gz

# Share the link with your team
```

**Option C: Dropbox**
```bash
# Install Dropbox CLI: https://www.dropbox.com/install-linux
dropbox upload long-context-bench-v0-full-output.tar.gz
```

**Option D: Internal file server**
```bash
# Copy to your team's shared drive
cp long-context-bench-v0-full-output.tar.gz /mnt/shared/benchmarks/
```

#### Step 3: Share instructions with your team

Create a message like this:

```
📊 Long-Context-Code-Bench v0 Results Available

Full results with logs are ready for debugging:

📥 Download: [insert link to tar.gz file]
📦 Size: ~2.5GB compressed

🚀 Quick Start:

1. Clone the benchmark repo:
   git clone git@github.com:AugmentedAJ/Long-Context-Code-Bench.git
   cd Long-Context-Code-Bench

2. Download and extract the results:
   # Download the file to the repo root, then:
   tar -xzf long-context-bench-v0-full-output.tar.gz

3. Start the dashboard:
   cd output/web
   npm install
   npm start

4. Open: http://localhost:3000

📊 What's included:
- 40 PRs from elastic/elasticsearch
- 3 agents tested: Auggie, Claude Code, Factory
- Full logs available for every task
- Complete diffs and judge evaluations

🔍 Debugging tips:
- Click any task to see full logs
- Use "Download Logs" button to save locally
- Filter logs by stdout/stderr
- Compare diffs side-by-side

Questions? Ping me on Slack!
```

---

## Recommended Workflow

### For Your Team (Internal)
1. **Use Method 2** - Share full `output/` directory via S3/Drive
2. Team members clone the repo and extract `output/` into it
3. Everyone can debug with full logs locally

### For External Stakeholders
1. **Use Method 1** - Deploy to Cloudflare Pages
2. Share the public URL (e.g., https://v0-long-context-bench.pages.dev)
3. No logs exposed, clean presentation

### For GitHub Release
1. **Create two assets:**
   - `long-context-bench-v0-results.tar.gz` (lightweight, 444KB)
   - `long-context-bench-v0-full-output.tar.gz` (with logs, ~2GB)
2. Mark the full version as "For debugging only"

```bash
# Create GitHub release with both versions
gh release create v0-results \
  long-context-bench-v0-results_*.tar.gz \
  long-context-bench-v0-full-output.tar.gz \
  --title "v0 Benchmark Results" \
  --notes "See DISTRIBUTION.md for usage instructions"
```

---

## Security Considerations

### Public Distribution (Method 1)
- ✅ Safe to share publicly
- ✅ No sensitive logs
- ✅ No API keys or credentials
- ✅ Only aggregate metrics and diffs

### Internal Distribution (Method 2)
- ⚠️ May contain sensitive information in logs:
  - API keys (if accidentally logged)
  - Internal file paths
  - Error messages with stack traces
  - Agent reasoning/prompts
- 🔒 **Recommendation:** Share only with trusted team members
- 🔒 Use presigned URLs with expiration
- 🔒 Don't commit `output/` to public repos

---

## File Size Reference

| Component | Size | Included in Method 1 | Included in Method 2 |
|-----------|------|---------------------|---------------------|
| Web UI | ~100KB | ✅ | ✅ |
| Index & Summaries | ~50KB | ✅ | ✅ |
| Edit data (diffs) | ~2MB | ✅ | ✅ |
| Judge data | ~500KB | ✅ | ✅ |
| Sample data | ~200KB | ✅ | ✅ |
| **Logs** | **~2-3GB** | ❌ | ✅ |
| **Total** | **~4MB / ~3GB** | **444KB** | **~1-2GB** |

---

## Quick Commands Reference

```bash
# Create lightweight package (no logs)
./scripts/package_results.sh

# Create full archive with logs
tar -czf long-context-bench-v0-full-output.tar.gz output/

# Upload to S3
aws s3 cp long-context-bench-v0-full-output.tar.gz s3://your-bucket/

# Generate presigned URL (7 days)
aws s3 presign s3://your-bucket/long-context-bench-v0-full-output.tar.gz --expires-in 604800

# Team member: Download and extract
wget [presigned-url] -O long-context-bench-v0-full-output.tar.gz
tar -xzf long-context-bench-v0-full-output.tar.gz

# Team member: Start dashboard
cd output/web
npm install
npm start
```

---

## Troubleshooting

### "Logs not available" on deployed site
- This is expected for Method 1 (lightweight package)
- Logs are only included in Method 2 (full output)
- Deploy the full `output/` directory if you need logs

### Large file upload fails
- Split the archive: `split -b 1G long-context-bench-v0-full-output.tar.gz output-part-`
- Upload parts separately
- Recipients: `cat output-part-* > long-context-bench-v0-full-output.tar.gz`

### Symlinks don't work on Windows
- Extract on Mac/Linux first
- Or use WSL on Windows
- Or modify `stats.py` to copy files instead of symlinking

---

## Next Steps

1. **For your team:** Archive `output/` and upload to S3/Drive
2. **For public:** Deploy packaged `web/` to Cloudflare Pages
3. **For GitHub:** Create release with both versions

Need help? Check the main README or open an issue.

