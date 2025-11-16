/**
 * Main application logic for Long-Context-Bench web app
 */

// Global state
let currentSummaries = [];
let filteredSummaries = [];
let currentSort = { field: 'win_rate', ascending: false };
let crossAgentAnalyses = [];
let crossAgentLeaderboard = [];
let headToHeadLeaderboard = [];

// Lazy loading state
let leaderboardDisplayCount = 3; // Start with top 3
let crossAgentDisplayCount = 10; // Start with top 10
const LEADERBOARD_INCREMENT = 10;
const CROSS_AGENT_INCREMENT = 20;

/**
 * Load and display leaderboard (cross-agent analysis)
 */
async function loadLeaderboard() {
    try {
        const index = await loadIndex();

        // Load and display agent leaderboard
        await loadAgentLeaderboard();

        // Load cross-agent analyses
        await loadCrossAgentAnalyses();

        // Update timestamp
        document.getElementById('last-updated').textContent = formatTimestamp(index.last_updated);
    } catch (error) {
        console.error('Error loading leaderboard:', error);
        const listContainer = document.getElementById('analysis-list');
        if (listContainer) {
            listContainer.innerHTML = '<p class="loading">Error loading data. Make sure the benchmark has been run.</p>';
        }
    }
}

/**
 * Load and display agent leaderboard
 */
async function loadAgentLeaderboard() {
    const tbody = document.getElementById('leaderboard-body');

    try {
        const analyses = await loadAllCrossAgentAnalyses();

        if (!analyses || analyses.length === 0) {
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="6" class="loading">No analyses found</td></tr>';
            }
            return;
        }

        // Compute agent statistics
        const agentStats = computeAgentLeaderboard(analyses);

        // Display leaderboard
        displayAgentLeaderboard(agentStats);
    } catch (error) {
        console.error('Error loading agent leaderboard:', error);
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading">Error loading leaderboard</td></tr>';
        }
    }
}

/**
 * Compute agent leaderboard statistics from cross-agent analyses
 */
function computeAgentLeaderboard(analyses) {
    const agentStats = {};

    // First pass: collect all agents that participated in each PR
    const prAgents = {};
    analyses.forEach(analysis => {
        if (!analysis.agent_results) return;
        const prKey = `${analysis.repo_url}:${analysis.pr_number}`;
        prAgents[prKey] = {
            agents: analysis.agent_results.map(r => `${r.runner}:${r.model}`),
            bestAgent: analysis.comparative_analysis?.best_agent || null
        };
    });

    // Second pass: aggregate statistics for each agent
    analyses.forEach(analysis => {
        if (!analysis.agent_results) return;

        const prKey = `${analysis.repo_url}:${analysis.pr_number}`;
        const prInfo = prAgents[prKey];

        analysis.agent_results.forEach(result => {
            const agentKey = `${result.runner}:${result.model}`;

            if (!agentStats[agentKey]) {
                agentStats[agentKey] = {
                    runner: result.runner,
                    model: result.model,
                    totalScore: 0,
                    prCount: 0,
                    wins: 0,
                    losses: 0,
                    ties: 0,
                    scores: []
                };
            }

            // Add score if available
            if (typeof result.aggregate === 'number') {
                agentStats[agentKey].totalScore += result.aggregate;
                agentStats[agentKey].scores.push(result.aggregate);
                agentStats[agentKey].prCount++;
            }

            // Determine win/loss/tie for this PR
            if (prInfo.bestAgent) {
                if (prInfo.bestAgent === agentKey) {
                    // This agent won
                    agentStats[agentKey].wins++;
                } else if (prInfo.bestAgent.includes('tie') || prInfo.bestAgent.includes('Tie')) {
                    // It's a tie
                    agentStats[agentKey].ties++;
                } else {
                    // This agent lost
                    agentStats[agentKey].losses++;
                }
            } else {
                // No best agent determined, count as tie
                agentStats[agentKey].ties++;
            }
        });
    });

    // Compute derived statistics
    const leaderboard = Object.keys(agentStats).map(agentKey => {
        const stats = agentStats[agentKey];
        const meanScore = stats.prCount > 0 ? stats.totalScore / stats.prCount : 0;
        const winRate = stats.prCount > 0 ? stats.wins / stats.prCount : 0;

        return {
            agentKey,
            runner: stats.runner,
            model: stats.model,
            meanScore,
            prCount: stats.prCount,
            wins: stats.wins,
            losses: stats.losses,
            ties: stats.ties,
            winRate
        };
    });

    // Sort by win rate (descending), then by mean score
    leaderboard.sort((a, b) => {
        if (b.winRate !== a.winRate) {
            return b.winRate - a.winRate;
        }
        return b.meanScore - a.meanScore;
    });

    return leaderboard;
}

/**
 * Display agent leaderboard table
 */
function displayAgentLeaderboard(leaderboard) {
    const tbody = document.getElementById('leaderboard-body');
    if (!tbody) return;

    if (!leaderboard || leaderboard.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="loading">No agents found</td></tr>';
        return;
    }

    tbody.innerHTML = '';

    const medals = ['🥇', '🥈', '🥉'];

    leaderboard.forEach((agent, index) => {
        const row = document.createElement('tr');
        const rankDisplay = index < 3 ? `${medals[index]} ${index + 1}` : `${index + 1}`;

        row.innerHTML = `
            <td>${rankDisplay}</td>
            <td><strong>${formatPercentage(agent.winRate)}</strong></td>
            <td><strong>${agent.runner}:${agent.model}</strong></td>
            <td>${agent.wins}</td>
            <td>${agent.losses}</td>
            <td>${agent.ties}</td>
            <td>${formatScore(agent.meanScore)}</td>
            <td>${agent.prCount}</td>
        `;

        tbody.appendChild(row);
    });
}

/**
 * Load and display cross-agent analyses
 * Note: This function is defined in both app.js and cross-agent.js
 * The cross-agent.js version is used on the cross-agent.html page
 * This version is used on the index.html page
 */
async function loadCrossAgentAnalyses() {
    try {
        const analyses = await loadAllCrossAgentAnalyses();

        if (!analyses || analyses.length === 0) {
            const listContainer = document.getElementById('analysis-list');
            if (listContainer) {
                listContainer.innerHTML = '<p class="loading">No cross-agent analyses found. Run cross-agent analysis first.</p>';
            }
            return;
        }

        // Set currentAnalyses for the detail view to work
        currentAnalyses = analyses;

        // Display list of PRs with cross-agent analyses
        // Use the function from cross-agent.js
        if (typeof displayAnalysisList === 'function') {
            displayAnalysisList(analyses);
        } else {
            console.error('displayAnalysisList function not found');
        }
    } catch (error) {
        console.error('Error loading cross-agent analyses:', error);
        const listContainer = document.getElementById('analysis-list');
        if (listContainer) {
            listContainer.innerHTML = '<p class="loading">Error loading cross-agent analyses</p>';
        }
    }
}

/**
 * Update overview statistics
 */
function updateOverviewStats(index, summaries) {
    document.getElementById('total-runs').textContent = summaries.length;

    const uniqueAgents = new Set();
    summaries.forEach(s => {
        if (s.runner && s.model) {
            uniqueAgents.add(`${s.runner}:${s.model}`);
        }
    });
    document.getElementById('total-agents').textContent = uniqueAgents.size;

    const totalSamples = summaries.reduce((sum, s) => sum + (s.total_samples || 0), 0);
    document.getElementById('total-samples').textContent = totalSamples;

    const avgAggregateScore = summaries.length > 0
        ? summaries.reduce((sum, s) => sum + (s.mean_aggregate || 0), 0) / summaries.length
        : 0;
    document.getElementById('avg-aggregate-score').innerHTML = formatScore(avgAggregateScore);

    const avgSuccessRate = summaries.length > 0
        ? summaries.reduce((sum, s) => sum + (s.success_rate || 0), 0) / summaries.length
        : 0;
    document.getElementById('avg-success-rate').textContent = formatPercentage(avgSuccessRate);
}

/**
 * Populate filter dropdowns
 */
function populateFilters(index) {
    const runners = getUniqueValues(index.runs, 'runner');
    const models = getUniqueValues(index.runs, 'model');
    const labels = getUniqueValues(index.runs, 'test_label');

    populateSelect('filter-runner', runners);
    populateSelect('filter-model', models);
    populateSelect('filter-label', labels);
}

/**
 * Populate a select element
 */
function populateSelect(selectId, values) {
    const select = document.getElementById(selectId);
    if (!select) return;

    // Keep the "All" option
    const currentValue = select.value;
    select.innerHTML = '<option value="">All</option>';

    values.forEach(value => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
    });

    select.value = currentValue;
}

/**
 * Display leaderboard table with lazy loading
 */
function displayLeaderboard(summaries, limit = null) {
    const tbody = document.getElementById('leaderboard-body');
    if (!tbody) return;

    if (summaries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="loading">No runs found</td></tr>';
        return;
    }

    // Sort summaries by win rate (descending) by default
    const sorted = [...summaries].sort((a, b) => {
        const aVal = a[currentSort.field] || 0;
        const bVal = b[currentSort.field] || 0;
        return currentSort.ascending ? aVal - bVal : bVal - aVal;
    });

    // Apply limit for lazy loading
    const displayLimit = limit || leaderboardDisplayCount;
    const itemsToDisplay = sorted.slice(0, displayLimit);
    const hasMore = sorted.length > displayLimit;

    tbody.innerHTML = '';
    itemsToDisplay.forEach((summary, index) => {
        const row = document.createElement('tr');

        // Check if this is cross-agent data or regular summary
        const isCrossAgent = summary.wins !== undefined;

        // Medal emojis for top 3
        const medals = ['🥇', '🥈', '🥉'];
        const rankDisplay = index < 3 ? `${medals[index]} ${index + 1}` : `${index + 1}`;

        if (isCrossAgent) {
            row.innerHTML = `
                <td>${rankDisplay}</td>
                <td>${summary.runner || '-'}</td>
                <td>${summary.model || '-'}</td>
                <td>${formatPercentage(summary.win_rate)}</td>
                <td>${summary.wins || 0}</td>
                <td>${formatScore(summary.mean_correctness)}</td>
                <td>${formatScore(summary.mean_completeness)}</td>
                <td>${formatScore(summary.mean_code_reuse)}</td>
            `;
        } else {
            row.innerHTML = `
                <td>${rankDisplay}</td>
                <td>${summary.runner || '-'}</td>
                <td>${summary.model || '-'}</td>
                <td>-</td>
                <td>-</td>
                <td>${formatScore(summary.mean_correctness)}</td>
                <td>${formatScore(summary.mean_completeness)}</td>
                <td>${formatScore(summary.mean_code_reuse)}</td>
            `;
        }

        tbody.appendChild(row);
    });

    // Add "Load More" button if there are more items
    if (hasMore) {
        const loadMoreRow = document.createElement('tr');
        loadMoreRow.innerHTML = `
            <td colspan="8" style="text-align: center; padding: 16px;">
                <button class="btn-secondary" onclick="loadMoreLeaderboard()">
                    Load More (${sorted.length - displayLimit} remaining)
                </button>
            </td>
        `;
        tbody.appendChild(loadMoreRow);
    }

    // Add sort handlers
    document.querySelectorAll('th.sortable').forEach(th => {
        th.onclick = () => {
            const field = th.dataset.sort;
            if (currentSort.field === field) {
                currentSort.ascending = !currentSort.ascending;
            } else {
                currentSort.field = field;
                currentSort.ascending = false;
            }
            displayLeaderboard(filteredSummaries.length > 0 ? filteredSummaries : currentSummaries);
        };
    });
}

/**
 * Load more leaderboard entries
 */
function loadMoreLeaderboard() {
    leaderboardDisplayCount += LEADERBOARD_INCREMENT;
    displayLeaderboard(filteredSummaries.length > 0 ? filteredSummaries : currentSummaries);
}

/**
 * Update leaderboard charts based on current summaries and controls
 */
function updateLeaderboardCharts() {
    const summariesToUse = filteredSummaries.length > 0 ? filteredSummaries : currentSummaries;
    if (summariesToUse.length === 0) return;

    // Sort by aggregate score to get top performers
    const sorted = [...summariesToUse].sort((a, b) => (b.mean_aggregate || 0) - (a.mean_aggregate || 0));

    // Create cross-agent comparison charts
    createBarComparisonChart('bar-comparison-chart', sorted);
    createRadarChart('radar-chart', sorted);
}

/**
 * Filter leaderboard
 */
function filterLeaderboard() {
    const label = document.getElementById('test-label-filter')?.value;

    if (!label) {
        filteredSummaries = [];
        displayLeaderboard(currentSummaries);
        updateLeaderboardCharts();
        return;
    }

    filteredSummaries = currentSummaries.filter(s => s.test_label === label);

    displayLeaderboard(filteredSummaries);
    updateLeaderboardCharts();
}

/**
 * Load run selector for summary page
 */
async function loadRunSelector() {
    try {
        const index = await loadIndex();
        const select = document.getElementById('run-selector');

        if (!select) return;

        select.innerHTML = '<option value="">Select a run...</option>';

        index.runs.forEach(run => {
            const option = document.createElement('option');
            // Use summary_path as unique identifier
            option.value = run.summary_path || run.run_id;
            option.textContent = `${run.runner || 'Unknown'} / ${run.model || 'Unknown'} - ${run.test_label || run.run_id}`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading run selector:', error);
    }
}

/**
 * Load and display run summary
 * @param {string} identifier - Either run_id or summary_path
 */
async function loadRunSummary(identifier) {
    try {
        // Check if identifier is a summary_path or run_id
        const data = identifier.startsWith('summaries/')
            ? await loadRunDetailsByPath(identifier)
            : await loadRunDetails(identifier);

        if (!data || !data.summary) {
            alert('Failed to load run data');
            return;
        }

        const { summary, edits, judges, samples } = data;

        // Update run info
        document.getElementById('info-run-id').textContent = summary.run_id || '-';
        document.getElementById('info-runner').textContent = summary.runner || '-';
        document.getElementById('info-model').textContent = summary.model || '-';
        document.getElementById('info-test-label').textContent = summary.test_label || '-';
        document.getElementById('info-edit-run-id').textContent = summary.edit_run_id || '-';
        document.getElementById('info-judge-run-id').textContent = summary.judge_run_id || '-';

        // Update metrics
        document.getElementById('metric-aggregate').textContent = summary.mean_aggregate.toFixed(2);
        document.getElementById('metric-std').textContent = summary.std_aggregate.toFixed(2);
        document.getElementById('metric-success-rate').textContent = formatPercentage(summary.success_rate);
        document.getElementById('metric-successful').textContent = summary.successful_samples;
        document.getElementById('metric-total').textContent = summary.total_samples;
        document.getElementById('metric-correctness').textContent = summary.mean_correctness.toFixed(2);
        document.getElementById('metric-completeness').textContent = summary.mean_completeness.toFixed(2);
        document.getElementById('metric-code-reuse').textContent = summary.mean_code_reuse.toFixed(2);
        document.getElementById('metric-best-practices').textContent = summary.mean_best_practices.toFixed(2);
        document.getElementById('metric-unsolicited-docs').textContent = summary.mean_unsolicited_docs.toFixed(2);
        document.getElementById('metric-tasks-per-hour').textContent = summary.tasks_per_hour.toFixed(2);
        document.getElementById('metric-elapsed').textContent = summary.mean_elapsed_ms.toFixed(0);

        // Update charts
        createScoreBreakdownChart('score-breakdown-chart', summary);
        createRunScoreDistribution('score-distribution-chart', judges);

        // Display PR results
        displayPRResults(edits, judges, samples);

        // Update timestamp
        const index = await loadIndex();
        document.getElementById('last-updated').textContent = formatTimestamp(index.last_updated);
    } catch (error) {
        console.error('Error loading run summary:', error);
        alert('Error loading run summary');
    }
}

/**
 * Display PR results table
 */
function displayPRResults(edits, judges, samples) {
    const tbody = document.getElementById('pr-results-body');
    if (!tbody) return;

    if (edits.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" class="loading">No results found</td></tr>';
        return;
    }

    tbody.innerHTML = '';

    edits.forEach(edit => {
        const judge = judges.find(j => j.pr_number === edit.pr_number);
        const sample = samples.find(s => s.pr_number === edit.pr_number);

        // Get run_id from URL params
        const urlParams = new URLSearchParams(window.location.search);
        const runId = urlParams.get('run_id') || document.getElementById('run-selector')?.value;

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${edit.pr_number}</td>
            <td>${edit.repo_url ? edit.repo_url.split('/').slice(-2).join('/') : '-'}</td>
            <td>${formatStatus(edit.status)}</td>
            <td>${judge ? formatScore(judge.aggregate) : '-'}</td>
            <td>${judge ? formatScore(judge.scores.correctness) : '-'}</td>
            <td>${judge ? formatScore(judge.scores.completeness) : '-'}</td>
            <td>${judge ? formatScore(judge.scores.code_reuse) : '-'}</td>
            <td>${judge ? formatScore(judge.scores.best_practices) : '-'}</td>
            <td>${judge ? formatScore(judge.scores.unsolicited_docs) : '-'}</td>
            <td>${edit.elapsed_ms || '-'}</td>
            <td><a href="task.html?run_id=${runId}&pr_number=${edit.pr_number}">View</a></td>
        `;
        tbody.appendChild(row);
    });
}

/**
 * Load comparison options
 */
async function loadComparisonOptions() {
    try {
        const index = await loadIndex();

        // Populate test label selector
        const testLabels = getUniqueValues(index.runs, 'test_label').filter(l => l);
        const labelSelect = document.getElementById('test-label-selector');
        if (labelSelect) {
            labelSelect.innerHTML = '<option value="">Select label...</option>';
            testLabels.forEach(label => {
                const option = document.createElement('option');
                option.value = label;
                option.textContent = label;
                labelSelect.appendChild(option);
            });
        }

        // Populate manual selection checkboxes
        const checkboxContainer = document.getElementById('run-checkboxes');
        if (checkboxContainer) {
            checkboxContainer.innerHTML = '';
            index.runs.forEach((run, idx) => {
                const label = document.createElement('label');
                label.style.display = 'block';
                label.style.marginBottom = '8px';

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                // Use summary_path as unique identifier (includes runner and model)
                checkbox.value = run.summary_path || run.run_id;
                checkbox.dataset.runIndex = idx; // Store index for lookup
                checkbox.style.marginRight = '8px';

                label.appendChild(checkbox);
                label.appendChild(document.createTextNode(
                    `${run.runner || 'Unknown'} / ${run.model || 'Unknown'} - ${run.test_label || run.run_id}`
                ));

                checkboxContainer.appendChild(label);
            });
        }
    } catch (error) {
        console.error('Error loading comparison options:', error);
    }
}

/**
 * Load and display comparison
 */
async function loadComparison() {
    try {
        const mode = document.getElementById('comparison-mode').value;
        let summaries = [];

        if (mode === 'test-label') {
            const testLabel = document.getElementById('test-label-selector').value;
            if (!testLabel) {
                alert('Please select a test label');
                return;
            }
            summaries = await getSummariesByTestLabel(testLabel);
        } else {
            // Manual selection
            const checkboxes = document.querySelectorAll('#run-checkboxes input[type="checkbox"]:checked');
            const summaryPaths = Array.from(checkboxes).map(cb => cb.value);

            if (summaryPaths.length < 2) {
                alert('Please select at least 2 runs to compare');
                return;
            }

            const index = await loadIndex();
            for (const summaryPath of summaryPaths) {
                // Find the run by summary_path
                const run = index.runs.find(r => (r.summary_path || r.run_id) === summaryPath);
                if (run) {
                    const summary = await loadSummaryByPath(summaryPath);
                    if (summary) summaries.push(summary);
                }
            }
        }

        if (summaries.length < 2) {
            alert('Need at least 2 runs to compare');
            return;
        }

        // Show comparison sections
        document.getElementById('comparison-summary').style.display = 'block';
        document.getElementById('comparison-table-section').style.display = 'block';
        document.getElementById('comparison-charts').style.display = 'block';

        // Update summary
        document.getElementById('agents-compared').textContent = summaries.length;
        document.getElementById('comparison-test-label').textContent =
            summaries[0].test_label || 'Mixed';
        document.getElementById('comparison-samples').textContent = summaries[0].total_samples;

        // Display comparison table
        displayComparisonTable(summaries);

        // Display charts
        createRadarChart('radar-chart', summaries);
        createBarComparisonChart('bar-comparison-chart', summaries);

        // Update timestamp
        const index = await loadIndex();
        document.getElementById('last-updated').textContent = formatTimestamp(index.last_updated);
    } catch (error) {
        console.error('Error loading comparison:', error);
        alert('Error loading comparison');
    }
}

/**
 * Display comparison table
 */
function displayComparisonTable(summaries) {
    const table = document.getElementById('comparison-table');
    if (!table) return;

    const thead = table.querySelector('thead tr');
    const tbody = document.getElementById('comparison-body');

    // Build header
    thead.innerHTML = '<th>Metric</th>';
    summaries.forEach(s => {
        const th = document.createElement('th');
        th.textContent = `${s.runner || 'Unknown'} (${s.model || 'Unknown'})`;
        thead.appendChild(th);
    });

    // Build rows
    const metrics = [
        { label: 'Aggregate Score', field: 'mean_aggregate', format: 'score' },
        { label: 'Success Rate', field: 'success_rate', format: 'percentage' },
        { label: 'Correctness', field: 'mean_correctness', format: 'score' },
        { label: 'Completeness', field: 'mean_completeness', format: 'score' },
        { label: 'Code Reuse', field: 'mean_code_reuse', format: 'score' },
        { label: 'Best Practices', field: 'mean_best_practices', format: 'score' },
        { label: 'Unsolicited Docs', field: 'mean_unsolicited_docs', format: 'score' },
        { label: 'Tasks/Hour', field: 'tasks_per_hour', format: 'number' }
    ];

    tbody.innerHTML = '';
    metrics.forEach(metric => {
        const row = document.createElement('tr');
        const labelCell = document.createElement('td');
        labelCell.textContent = metric.label;
        labelCell.style.fontWeight = '500';
        row.appendChild(labelCell);

        summaries.forEach(summary => {
            const cell = document.createElement('td');
            const value = summary[metric.field];

            if (metric.format === 'score') {
                cell.innerHTML = formatScore(value);
            } else if (metric.format === 'percentage') {
                cell.textContent = formatPercentage(value);
            } else {
                cell.textContent = value ? value.toFixed(2) : '-';
            }

            row.appendChild(cell);
        });

        tbody.appendChild(row);
    });
}

