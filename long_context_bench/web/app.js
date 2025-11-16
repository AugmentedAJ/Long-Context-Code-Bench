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
 * Load and display leaderboard (head-to-head only)
 */
async function loadLeaderboard() {
    try {
        const index = await loadIndex();

        // Load head-to-head results
        await loadHeadToHeadLeaderboard();

        // Load head-to-head PR details
        if (typeof loadHeadToHeadPRDetails === 'function') {
            await loadHeadToHeadPRDetails();
        }

        // Update timestamp
        document.getElementById('last-updated').textContent = formatTimestamp(index.last_updated);
    } catch (error) {
        console.error('Error loading leaderboard:', error);
        const tbody = document.getElementById('h2h-leaderboard-body');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading">Error loading data. Make sure the benchmark has been run.</td></tr>';
        }
    }
}

/**
 * Load and display head-to-head leaderboard (Elo-based).
 */
async function loadHeadToHeadLeaderboard() {
    const tbody = document.getElementById('h2h-leaderboard-body');

    try {
        const results = await loadAllHeadToHeadResults();

        if (!results || results.length === 0) {
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="7" class="loading">No head-to-head results found. Run head-to-head evaluation first.</td></tr>';
            }
            return;
        }

        headToHeadLeaderboard = aggregateHeadToHeadData(results);
        displayHeadToHeadLeaderboard(headToHeadLeaderboard);
    } catch (error) {
        console.error('Error loading head-to-head leaderboard:', error);
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading">Error loading head-to-head results</td></tr>';
        }
    }
}

/**
 * Display head-to-head leaderboard table.
 */
function displayHeadToHeadLeaderboard(leaderboard) {
    const tbody = document.getElementById('h2h-leaderboard-body');
    if (!tbody) return;

    if (!leaderboard || leaderboard.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading">No head-to-head results found</td></tr>';
        return;
    }

    tbody.innerHTML = '';

    const medals = ['🥇', '🥈', '🥉'];

    leaderboard.forEach((agent, index) => {
        const row = document.createElement('tr');
        const rankDisplay = index < 3 ? `${medals[index]} ${index + 1}` : `${index + 1}`;

        row.innerHTML = `
            <td>${rankDisplay}</td>
            <td><strong>${agent.runner || ''}:${agent.model || ''}</strong></td>
            <td>${agent.wins}</td>
            <td>${agent.losses}</td>
            <td>${agent.ties}</td>
            <td>${formatPercentage(agent.win_rate)}</td>
            <td><strong>${agent.elo_rating.toFixed(1)}</strong></td>
        `;

        tbody.appendChild(row);
    });
}

/**
 * Load and display head-to-head PR details
 */
async function loadHeadToHeadPRDetails() {
    try {
        const results = await loadAllHeadToHeadResults();

        if (!results || results.length === 0) {
            const listContainer = document.getElementById('analysis-list');
            if (listContainer) {
                listContainer.innerHTML = '<p class="loading">No head-to-head results found</p>';
            }
            return;
        }

        // Display list of PRs with head-to-head results
        displayHeadToHeadPRList(results);
    } catch (error) {
        console.error('Error loading head-to-head PR details:', error);
        const listContainer = document.getElementById('analysis-list');
        if (listContainer) {
            listContainer.innerHTML = '<p class="loading">Error loading head-to-head results</p>';
        }
    }
}

/**
 * Display list of PRs with head-to-head results
 */
function displayHeadToHeadPRList(results) {
    const listContainer = document.getElementById('analysis-list');
    if (!listContainer) return;

    // Sort by PR number
    const sorted = [...results].sort((a, b) => a.pr_number - b.pr_number);

    // Create table
    const table = document.createElement('table');
    table.style.width = '100%';
    table.innerHTML = `
        <thead>
            <tr>
                <th>PR Number</th>
                <th>Agents</th>
                <th>Pairwise Decisions</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody id="h2h-pr-list-body"></tbody>
    `;

    listContainer.innerHTML = '';
    listContainer.appendChild(table);

    const tbody = document.getElementById('h2h-pr-list-body');

    sorted.forEach(result => {
        const row = document.createElement('tr');
        const agentCount = result.agent_results ? result.agent_results.length : 0;
        const decisionCount = result.pairwise_decisions ? result.pairwise_decisions.length : 0;

        row.innerHTML = `
            <td><strong>${result.pr_number}</strong></td>
            <td>${agentCount} agents</td>
            <td>${decisionCount} decisions</td>
            <td>
                <button class="btn-primary" onclick="showHeadToHeadDetail('${result.head_to_head_run_id}', ${result.pr_number})">
                    View Details
                </button>
            </td>
        `;

        tbody.appendChild(row);
    });
}


/**
 * Show head-to-head detail view for a specific PR
 */
async function showHeadToHeadDetail(runId, prNumber) {
    try {
        // Find the result for this PR
        const results = await loadAllHeadToHeadResults();
        const result = results.find(r => r.pr_number === prNumber);

        if (!result) {
            alert('Head-to-head result not found for PR ' + prNumber);
            return;
        }

        // Hide list, show detail
        document.getElementById('analysis-list').style.display = 'none';
        document.getElementById('analysis-detail').style.display = 'block';

        // Set title
        document.getElementById('detail-title').textContent = `PR ${prNumber} - Head-to-Head Results`;

        // Show task instructions
        document.getElementById('task-instructions').textContent = result.task_instructions || 'N/A';

        // Hide comparative section (not used in head-to-head)
        document.getElementById('comparative-section').style.display = 'none';

        // Display agent results
        displayHeadToHeadAgentResults(result);

        // Display pairwise decisions
        displayPairwiseDecisions(result);

    } catch (error) {
        console.error('Error showing head-to-head detail:', error);
        alert('Error loading head-to-head details');
    }
}

/**
 * Display agent results for head-to-head
 */
function displayHeadToHeadAgentResults(result) {
    const tbody = document.getElementById('agent-results-body');
    if (!tbody) return;

    tbody.innerHTML = '';

    result.agent_results.forEach((agentResult, index) => {
        const agentId = `${agentResult.runner}:${agentResult.model}`;
        const stats = result.agent_stats.find(s => s.agent_id.startsWith(agentId));

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><strong>${agentId}</strong></td>
            <td>${formatStatus(agentResult.status)}</td>
            <td>${stats ? `${stats.wins}W / ${stats.losses}L / ${stats.ties}T` : 'N/A'}</td>
            <td style="font-size: 0.9em;">${agentResult.llm_summary || 'N/A'}</td>
            <td>-</td>
            <td>-</td>
            <td>-</td>
            <td>-</td>
            <td>-</td>
            <td>-</td>
            <td>${(agentResult.elapsed_ms / 1000).toFixed(1)}</td>
        `;

        tbody.appendChild(row);
    });
}

/**
 * Display pairwise decisions
 */
function displayPairwiseDecisions(result) {
    const container = document.getElementById('agent-details-container');
    if (!container) return;

    container.innerHTML = '<div class="card"><h4>Pairwise Decisions</h4><div id="pairwise-decisions-content"></div></div>';
    const content = document.getElementById('pairwise-decisions-content');

    if (!result.pairwise_decisions || result.pairwise_decisions.length === 0) {
        content.innerHTML = '<p>No pairwise decisions found</p>';
        return;
    }

    const table = document.createElement('table');
    table.style.width = '100%';
    table.innerHTML = `
        <thead>
            <tr>
                <th>Submission A</th>
                <th>Submission B</th>
                <th>Judge</th>
                <th>Winner</th>
                <th>Rationale</th>
            </tr>
        </thead>
        <tbody id="pairwise-tbody"></tbody>
    `;

    content.appendChild(table);

    const tbody = document.getElementById('pairwise-tbody');

    result.pairwise_decisions.forEach(decision => {
        const row = document.createElement('tr');

        const winnerDisplay = decision.winner === 'A' ? '🏆 A' : decision.winner === 'B' ? '🏆 B' : '🤝 Tie';
        const judgeDisplay = decision.judge_runner ? `${decision.judge_runner} (${decision.judge_model || 'N/A'})` : decision.judge_model || 'N/A';

        row.innerHTML = `
            <td style="font-size: 0.85em;">${decision.submission_a_id}</td>
            <td style="font-size: 0.85em;">${decision.submission_b_id}</td>
            <td>${judgeDisplay}</td>
            <td><strong>${winnerDisplay}</strong></td>
            <td style="font-size: 0.9em; max-width: 400px;">${decision.rationale || 'N/A'}</td>
        `;

        tbody.appendChild(row);
    });
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

