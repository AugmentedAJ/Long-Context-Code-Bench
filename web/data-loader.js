/**
 * Data loading utilities for Long-Context-Bench web app
 */

// API base path - auto-detect based on environment
// Use /api when served by Node.js server (port 3000)
// Use empty string for static hosting from root (e.g., dist/)
// Use '..' for static hosting from output/web/ subdirectory
function detectApiBase() {
    if (window.location.port === '3000') {
        return '/api';  // Node.js server
    }
    // Check if index.json exists at root level (dist/ flat structure)
    // vs in parent directory (output/web/ structure)
    // For simplicity, assume flat structure for ports other than 3000
    return '.';
}
const API_BASE = detectApiBase();

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
            cross_agent_runs: [],
            head_to_head_runs: [],
            test_labels: [],
            runners: [],
            models: [],
            last_updated: new Date().toISOString()
        };
    }
}

/**
 * Load a summary file
 * @param {string|object} runIdOrRun - Either a run_id string or a run object with summary_path
 */
async function loadSummary(runIdOrRun) {
    // Determine the cache key and summary path
    let cacheKey;
    let summaryPath;

    if (typeof runIdOrRun === 'object' && runIdOrRun.summary_path) {
        // If a run object with summary_path is provided, use it directly
        cacheKey = runIdOrRun.summary_path;
        summaryPath = `${API_BASE}/${runIdOrRun.summary_path}`;
    } else {
        // Legacy: lookup by run_id
        const runId = typeof runIdOrRun === 'object' ? runIdOrRun.run_id : runIdOrRun;
        cacheKey = runId;

        // Try to find the summary_path from the index
        const index = dataCache.index || await loadIndex();
        const run = index.runs.find(r => r.run_id === runId);

        if (run && run.summary_path) {
            summaryPath = `${API_BASE}/${run.summary_path}`;
        } else {
            summaryPath = `${API_BASE}/summaries/${runId}/summary.json`;
        }
    }

    if (dataCache.summaries[cacheKey]) {
        return dataCache.summaries[cacheKey];
    }

    try {
        const response = await fetch(summaryPath);
        if (!response.ok) {
            throw new Error(`Failed to load summary from ${summaryPath}`);
        }

        const summary = await response.json();
        dataCache.summaries[cacheKey] = summary;
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
        const judgeMode = run.judge_mode || 'llm';
        const judgeModel = run.judge_model || 'claude-sonnet-4-5';
        const editRunId = run.edit_run_id || run.run_id;

        // Path structure: judges/{judge_mode}/{judge_model}/{judge_run_id}/{edit_run_id}/{pr_id}/judge.json
        const response = await fetch(`${API_BASE}/judges/${judgeMode}/${judgeModel}/${runIdToUse}/${editRunId}/${prId}/judge.json`);

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
    return `<span class="win-rate">${(value * 100).toFixed(1)}%</span>`;
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
 * Load the human (ground-truth) diff for a PR using repo_url and commit SHAs.
 *
 * This mirrors the GitHub compare API usage in task.js but lives in the
 * shared data-loader so it can be reused by multiple views (e.g. the
 * side-by-side inspector in the head-to-head UI).
 *
 * NOTE: This calls the public GitHub API and should only be invoked when the
 * user explicitly chooses to view the human diff.
 */
async function loadGroundTruthDiffFromCommits(repoUrl, baseCommit, headCommit) {
    if (!repoUrl || !baseCommit || !headCommit) {
        return null;
    }

    const cacheKey = `human_diff:${repoUrl}:${baseCommit}:${headCommit}`;
    if (dataCache[cacheKey]) {
        return dataCache[cacheKey];
    }

    try {
        const match = repoUrl.match(/github\.com\/([^/]+)\/([^/]+)/);
        if (!match) {
            console.warn('Unable to parse repo_url for ground truth diff', repoUrl);
            return null;
        }

        const owner = match[1];
        const repo = match[2].replace('.git', '');
        const url = `https://api.github.com/repos/${owner}/${repo}/compare/${baseCommit}...${headCommit}`;

        const response = await fetch(url);
        if (!response.ok) {
            console.warn('Failed to load ground truth diff from GitHub compare API:', response.status);
            return null;
        }

        const data = await response.json();
        if (!Array.isArray(data.files)) {
            return null;
        }

        let diff = '';
        for (const file of data.files) {
            if (file.patch) {
                diff += `diff --git a/${file.filename} b/${file.filename}\n`;
                diff += `--- a/${file.filename}\n+++ b/${file.filename}\n${file.patch}\n`;
            }
        }

        dataCache[cacheKey] = diff;
        return diff;
    } catch (error) {
        console.error('Error loading ground truth diff from commits:', error);
        return null;
    }
}

/**
 * Load all cross-agent analysis files
 */
async function loadAllCrossAgentAnalyses() {
    try {
        // Get index manifest which contains list of cross-agent analysis files
        const index = await loadIndex();

        if (!index.cross_agent_runs || index.cross_agent_runs.length === 0) {
            console.log('No cross-agent analyses found in index');
            return [];
        }

        const analyses = [];
        for (const run of index.cross_agent_runs) {
            try {
                const analysisResponse = await fetch(`${API_BASE}/cross_agent_analysis/${run.file}`);
                if (analysisResponse.ok) {
                    const analysis = await analysisResponse.json();
                    // Add metadata from index
                    analysis.analysis_run_id = run.analysis_run_id;
                    analyses.push(analysis);
                } else {
                    console.warn(`Failed to load ${run.file}: ${analysisResponse.status}`);
                }
            } catch (error) {
                console.error(`Error loading ${run.file}:`, error);
            }
        }

        return analyses;
    } catch (error) {
        console.error('Error loading cross-agent analyses:', error);
        return [];
    }
}

/**
 * Aggregate cross-agent analysis data by agent
 * Returns leaderboard data with aggregate scores per agent
 */
function aggregateCrossAgentData(analyses) {
    const agentStats = {};

    analyses.forEach(analysis => {
        if (!analysis.agent_results || !analysis.comparative_analysis) return;

        analysis.agent_results.forEach(result => {
            const agentKey = `${result.runner}:${result.model}`;

            if (!agentStats[agentKey]) {
                agentStats[agentKey] = {
                    runner: result.runner,
                    model: result.model,
                    total_tasks: 0,
                    total_aggregate: 0,
                    total_correctness: 0,
                    total_completeness: 0,
                    total_code_reuse: 0,
                    total_best_practices: 0,
                    total_unsolicited_docs: 0,
                    total_llm_rating: 0,
                    wins: 0,
                    tasks: []
                };
            }

            const stats = agentStats[agentKey];
            stats.total_tasks++;
            stats.total_aggregate += result.aggregate || 0;
            stats.total_correctness += result.scores?.correctness || 0;
            stats.total_completeness += result.scores?.completeness || 0;
            stats.total_code_reuse += result.scores?.code_reuse || 0;
            stats.total_best_practices += result.scores?.best_practices || 0;
            stats.total_unsolicited_docs += result.scores?.unsolicited_docs || 0;
            stats.total_llm_rating += result.llm_rating || 0;

            // Track if this agent won this task
            if (analysis.comparative_analysis.best_agent === agentKey) {
                stats.wins++;
            }

            stats.tasks.push({
                pr_number: analysis.pr_number,
                aggregate: result.aggregate,
                llm_rating: result.llm_rating
            });
        });
    });

    // Calculate averages
    const leaderboard = Object.values(agentStats).map(stats => ({
        runner: stats.runner,
        model: stats.model,
        total_tasks: stats.total_tasks,
        mean_aggregate: stats.total_aggregate / stats.total_tasks,
        mean_correctness: stats.total_correctness / stats.total_tasks,
        mean_completeness: stats.total_completeness / stats.total_tasks,
        mean_code_reuse: stats.total_code_reuse / stats.total_tasks,
        mean_best_practices: stats.total_best_practices / stats.total_tasks,
        mean_unsolicited_docs: stats.total_unsolicited_docs / stats.total_tasks,
        mean_llm_rating: stats.total_llm_rating / stats.total_tasks,
        wins: stats.wins,
        win_rate: stats.wins / stats.total_tasks,
        tasks: stats.tasks
    }));

    return leaderboard;
}

/**
 * Load head-to-head metadata (lightweight, for PR list and leaderboard).
 *
 * We support both dev-server and static-hosting layouts and are tolerant
 * of older deployments where the metadata file only exists under
 * `output/web/`.
 */
async function loadHeadToHeadMetadata() {
    const isDevServer = window.location.port === '3000';

    // Try a sequence of possible locations. We stop at the first one that
    // returns a valid metadata object with a `results` array.
    const candidateUrls = isDevServer
        ? [
            '/data/head_to_head_metadata.json',            // preferred (output/head_to_head_metadata.json)
            '/data/web/head_to_head_metadata.json',        // backwards-compat (output/web/head_to_head_metadata.json)
          ]
        : [
            'head_to_head_metadata.json',                  // preferred when index.html is in output/web/
            '../head_to_head_metadata.json',               // alternative relative path
            'web/head_to_head_metadata.json',              // older layouts
            '../web/head_to_head_metadata.json',
          ];

    for (const url of candidateUrls) {
        try {
            const response = await fetch(url);
            if (!response.ok) {
                continue;
            }

            const metadata = await response.json();
            if (metadata && Array.isArray(metadata.results)) {
                return metadata.results;
            }
        } catch (error) {
            console.warn('Error trying head-to-head metadata URL', url, error);
        }
    }

    console.warn('Head-to-head metadata not found via known URLs, falling back to loading all results');
    return await loadAllHeadToHeadResults();
}

/**
 * Load a single head-to-head result by PR number.
 */
async function loadHeadToHeadResult(prNumber) {
    try {
        // Check cache first
        const cacheKey = `h2h_${prNumber}`;
        if (dataCache[cacheKey]) {
            return dataCache[cacheKey];
        }

        // Find the file path from metadata or, if metadata is missing,
        // fall back to the full HeadToHeadPRResult objects.
        const metadata = await loadHeadToHeadMetadata();
        const prMeta = metadata.find(m => m.pr_number === prNumber);

        if (!prMeta) {
            console.error(`No metadata entry found for PR ${prNumber}`);
            return null;
        }

        // If there's no "file" field, assume this is already a full
        // HeadToHeadPRResult object returned by loadAllHeadToHeadResults.
        if (!prMeta.file) {
            dataCache[cacheKey] = prMeta;
            return prMeta;
        }

        const isDevServer = window.location.port === '3000';
        const base = isDevServer ? '/data' : '..';
        const response = await fetch(`${base}/${prMeta.file}`);
        if (!response.ok) {
            throw new Error(`Failed to load PR ${prNumber}: ${response.status}`);
        }

        const result = await response.json();

        // Cache the result
        dataCache[cacheKey] = result;

        return result;
    } catch (error) {
        console.error(`Error loading head-to-head result for PR ${prNumber}:`, error);
        return null;
    }
}

/**
 * Load all head-to-head result files (HeadToHeadPRResult artifacts).
 * This is the old method that loads everything at once - kept for backward compatibility.
 */
async function loadAllHeadToHeadResults() {
    try {
        const index = await loadIndex();

        if (!index.head_to_head_runs || index.head_to_head_runs.length === 0) {
            console.log('No head-to-head results found in index');
            return [];
        }

        const results = [];
        for (const run of index.head_to_head_runs) {
            try {
                const response = await fetch(`${API_BASE}/${run.file}`);
                if (response.ok) {
                    const result = await response.json();
                    // Attach metadata from index entry if not already present
                    if (run.head_to_head_run_id && !result.head_to_head_run_id) {
                        result.head_to_head_run_id = run.head_to_head_run_id;
                    }
                    results.push(result);
                } else {
                    console.warn(`Failed to load head-to-head result ${run.file}: ${response.status}`);
                }
            } catch (error) {
                console.error(`Error loading head-to-head result ${run.file}:`, error);
            }
        }

        return results;
    } catch (error) {
        console.error('Error loading head-to-head results:', error);
        return [];
    }
}

/**
 * Aggregate head-to-head results into per-agent Elo leaderboard.
 */
function aggregateHeadToHeadData(results) {
    const comparisons = [];
    results.forEach(result => {
        if (Array.isArray(result.pairwise_decisions)) {
            result.pairwise_decisions.forEach(decision => comparisons.push(decision));
        }
    });

    if (comparisons.length === 0) {
        return [];
    }

    const matrix = computeHeadToHeadWinLossMatrix(comparisons);
    const ratings = computeHeadToHeadEloRatings(comparisons);

    const leaderboard = Object.entries(matrix).map(([agentId, opponents]) => {
        let wins = 0;
        let losses = 0;
        let ties = 0;

        Object.values(opponents).forEach(stats => {
            wins += stats.wins;
            losses += stats.losses;
            ties += stats.ties;
        });

        const matches = wins + losses + ties;
        const winRate = matches > 0 ? (wins + 0.5 * ties) / matches : 0;

        const parts = agentId.split(':');
        const runner = parts[0] || '';
        const model = parts[1] || '';

        return {
            agent_id: agentId,
            runner,
            model,
            wins,
            losses,
            ties,
            matches,
            win_rate: winRate,
            elo_rating: ratings[agentId] ?? 1500.0,
        };
    });

    leaderboard.sort((a, b) => {
        if (b.elo_rating !== a.elo_rating) {
            return b.elo_rating - a.elo_rating;
        }
        return b.win_rate - a.win_rate;
    });

    return leaderboard;
}

/**
 * Compute head-to-head win/loss matrix (frontend version).
 */
function computeHeadToHeadWinLossMatrix(comparisons) {
    const matrix = {};

    comparisons.forEach(decision => {
        const a = decision.submission_a_id;
        const b = decision.submission_b_id;
        if (!a || !b) return;

        if (!matrix[a]) matrix[a] = {};
        if (!matrix[b]) matrix[b] = {};
        if (!matrix[a][b]) matrix[a][b] = { wins: 0, losses: 0, ties: 0 };
        if (!matrix[b][a]) matrix[b][a] = { wins: 0, losses: 0, ties: 0 };

        const winner = (decision.winner || '').toLowerCase();
        if (winner === 'a') {
            matrix[a][b].wins += 1;
            matrix[b][a].losses += 1;
        } else if (winner === 'b') {
            matrix[a][b].losses += 1;
            matrix[b][a].wins += 1;
        } else {
            matrix[a][b].ties += 1;
            matrix[b][a].ties += 1;
        }
    });

    return matrix;
}

/**
 * Compute Elo ratings from head-to-head comparisons (frontend version).
 */
function computeHeadToHeadEloRatings(comparisons, initialRating = 1500.0, kFactor = 32.0) {
    const ratings = {};

    function getRating(agentId) {
        if (!(agentId in ratings)) {
            ratings[agentId] = initialRating;
        }
        return ratings[agentId];
    }

    comparisons.forEach(decision => {
        const a = decision.submission_a_id;
        const b = decision.submission_b_id;
        if (!a || !b) return;

        const ra = getRating(a);
        const rb = getRating(b);

        const expectedA = 1.0 / (1.0 + Math.pow(10, (rb - ra) / 400.0));
        const expectedB = 1.0 - expectedA;

        const winner = (decision.winner || '').toLowerCase();
        let scoreA;
        let scoreB;
        if (winner === 'a') {
            scoreA = 1.0;
            scoreB = 0.0;
        } else if (winner === 'b') {
            scoreA = 0.0;
            scoreB = 1.0;
        } else {
            scoreA = 0.5;
            scoreB = 0.5;
        }

        ratings[a] = ra + kFactor * (scoreA - expectedA);
        ratings[b] = rb + kFactor * (scoreB - expectedB);
    });

    return ratings;
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

