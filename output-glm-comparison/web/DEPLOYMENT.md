# Cloudflare Pages Deployment Guide

This directory contains a static build of the GLM 4.6 with/without MCP comparison web UI, ready for deployment to Cloudflare Pages.

## What's Included

- **HTML/CSS/JS**: All web assets (index.html, styles.css, app.js, etc.)
- **Data files**: index.json, summaries/, edits/, judges/
- **robots.txt**: Prevents Google and other search engines from indexing this site

## Deployment Steps

### Option 1: Cloudflare Pages Dashboard (Recommended)

1. **Create a new Cloudflare Pages project**
   - Go to https://dash.cloudflare.com/
   - Navigate to Workers & Pages → Create application → Pages → Upload assets

2. **Upload the web directory**
   - Drag and drop the entire `output-glm-comparison/web/` directory
   - Or use the file picker to select all files in this directory

3. **Configure the project**
   - Project name: `glm-mcp-comparison` (or your choice)
   - Production branch: Not applicable for direct upload
   - Build settings: Not needed (static files)

4. **Deploy**
   - Click "Save and Deploy"
   - Your site will be available at `https://<project-name>.pages.dev`

### Option 2: Wrangler CLI

1. **Install Wrangler** (if not already installed)
   ```bash
   npm install -g wrangler
   ```

2. **Login to Cloudflare**
   ```bash
   wrangler login
   ```

3. **Deploy from this directory**
   ```bash
   cd output-glm-comparison/web
   wrangler pages deploy . --project-name=glm-mcp-comparison
   ```

### Option 3: Git Integration

1. **Create a new Git repository** (if not already in one)
   ```bash
   cd output-glm-comparison/web
   git init
   git add .
   git commit -m "Initial commit: GLM MCP comparison"
   ```

2. **Push to GitHub/GitLab**
   ```bash
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

3. **Connect to Cloudflare Pages**
   - Go to Cloudflare Pages dashboard
   - Create application → Pages → Connect to Git
   - Select your repository
   - Build settings:
     - Build command: (leave empty)
     - Build output directory: `/`
   - Deploy

## Preventing Search Engine Indexing

The `robots.txt` file is already included and configured to prevent all search engines from indexing:

```
User-agent: *
Disallow: /
```

### Additional Protection (Optional)

You can also add these meta tags to `index.html` if you want extra protection:

```html
<meta name="robots" content="noindex, nofollow">
<meta name="googlebot" content="noindex, nofollow">
```

Or configure Cloudflare Pages to add these headers:
1. Go to your Pages project settings
2. Navigate to "Functions" → "Headers"
3. Add a `_headers` file with:
   ```
   /*
     X-Robots-Tag: noindex, nofollow
   ```

## Verifying the Deployment

After deployment, visit your site and verify:

1. ✅ The leaderboard shows 2 agents (factory:glm-4.6 and factory:custom:glm-4.6)
2. ✅ 47 PRs are listed in the "Head-to-Head Details by PR" section
3. ✅ Clicking "View Details" on any PR shows the detailed comparison
4. ✅ The metrics chart displays correctly
5. ✅ robots.txt is accessible at `https://your-site.pages.dev/robots.txt`

## File Size Note

The total size of this directory is approximately:
- Web assets: ~500 KB
- Data files (summaries, edits, judges): ~50-100 MB

Cloudflare Pages has a 25 MB limit per file and 20,000 files per deployment. If you encounter issues:
- The judge files are the largest - consider compressing them
- Or use Cloudflare R2 for large data files and fetch them dynamically

## Updating the Data

To update the comparison with new data:

1. Run the judge and summary commands in the main repository
2. Regenerate the filtered index.json
3. Copy the updated files to this directory
4. Redeploy to Cloudflare Pages

## Support

For issues or questions:
- Check the main repository: https://github.com/AugmentedAJ/Long-Context-Code-Bench
- Review the README.md in the parent directory

