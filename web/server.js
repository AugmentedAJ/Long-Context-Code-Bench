#!/usr/bin/env node

/**
 * Simple Express server for Long-Context-Bench web dashboard
 * 
 * Serves the web app and provides API endpoints for data files.
 * This avoids CORS issues when loading JSON files from the file system.
 */

const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// Determine the output directory
// When running from long_context_bench/web/, output is at ../../output
// When deployed to output/web/, data is at ../
// Resolve to absolute path for res.sendFile() compatibility
const OUTPUT_DIR = path.resolve(process.env.OUTPUT_DIR || path.join(__dirname, '..', '..', 'output'));

console.log('Long-Context-Bench Web Server');
console.log('==============================');
console.log(`Output directory: ${OUTPUT_DIR}`);
console.log(`Web files directory: ${__dirname}`);

// Serve static files (HTML, CSS, JS, etc.) from the web directory
app.use(express.static(__dirname));

// Serve data files from the output directory at /data path
// This allows the web app to access output/head_to_head_metadata.json at /data/head_to_head_metadata.json
app.use('/data', express.static(OUTPUT_DIR));

// API endpoint to get the index manifest
app.get('/api/index.json', (req, res) => {
    const indexPath = path.join(OUTPUT_DIR, 'index.json');

    if (!fs.existsSync(indexPath)) {
        return res.status(404).json({ error: 'Index not found. Run a benchmark first.' });
    }

    // Disable caching for index.json to always get fresh data
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');

    res.sendFile(indexPath);
});

// API endpoint to get summary data
// Support both simple runId and runId_runner_model format
app.get('/api/summaries/:runId(*)/summary.json', (req, res) => {
    const { runId } = req.params;
    const summaryPath = path.join(OUTPUT_DIR, 'summaries', runId, 'summary.json');

    if (!fs.existsSync(summaryPath)) {
        return res.status(404).json({ error: `Summary not found for run ${runId}` });
    }

    // Disable caching for summary data to always get fresh results
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');

    res.sendFile(summaryPath);
});

// API endpoint to get edit data (supports both edit.json and edit_summary.json)
app.get('/api/edits/:runner/:model/:editRunId/:prId/edit.json', (req, res) => {
    const { runner, model, editRunId, prId } = req.params;

    // Try edit.json first, then fall back to edit_summary.json
    const editPath = path.join(OUTPUT_DIR, 'edits', runner, model, editRunId, prId, 'edit.json');
    const editSummaryPath = path.join(OUTPUT_DIR, 'edits', runner, model, editRunId, prId, 'edit_summary.json');

    if (fs.existsSync(editPath)) {
        return res.sendFile(editPath);
    } else if (fs.existsSync(editSummaryPath)) {
        return res.sendFile(editSummaryPath);
    } else {
        return res.status(404).json({ error: `Edit not found` });
    }
});

// API endpoint to get edit summary data
app.get('/api/edits/:runner/:model/:editRunId/:prId/edit_summary.json', (req, res) => {
    const { runner, model, editRunId, prId } = req.params;
    const editSummaryPath = path.join(OUTPUT_DIR, 'edits', runner, model, editRunId, prId, 'edit_summary.json');

    if (!fs.existsSync(editSummaryPath)) {
        return res.status(404).json({ error: `Edit summary not found` });
    }

    res.sendFile(editSummaryPath);
});

// API endpoint to get edit patch
app.get('/api/edits/:runner/:model/:editRunId/:prId/edit.patch', (req, res) => {
    const { runner, model, editRunId, prId } = req.params;
    const patchPath = path.join(OUTPUT_DIR, 'edits', runner, model, editRunId, prId, 'edit.patch');

    if (!fs.existsSync(patchPath)) {
        return res.status(404).json({ error: `Edit patch not found` });
    }

    res.sendFile(patchPath);
});

// API endpoint to get logs data
app.get('/api/edits/:runner/:model/:editRunId/:prId/logs.jsonl', (req, res) => {
    const { runner, model, editRunId, prId } = req.params;
    const logsPath = path.join(OUTPUT_DIR, 'edits', runner, model, editRunId, prId, 'logs.jsonl');

    if (!fs.existsSync(logsPath)) {
        return res.status(404).json({ error: `Logs not found` });
    }

    res.sendFile(logsPath);
});

// API endpoint to get judge data
// Path structure: judges/{judgeMode}/{judgeModel}/{judgeRunId}/{editRunId}/{prId}/judge.json
app.get('/api/judges/:judgeMode/:judgeModel/:judgeRunId/:editRunId/:prId/judge.json', (req, res) => {
    const { judgeMode, judgeModel, judgeRunId, editRunId, prId } = req.params;
    const judgePath = path.join(OUTPUT_DIR, 'judges', judgeMode, judgeModel, judgeRunId, editRunId, prId, 'judge.json');

    if (!fs.existsSync(judgePath)) {
        return res.status(404).json({ error: `Judge not found` });
    }

    res.sendFile(judgePath);
});

// API endpoint to get sample data (with version)
app.get('/api/samples/:version/:prId/sample.json', (req, res) => {
    const { version, prId } = req.params;

    // Try various possible locations for sample data
    const possiblePaths = [
        path.join(OUTPUT_DIR, 'samples', version, prId, 'sample.json'),  // output/samples/v1/pr_id/sample.json
        path.join(OUTPUT_DIR, 'samples', prId, 'sample.json'),           // output/samples/pr_id/sample.json (flat structure)
        path.join(__dirname, '..', '..', 'data', 'samples', version, prId, 'sample.json'),  // data/samples/v1/pr_id/sample.json
    ];

    for (const samplePath of possiblePaths) {
        if (fs.existsSync(samplePath)) {
            return res.sendFile(samplePath);
        }
    }

    return res.status(404).json({ error: `Sample not found` });
});

// API endpoint to get sample data (without version - flat structure)
app.get('/api/samples/:prId/sample.json', (req, res) => {
    const { prId } = req.params;

    const samplePath = path.join(OUTPUT_DIR, 'samples', prId, 'sample.json');

    if (fs.existsSync(samplePath)) {
        return res.sendFile(samplePath);
    } else {
        return res.status(404).json({ error: `Sample not found` });
    }
});

// API endpoint to list cross-agent analyses
app.get('/api/cross_agent_analysis/', (req, res) => {
    const analysisDir = path.join(OUTPUT_DIR, 'cross_agent_analysis');

    if (!fs.existsSync(analysisDir)) {
        return res.json([]);
    }

    const files = fs.readdirSync(analysisDir).filter(f => f.endsWith('.json'));
    res.json(files);
});

// API endpoint to get a specific cross-agent analysis
app.get('/api/cross_agent_analysis/:filename', (req, res) => {
    const { filename } = req.params;
    const analysisPath = path.join(OUTPUT_DIR, 'cross_agent_analysis', filename);

    if (!fs.existsSync(analysisPath)) {
        return res.status(404).json({ error: `Analysis not found` });
    }

    res.sendFile(analysisPath);
});

// API endpoint to list head-to-head results
app.get('/api/head_to_head/', (req, res) => {
    const h2hDir = path.join(OUTPUT_DIR, 'head_to_head');

    if (!fs.existsSync(h2hDir)) {
        return res.json([]);
    }

    const files = fs.readdirSync(h2hDir).filter(f => f.endsWith('.json'));
    res.json(files);
});

// API endpoint to get a specific head-to-head result
app.get('/api/head_to_head/:filename', (req, res) => {
    const { filename } = req.params;
    const h2hPath = path.join(OUTPUT_DIR, 'head_to_head', filename);

    if (!fs.existsSync(h2hPath)) {
        return res.status(404).json({ error: `Head-to-head result not found` });
    }

    res.sendFile(h2hPath);
});

// Serve data files directly (for task detail page)
app.use('/data', express.static(OUTPUT_DIR));

// Health check endpoint
app.get('/api/health', (req, res) => {
    res.json({
        status: 'ok',
        outputDir: OUTPUT_DIR,
        indexExists: fs.existsSync(path.join(OUTPUT_DIR, 'index.json'))
    });
});

// Serve index.html for the root path
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

// Start the server
app.listen(PORT, () => {
    console.log(`\n✓ Server running at http://localhost:${PORT}`);
    console.log(`\nPress Ctrl+C to stop the server\n`);
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\n\nShutting down server...');
    process.exit(0);
});

