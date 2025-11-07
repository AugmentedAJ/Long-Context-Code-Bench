/**
 * Cross-agent analysis page logic
 */

let currentAnalyses = [];
let currentAnalysis = null;
let agentScoresChart = null;

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
 * Display list of analyses
 */
function displayAnalysisList(analyses) {
    const container = document.getElementById('analysis-list');
    
    if (analyses.length === 0) {
        container.innerHTML = '<p class="empty-state">No cross-agent analyses found. Run <code>long-context-bench analyze-pr</code> to create one.</p>';
        return;
    }

    // Sort by PR number
    analyses.sort((a, b) => a.pr_number - b.pr_number);

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
                    ${analyses.map(analysis => {
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
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;

    container.innerHTML = html;
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
 * Display agent results table and chart
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

    // Create chart
    createAgentScoresChart(sortedResults);
}

/**
 * Create agent scores comparison chart
 */
function createAgentScoresChart(agentResults) {
    if (agentScoresChart) {
        agentScoresChart.destroy();
    }

    const ctx = document.getElementById('agent-scores-chart');
    if (!ctx) return;

    const labels = agentResults.map(r => `${r.runner}\n${r.model}`);
    
    agentScoresChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Correctness',
                    data: agentResults.map(r => r.scores.correctness),
                    backgroundColor: 'rgba(54, 162, 235, 0.7)'
                },
                {
                    label: 'Completeness',
                    data: agentResults.map(r => r.scores.completeness),
                    backgroundColor: 'rgba(75, 192, 192, 0.7)'
                },
                {
                    label: 'Code Reuse',
                    data: agentResults.map(r => r.scores.code_reuse),
                    backgroundColor: 'rgba(255, 206, 86, 0.7)'
                },
                {
                    label: 'Best Practices',
                    data: agentResults.map(r => r.scores.best_practices),
                    backgroundColor: 'rgba(153, 102, 255, 0.7)'
                },
                {
                    label: 'Unsolicited Docs',
                    data: agentResults.map(r => r.scores.unsolicited_docs),
                    backgroundColor: 'rgba(255, 159, 64, 0.7)'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: {
                    beginAtZero: true,
                    min: -1,
                    max: 1
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Score Breakdown by Agent'
                }
            }
        }
    });
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
            <div class="agent-detail-content">
                <div class="metric-card">
                    <div class="stat-label">Status</div>
                    <div class="stat-value"><span class="badge badge-${result.status}">${result.status}</span></div>
                </div>
                <div class="metric-card">
                    <div class="stat-label">Aggregate Score</div>
                    <div class="stat-value">${result.aggregate.toFixed(2)}</div>
                </div>
                <div class="metric-card">
                    <div class="stat-label">Time</div>
                    <div class="stat-value">${(result.elapsed_ms / 1000).toFixed(1)}s</div>
                </div>
            </div>
            ${result.rationale ? `
                <div class="rationale-section">
                    <h5>Judge Rationale</h5>
                    <p>${result.rationale}</p>
                </div>
            ` : ''}
            <details>
                <summary>View Diff</summary>
                <pre class="code-block">${escapeHtml(result.patch_unified)}</pre>
            </details>
            ${result.logs_path ? `
                <details>
                    <summary>View Agent Logs</summary>
                    <div id="logs-${agentId}" class="logs-container">
                        <div style="text-align: center; padding: 20px; color: #666;">
                            <em>Loading logs...</em>
                        </div>
                    </div>
                </details>
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

