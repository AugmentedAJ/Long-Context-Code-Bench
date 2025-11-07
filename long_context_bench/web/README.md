# Long-Context-Bench Web Dashboard

Interactive web dashboard for visualizing benchmark results.

## Quick Start

### For Development (editing web UI files)

Run the server from the source directory:

```bash
cd long_context_bench/web
npm install  # First time only
npm start
```

Changes to HTML/CSS/JS files are immediately visible (just refresh browser).

### For Viewing Results (production)

The web app is automatically deployed to `output/web/` when you run benchmark commands.

```bash
cd output/web
npm install  # First time only
npm start
```

Then open http://localhost:3000 in your browser.

## Directory Structure

- **`long_context_bench/web/`** - Source files (edit here during development)
- **`output/web/`** - Deployed copy with benchmark data (auto-generated)

The pipeline automatically copies files from source to output via `deploy_web_app()`.

## Features

- **Leaderboard**: Compare all runs with filtering and sorting
- **Run Details**: Deep dive into individual run metrics and per-PR results
- **Agent Comparison**: Side-by-side comparison with interactive charts

## Architecture

- **Express server** (`server.js`) - Serves static files and provides API endpoints
- **Static web app** - HTML/CSS/JS files that load data dynamically via API
- **No build step** - Simple, easy to customize

## Troubleshooting

**Server won't start:**
- Ensure Node.js v14+ is installed
- Run `npm install` in output/web directory
- Check if port 3000 is in use (set `PORT` env var for different port)

**No data showing:**
- Ensure benchmark has been run
- Check server logs and browser console (F12) for errors

