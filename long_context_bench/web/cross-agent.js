/**
 * Cross-agent analysis page logic
 */

let currentAnalyses = [];
let currentAnalysis = null;

// Lazy loading state for cross-agent analysis list
let analysisDisplayCount = 10; // Start with top 10
const ANALYSIS_INCREMENT = 20;

/**
 * Load all cross-agent analyses
 */
async function loadCrossAgentAnalyses() {
    try {
        const analyses = await loadAllCrossAgentAnalyses();
        currentAnalyses = analyses;
        displayAnalysisList(analyses);
    } catch (error) {
        console.error('Error loading cross-agent analyses:', error);
        document.getElementById('analysis-list').innerHTML = '<p class="error">Failed to load analyses</p>';
    }
}

/**
 * Display list of analyses with lazy loading
 */
function displayAnalysisList(analyses, limit = null) {
    const container = document.getElementById('analysis-list');

    if (analyses.length === 0) {
        container.innerHTML = '<p class="empty-state">No cross-agent analyses found. Run <code>long-context-bench analyze-pr</code> to create one.</p>';
        return;
    }

    // Sort by PR number
    analyses.sort((a, b) => a.pr_number - b.pr_number);

    // Apply limit for lazy loading
    const displayLimit = limit || analysisDisplayCount;
    const itemsToDisplay = analyses.slice(0, displayLimit);
    const hasMore = analyses.length > displayLimit;

    const tableRows = itemsToDisplay.map(analysis => {
        // Get best agent and summary if available
        const bestAgentName = analysis.comparative_analysis ? analysis.comparative_analysis.best_agent : null;
        const comparativeSummary = analysis.comparative_analysis && analysis.comparative_analysis.summary
            ? analysis.comparative_analysis.summary
            : 'N/A';

        return `
            <tr>
                <td><strong>${analysis.pr_number}</strong></td>
                <td>${bestAgentName || 'N/A'}</td>
                <td style="max-width: 600px; font-size: 0.9em;">${comparativeSummary}</td>
                <td>
                    <button class="btn-primary" onclick="showAnalysisDetail('${analysis.analysis_run_id}')">
                        View Details
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    const loadMoreButton = hasMore ? `
        <tr>
            <td colspan="4" style="text-align: center; padding: 16px;">
                <button class="btn-secondary" onclick="loadMoreAnalyses()">
                    Load More (${analyses.length - displayLimit} remaining)
                </button>
            </td>
        </tr>
    ` : '';

    const html = `
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>PR Number</th>
                        <th>Best Agent</th>
                        <th>Summary</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${tableRows}
                    ${loadMoreButton}
                </tbody>
            </table>
        </div>
    `;

    container.innerHTML = html;
}

/**
 * Load more analyses
 */
function loadMoreAnalyses() {
    analysisDisplayCount += ANALYSIS_INCREMENT;
    displayAnalysisList(currentAnalyses);
}

/**
 * Show analysis detail view
 */
async function showAnalysisDetail(analysisRunId) {
    const analysis = currentAnalyses.find(a => a.analysis_run_id === analysisRunId);
    if (!analysis) {
        console.error('Analysis not found:', analysisRunId);
        return;
    }

    currentAnalysis = analysis;

    // Hide list, show detail
    document.getElementById('analysis-list').style.display = 'none';
    document.getElementById('analysis-detail').style.display = 'block';

    // Update title
    document.getElementById('detail-title').textContent = `PR ${analysis.pr_number} - Cross-Agent Analysis`;

    // Display task instructions
    document.getElementById('task-instructions').textContent = analysis.task_instructions;

    // Display comparative analysis if available
    if (analysis.comparative_analysis) {
        document.getElementById('comparative-section').style.display = 'block';
        document.getElementById('best-agent').textContent = analysis.comparative_analysis.best_agent;
        document.getElementById('comparative-summary').textContent = analysis.comparative_analysis.summary;
        document.getElementById('best-agent-reasoning').textContent = analysis.comparative_analysis.best_agent_reasoning;
        document.getElementById('approach-differences').textContent = analysis.comparative_analysis.approach_differences;
    } else {
        document.getElementById('comparative-section').style.display = 'none';
    }

    // Display agent results
    displayAgentResults(analysis.agent_results, analysis.comparative_analysis);

    // Display individual agent details
    displayAgentDetails(analysis.agent_results);
}

/**
 * Display agent results table
 */
function displayAgentResults(agentResults, comparativeAnalysis) {
    // Sort by aggregate score (descending)
    const sortedResults = [...agentResults].sort((a, b) => b.aggregate - a.aggregate);

    // Create ranking based on comparative analysis if available
    const ranking = comparativeAnalysis ? comparativeAnalysis.ranking : [];

    // Populate table
    const tbody = document.getElementById('agent-results-body');
    tbody.innerHTML = sortedResults.map((result, index) => {
        const agentName = `${result.runner}:${result.model}`;
        const rankInComparative = ranking.indexOf(agentName) + 1;
        const displayRank = rankInComparative > 0 ? rankInComparative : index + 1;

        // Format LLM rating and summary
        const llmRating = result.llm_rating !== null && result.llm_rating !== undefined
            ? `<strong>${result.llm_rating.toFixed(2)}</strong>`
            : '<span style="color: #999;">N/A</span>';
        const llmSummary = result.llm_summary
            ? `<span style="font-size: 0.9em;">${result.llm_summary}</span>`
            : '<span style="color: #999;">N/A</span>';

        return `
            <tr>
                <td><strong>${displayRank}</strong></td>
                <td>${result.runner}<br><small>${result.model}</small></td>
                <td><span class="badge badge-${result.status}">${result.status}</span></td>
                <td>${llmRating}</td>
                <td style="max-width: 300px;">${llmSummary}</td>
                <td><strong>${result.aggregate.toFixed(2)}</strong></td>
                <td>${result.scores.correctness.toFixed(2)}</td>
                <td>${result.scores.completeness.toFixed(2)}</td>
                <td>${result.scores.code_reuse.toFixed(2)}</td>
                <td>${result.scores.best_practices.toFixed(2)}</td>
                <td>${result.scores.unsolicited_docs.toFixed(2)}</td>
                <td>${(result.elapsed_ms / 1000).toFixed(1)}</td>
            </tr>
        `;
    }).join('');
}

/**
 * Display individual agent details
 */
function displayAgentDetails(agentResults) {
    const container = document.getElementById('agent-details-container');

    const html = agentResults.map(result => {
        const agentId = `${result.runner}-${result.model}-${result.edit_run_id}`.replace(/[^a-zA-Z0-9-]/g, '-');

        return `
        <div class="card">
            <h4>${result.runner}:${result.model}</h4>
            ${result.rationale ? `
                <div class="rationale-section">
                    <h5>Judge Rationale</h5>
                    <p>${result.rationale}</p>
                </div>
            ` : ''}
            <div class="agent-actions">
                <button class="btn-action" onclick="toggleSection('diff-${agentId}')">
                    <span class="btn-icon">📄</span> View Diff
                </button>
                ${result.logs_path ? `
                    <button class="btn-action" onclick="toggleSection('logs-${agentId}')">
                        <span class="btn-icon">📋</span> View Logs
                    </button>
                ` : ''}
            </div>
            <div id="diff-${agentId}" class="collapsible-section" style="display: none;">
                <pre class="code-block">${colorizeDiff(result.patch_unified)}</pre>
            </div>
            ${result.logs_path ? `
                <div id="logs-${agentId}" class="collapsible-section logs-container" style="display: none;">
                    <div style="text-align: center; padding: 20px; color: #666;">
                        <em>Loading logs...</em>
                    </div>
                </div>
            ` : ''}
        </div>
        `;
    }).join('');

    container.innerHTML = html;

    // Load logs for each agent that has logs_path
    agentResults.forEach(result => {
        if (result.logs_path) {
            const agentId = `${result.runner}-${result.model}-${result.edit_run_id}`.replace(/[^a-zA-Z0-9-]/g, '-');
            loadAgentLogs(result.logs_path, agentId);
        }
    });
}

/**
 * Load and display agent logs
 */
async function loadAgentLogs(logsPath, agentId) {
    const container = document.getElementById(`logs-${agentId}`);

    try {
        const response = await fetch(`${API_BASE}/${logsPath}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const text = await response.text();
        const lines = text.trim().split('\n');
        const logEntries = lines.map(line => {
            try {
                return JSON.parse(line);
            } catch (e) {
                return { raw: line };
            }
        });

        container.innerHTML = formatLogs(logEntries);
    } catch (error) {
        container.innerHTML = `
            <div style="color: #d32f2f; padding: 10px;">
                <strong>Error loading logs:</strong> ${error.message}
            </div>
        `;
    }
}

/**
 * Format JSONL log entries for display
 */
function formatLogs(logEntries) {
    if (!logEntries || logEntries.length === 0) {
        return '<div style="padding: 10px; color: #666;"><em>No logs available</em></div>';
    }

    const html = logEntries.map(entry => {
        if (entry.raw) {
            // Unparseable line
            return `<div class="log-entry log-raw">${escapeHtml(entry.raw)}</div>`;
        }

        const timestamp = entry.timestamp
            ? new Date(entry.timestamp * 1000).toISOString().replace('T', ' ').substring(0, 19)
            : '';
        const event = entry.event || 'unknown';

        let content = '';
        let eventClass = 'log-info';

        if (event === 'agent_start') {
            eventClass = 'log-start';
            content = `<strong>Agent Started</strong><br>
                Runner: ${entry.runner || 'N/A'}<br>
                Model: ${entry.model || 'N/A'}<br>
                Timeout: ${entry.timeout_s || 'N/A'}s`;
        } else if (event === 'agent_end') {
            eventClass = entry.exit_code === 0 ? 'log-success' : 'log-error';
            content = `<strong>Agent Ended</strong><br>
                Exit Code: ${entry.exit_code !== undefined ? entry.exit_code : 'N/A'}`;
        } else if (event === 'agent_run') {
            eventClass = 'log-output';
            const output = entry.stdout || entry.stderr || '';
            content = `<strong>Agent Output</strong><br>
                <pre class="log-output-text">${escapeHtml(output)}</pre>`;
        } else {
            // Generic event
            content = `<strong>${event}</strong><br>
                <pre class="log-output-text">${escapeHtml(JSON.stringify(entry, null, 2))}</pre>`;
        }

        return `
            <div class="log-entry ${eventClass}">
                <div class="log-timestamp">${timestamp}</div>
                <div class="log-content">${content}</div>
            </div>
        `;
    }).join('');

    return `<div class="logs-list">${html}</div>`;
}

/**
 * Show analysis list view
 */
function showAnalysisList() {
    document.getElementById('analysis-list').style.display = 'block';
    document.getElementById('analysis-detail').style.display = 'none';
    currentAnalysis = null;
}

/**
 * Helper: Get repository name from URL
 */
function getRepoName(url) {
    const match = url.match(/github\.com\/([^\/]+\/[^\/]+)/);
    return match ? match[1].replace('.git', '') : url;
}

/**
 * Helper: Format timestamp
 */
function formatTimestamp(timestamp) {
    return new Date(timestamp).toLocaleString();
}

/**
 * Helper: Escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Toggle collapsible section visibility
 */
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.style.display = section.style.display === 'none' ? 'block' : 'none';
    }
}

/**
 * Colorize diff text with git-style formatting
 */
function colorizeDiff(diffText) {
    if (!diffText) return '';

    const lines = diffText.split('\n');
    const colorizedLines = lines.map(line => {
        if (line.startsWith('+') && !line.startsWith('+++')) {
            return `<span class="diff-line-add">${escapeHtml(line)}</span>`;
        } else if (line.startsWith('-') && !line.startsWith('---')) {
            return `<span class="diff-line-del">${escapeHtml(line)}</span>`;
        } else if (line.startsWith('@@')) {
            return `<span class="diff-line-hunk">${escapeHtml(line)}</span>`;
        } else if (line.startsWith('diff ') || line.startsWith('index ') ||
                   line.startsWith('---') || line.startsWith('+++')) {
            return `<span class="diff-line-meta">${escapeHtml(line)}</span>`;
        } else {
            return escapeHtml(line);
        }
    });

    return colorizedLines.join('\n');
}

