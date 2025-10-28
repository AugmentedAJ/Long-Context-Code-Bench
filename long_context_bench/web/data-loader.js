/**
 * Data loading utilities for Long-Context-Bench web app
 */

// API base path - use /api when served by Node.js server
const API_BASE = '/api';

// Global data cache
const dataCache = {
    index: null,
    summaries: {},
    edits: {},
    judges: {},
    samples: {}
};

/**
 * Load the index manifest
 */
async function loadIndex() {
    try {
        const response = await fetch(`${API_BASE}/index.json`);
        if (!response.ok) {
            throw new Error('Failed to load index.json');
        }
        dataCache.index = await response.json();
        return dataCache.index;
    } catch (error) {
        console.error('Error loading index:', error);
        // Return empty index if file doesn't exist yet
        return {
            runs: [],
            test_labels: [],
            runners: [],
            models: [],
            last_updated: new Date().toISOString()
        };
    }
}

/**
 * Load a summary file
 */
async function loadSummary(runId) {
    if (dataCache.summaries[runId]) {
        return dataCache.summaries[runId];
    }

    try {
        const response = await fetch(`${API_BASE}/summaries/${runId}/summary.json`);
        if (!response.ok) {
            throw new Error(`Failed to load summary for ${runId}`);
        }

        const summary = await response.json();
        dataCache.summaries[runId] = summary;
        return summary;
    } catch (error) {
        console.error('Error loading summary:', error);
        return null;
    }
}

/**
 * Load all summaries
 */
async function loadAllSummaries() {
    const index = dataCache.index || await loadIndex();
    const summaries = [];
    
    for (const run of index.runs) {
        const summary = await loadSummary(run.run_id);
        if (summary) {
            summaries.push(summary);
        }
    }
    
    return summaries;
}

/**
 * Load edit data for a specific PR
 */
async function loadEdit(editRunId, prId) {
    const cacheKey = `${editRunId}:${prId}`;
    if (dataCache.edits[cacheKey]) {
        return dataCache.edits[cacheKey];
    }

    try {
        const index = dataCache.index || await loadIndex();
        const run = index.runs.find(r => r.edit_run_id === editRunId);

        if (!run) {
            throw new Error(`Edit run ${editRunId} not found`);
        }

        const response = await fetch(`${API_BASE}/edits/${run.runner}/${run.model}/${editRunId}/${prId}/edit.json`);

        if (!response.ok) {
            throw new Error(`Failed to load edit for ${prId}`);
        }

        const edit = await response.json();
        dataCache.edits[cacheKey] = edit;
        return edit;
    } catch (error) {
        console.error('Error loading edit:', error);
        return null;
    }
}

/**
 * Load judge data for a specific PR
 */
async function loadJudge(judgeRunId, prId) {
    const cacheKey = `${judgeRunId}:${prId}`;
    if (dataCache.judges[cacheKey]) {
        return dataCache.judges[cacheKey];
    }

    try {
        const index = dataCache.index || await loadIndex();
        const run = index.runs.find(r => r.judge_run_id === judgeRunId);

        if (!run) {
            throw new Error(`Judge run ${judgeRunId} not found`);
        }

        const judgeModel = run.judge_model || 'default';
        const response = await fetch(`${API_BASE}/judges/${run.judge_mode}/${judgeModel}/${judgeRunId}/${prId}/judge.json`);

        if (!response.ok) {
            throw new Error(`Failed to load judge for ${prId}`);
        }

        const judge = await response.json();
        dataCache.judges[cacheKey] = judge;
        return judge;
    } catch (error) {
        console.error('Error loading judge:', error);
        return null;
    }
}

/**
 * Load sample data for a specific PR
 */
async function loadSample(prId) {
    if (dataCache.samples[prId]) {
        return dataCache.samples[prId];
    }

    try {
        const response = await fetch(`${API_BASE}/samples/v0/${prId}/sample.json`);

        if (!response.ok) {
            throw new Error(`Failed to load sample for ${prId}`);
        }

        const sample = await response.json();
        dataCache.samples[prId] = sample;
        return sample;
    } catch (error) {
        console.error('Error loading sample:', error);
        return null;
    }
}

/**
 * Load all edits and judges for a run
 */
async function loadRunDetails(runId) {
    const summary = await loadSummary(runId);
    if (!summary) {
        return null;
    }

    const index = dataCache.index || await loadIndex();
    const run = index.runs.find(r => r.run_id === runId);
    
    if (!run || !run.pr_ids) {
        return { summary, edits: [], judges: [], samples: [] };
    }

    const edits = [];
    const judges = [];
    const samples = [];

    for (const prId of run.pr_ids) {
        const edit = await loadEdit(run.edit_run_id, prId);
        const judge = await loadJudge(run.judge_run_id, prId);
        const sample = await loadSample(prId);
        
        if (edit) edits.push(edit);
        if (judge) judges.push(judge);
        if (sample) samples.push(sample);
    }

    return { summary, edits, judges, samples };
}

/**
 * Get summaries by test label
 */
async function getSummariesByTestLabel(testLabel) {
    const index = dataCache.index || await loadIndex();
    const runs = index.runs.filter(r => r.test_label === testLabel);
    
    const summaries = [];
    for (const run of runs) {
        const summary = await loadSummary(run.run_id);
        if (summary) {
            summaries.push(summary);
        }
    }
    
    return summaries;
}

/**
 * Get unique values for filters
 */
function getUniqueValues(runs, field) {
    const values = new Set();
    runs.forEach(run => {
        if (run[field]) {
            values.add(run[field]);
        }
    });
    return Array.from(values).sort();
}

/**
 * Format timestamp
 */
function formatTimestamp(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString();
}

/**
 * Format score with color class
 */
function formatScore(score) {
    if (score === null || score === undefined) return '-';
    const value = parseFloat(score);
    let className = 'score-neutral';
    if (value > 0.3) className = 'score-positive';
    else if (value < -0.3) className = 'score-negative';
    return `<span class="${className}">${value.toFixed(2)}</span>`;
}

/**
 * Format percentage
 */
function formatPercentage(value) {
    if (value === null || value === undefined) return '-';
    return `${(value * 100).toFixed(1)}%`;
}

/**
 * Format status badge
 */
function formatStatus(status) {
    if (!status) return '-';
    const className = `status-badge status-${status}`;
    return `<span class="${className}">${status}</span>`;
}

/**
 * Extract PR ID from repo URL and PR number
 */
function getPrId(repoUrl, prNumber) {
    const match = repoUrl.match(/github\.com\/([^\/]+)\/([^\/]+)/);
    if (match) {
        const owner = match[1];
        const repo = match[2].replace('.git', '');
        return `${owner}_${repo}_${prNumber}`;
    }
    return `pr_${prNumber}`;
}

/**
 * Clear cache
 */
function clearCache() {
    dataCache.index = null;
    dataCache.summaries = {};
    dataCache.edits = {};
    dataCache.judges = {};
    dataCache.samples = {};
}

