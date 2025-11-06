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
