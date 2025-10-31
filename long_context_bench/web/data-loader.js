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
        // First, try to find the summary_path from the index
        const index = dataCache.index || await loadIndex();
        const run = index.runs.find(r => r.run_id === runId);

        let summaryPath;
        if (run && run.summary_path) {
            // Use the summary_path from the index
            summaryPath = `${API_BASE}/${run.summary_path}`;
        } else {
            // Fallback to the old path format
            summaryPath = `${API_BASE}/summaries/${runId}/summary.json`;
        }

        const response = await fetch(summaryPath);
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
 * Load a summary by its path (unique identifier including runner/model)
 */
async function loadSummaryByPath(summaryPath) {
    // Use summaryPath as cache key
    if (dataCache.summaries[summaryPath]) {
        return dataCache.summaries[summaryPath];
    }

    try {
        const fullPath = summaryPath.startsWith('summaries/')
            ? `${API_BASE}/${summaryPath}`
            : `${API_BASE}/summaries/${summaryPath}/summary.json`;

        const response = await fetch(fullPath);
        if (!response.ok) {
            throw new Error(`Failed to load summary from ${summaryPath}`);
        }

        const summary = await response.json();
        // Add summary_path to the summary object for unique identification
        summary.summary_path = summaryPath;
        dataCache.summaries[summaryPath] = summary;
        return summary;
    } catch (error) {
        console.error('Error loading summary by path:', error);
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
        // Use summary_path as unique identifier instead of run_id
        // since multiple runners can share the same run_id
        const cacheKey = run.summary_path || run.run_id;

        if (dataCache.summaries[cacheKey]) {
            summaries.push(dataCache.summaries[cacheKey]);
            continue;
        }

        try {
            let summaryPath;
            if (run.summary_path) {
                summaryPath = `${API_BASE}/${run.summary_path}`;
            } else {
                summaryPath = `${API_BASE}/summaries/${run.run_id}/summary.json`;
            }

            const response = await fetch(summaryPath);
            if (!response.ok) {
                console.error(`Failed to load summary from ${summaryPath}`);
                continue;
            }

            const summary = await response.json();
            // Add summary_path to the summary object for unique identification
            summary.summary_path = run.summary_path || run.run_id;
            dataCache.summaries[cacheKey] = summary;
            summaries.push(summary);
        } catch (error) {
            console.error(`Error loading summary for ${run.run_id}:`, error);
        }
    }

    return summaries;
}

/**
 * Load edit data for a specific PR
 * @param {string|object} editRunIdOrRun - Either edit_run_id string or run object
 * @param {string} prId - PR identifier
 */
async function loadEdit(editRunIdOrRun, prId) {
    // Handle both old API (editRunId string) and new API (run object)
    let run, editRunId, runIdToUse;

    if (typeof editRunIdOrRun === 'object' && editRunIdOrRun !== null) {
        // New API: run object passed directly
        run = editRunIdOrRun;
        editRunId = run.edit_run_id;
        runIdToUse = editRunId || run.run_id;
    } else {
        // Old API: editRunId string passed
        editRunId = editRunIdOrRun;
        runIdToUse = editRunId;

        if (!editRunId) {
            return null;
        }

        const index = dataCache.index || await loadIndex();
        run = index.runs.find(r => r.edit_run_id === editRunId);

        if (!run) {
            throw new Error(`Edit run ${editRunId} not found`);
        }
    }

    const cacheKey = `${run.runner}:${run.model}:${runIdToUse}:${prId}`;
    if (dataCache.edits[cacheKey]) {
        return dataCache.edits[cacheKey];
    }

    try {
        const response = await fetch(`${API_BASE}/edits/${run.runner}/${run.model}/${runIdToUse}/${prId}/edit.json`);

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
 * @param {string|object} judgeRunIdOrRun - Either judge_run_id string or run object
 * @param {string} prId - PR identifier
 */
async function loadJudge(judgeRunIdOrRun, prId) {
    // Handle both old API (judgeRunId string) and new API (run object)
    let run, judgeRunId, runIdToUse;

    if (typeof judgeRunIdOrRun === 'object' && judgeRunIdOrRun !== null) {
        // New API: run object passed directly
        run = judgeRunIdOrRun;
        judgeRunId = run.judge_run_id;
        runIdToUse = judgeRunId || run.run_id;
    } else {
        // Old API: judgeRunId string passed
        judgeRunId = judgeRunIdOrRun;
        runIdToUse = judgeRunId;

        if (!judgeRunId) {
            return null;
        }

        const index = dataCache.index || await loadIndex();
        run = index.runs.find(r => r.judge_run_id === judgeRunId);

        if (!run) {
            throw new Error(`Judge run ${judgeRunId} not found`);
        }
    }

    const cacheKey = `${run.judge_mode}:${run.judge_model}:${runIdToUse}:${prId}`;
    if (dataCache.judges[cacheKey]) {
        return dataCache.judges[cacheKey];
    }

    try {
        const judgeModel = run.judge_model || 'default';
        const response = await fetch(`${API_BASE}/judges/${run.judge_mode}/${judgeModel}/${runIdToUse}/${prId}/judge.json`);

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
        // Pass run object instead of just IDs to support null edit_run_id/judge_run_id
        const edit = await loadEdit(run, prId);
        const judge = await loadJudge(run, prId);
        const sample = await loadSample(prId);

        if (edit) edits.push(edit);
        if (judge) judges.push(judge);
        if (sample) samples.push(sample);
    }

    return { summary, edits, judges, samples };
}

/**
 * Load all edits and judges for a run by summary path
 */
async function loadRunDetailsByPath(summaryPath) {
    const summary = await loadSummaryByPath(summaryPath);
    if (!summary) {
        return null;
    }

    const index = dataCache.index || await loadIndex();
    const run = index.runs.find(r => (r.summary_path || r.run_id) === summaryPath);

    if (!run || !run.pr_ids) {
        return { summary, edits: [], judges: [], samples: [] };
    }

    const edits = [];
    const judges = [];
    const samples = [];

    for (const prId of run.pr_ids) {
        // Pass run object instead of just IDs to support null edit_run_id/judge_run_id
        const edit = await loadEdit(run, prId);
        const judge = await loadJudge(run, prId);
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
        // Load summary directly from the summary_path if available
        if (run.summary_path) {
            try {
                const response = await fetch(`${API_BASE}/${run.summary_path}`);
                if (response.ok) {
                    const summary = await response.json();
                    // Add summary_path to the summary object for unique identification
                    summary.summary_path = run.summary_path;
                    summaries.push(summary);
                }
            } catch (error) {
                console.error(`Error loading summary from ${run.summary_path}:`, error);
            }
        } else {
            // Fallback to loadSummary for backward compatibility
            const summary = await loadSummary(run.run_id);
            if (summary) {
                // Add summary_path for consistency
                summary.summary_path = run.run_id;
                summaries.push(summary);
            }
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

