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
const OUTPUT_DIR = process.env.OUTPUT_DIR || path.join(__dirname, '..', '..', 'output');

console.log('Long-Context-Bench Web Server');
console.log('==============================');
console.log(`Output directory: ${OUTPUT_DIR}`);
console.log(`Web files directory: ${__dirname}`);

// Serve static files (HTML, CSS, JS, etc.) from the web directory
app.use(express.static(__dirname));

// API endpoint to get the index manifest
app.get('/api/index.json', (req, res) => {
    const indexPath = path.join(OUTPUT_DIR, 'index.json');
    
    if (!fs.existsSync(indexPath)) {
        return res.status(404).json({ error: 'Index not found. Run a benchmark first.' });
    }
    
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

    res.sendFile(summaryPath);
});

// API endpoint to get edit data
app.get('/api/edits/:runner/:model/:editRunId/:prId/edit.json', (req, res) => {
    const { runner, model, editRunId, prId } = req.params;
    const editPath = path.join(OUTPUT_DIR, 'edits', runner, model, editRunId, prId, 'edit.json');

    if (!fs.existsSync(editPath)) {
        return res.status(404).json({ error: `Edit not found` });
    }

    res.sendFile(editPath);
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
app.get('/api/judges/:judgeMode/:judgeModel/:judgeRunId/:prId/judge.json', (req, res) => {
    const { judgeMode, judgeModel, judgeRunId, prId } = req.params;
    const judgePath = path.join(OUTPUT_DIR, 'judges', judgeMode, judgeModel, judgeRunId, prId, 'judge.json');
    
    if (!fs.existsSync(judgePath)) {
        return res.status(404).json({ error: `Judge not found` });
    }
    
    res.sendFile(judgePath);
});

// API endpoint to get sample data
app.get('/api/samples/:version/:prId/sample.json', (req, res) => {
    const { version, prId } = req.params;
    const samplePath = path.join(OUTPUT_DIR, 'samples', version, prId, 'sample.json');

    if (!fs.existsSync(samplePath)) {
        return res.status(404).json({ error: `Sample not found` });
    }

    res.sendFile(samplePath);
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
    console.log(`\nAvailable pages:`);
    console.log(`  - Leaderboard:       http://localhost:${PORT}/`);
    console.log(`  - Summary:           http://localhost:${PORT}/summary.html`);
    console.log(`  - Comparison:        http://localhost:${PORT}/comparison.html`);
    console.log(`  - Cross-Agent:       http://localhost:${PORT}/cross-agent.html`);
    console.log(`  - Task Detail:       http://localhost:${PORT}/task.html`);
    console.log(`\nPress Ctrl+C to stop the server\n`);
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\n\nShutting down server...');
    process.exit(0);
});

