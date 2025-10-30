/**
 * Main application logic for Long-Context-Bench web app
 */

// Global state
let currentSummaries = [];
let currentSort = { field: 'mean_aggregate', ascending: false };

/**
 * Load and display leaderboard
 */
async function loadLeaderboard() {
    try {
        const index = await loadIndex();
        currentSummaries = await loadAllSummaries();
        
        // Update overview stats
        updateOverviewStats(index, currentSummaries);
        
        // Populate filters
        populateFilters(index);
        
        // Display leaderboard
        displayLeaderboard(currentSummaries);
        
        // Update charts
        if (currentSummaries.length > 0) {
            createScoreDistributionChart('score-distribution-chart', currentSummaries);
            createSuccessRateChart('success-rate-chart', currentSummaries);
        }
        
        // Update timestamp
        document.getElementById('last-updated').textContent = formatTimestamp(index.last_updated);
    } catch (error) {
        console.error('Error loading leaderboard:', error);
        document.getElementById('leaderboard-body').innerHTML = 
            '<tr><td colspan="12" class="loading">Error loading data. Make sure the benchmark has been run.</td></tr>';
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
 * Display leaderboard table
 */
function displayLeaderboard(summaries) {
    const tbody = document.getElementById('leaderboard-body');
    if (!tbody) return;
    
    if (summaries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" class="loading">No runs found</td></tr>';
        return;
    }
    
    // Sort summaries
    const sorted = [...summaries].sort((a, b) => {
        const aVal = a[currentSort.field] || 0;
        const bVal = b[currentSort.field] || 0;
        return currentSort.ascending ? aVal - bVal : bVal - aVal;
    });
    
    tbody.innerHTML = '';
    sorted.forEach((summary, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${summary.runner || '-'}</td>
            <td>${summary.model || '-'}</td>
            <td>${summary.test_label || '-'}</td>
            <td>${formatScore(summary.mean_aggregate)}</td>
            <td>${formatPercentage(summary.success_rate)}</td>
            <td>${formatScore(summary.mean_correctness)}</td>
            <td>${formatScore(summary.mean_completeness)}</td>
            <td>${formatScore(summary.mean_code_reuse)}</td>
            <td>${formatScore(summary.mean_best_practices)}</td>
            <td>${summary.tasks_per_hour ? summary.tasks_per_hour.toFixed(2) : '-'}</td>
            <td><a href="summary.html?run_id=${summary.run_id}">View</a></td>
        `;
        tbody.appendChild(row);
    });
    
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
            displayLeaderboard(currentSummaries);
        };
    });
}

/**
 * Filter leaderboard
 */
function filterLeaderboard() {
    const runner = document.getElementById('filter-runner').value;
    const model = document.getElementById('filter-model').value;
    const label = document.getElementById('filter-label').value;
    
    const filtered = currentSummaries.filter(s => {
        if (runner && s.runner !== runner) return false;
        if (model && s.model !== model) return false;
        if (label && s.test_label !== label) return false;
        return true;
    });
    
    displayLeaderboard(filtered);
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
            option.value = run.run_id;
            option.textContent = `${run.runner || 'Unknown'} / ${run.model || 'Unknown'} - ${run.test_label || run.run_id}`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading run selector:', error);
    }
}

/**
 * Load and display run summary
 */
async function loadRunSummary(runId) {
    try {
        const data = await loadRunDetails(runId);
        
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
            index.runs.forEach(run => {
                const label = document.createElement('label');
                label.style.display = 'block';
                label.style.marginBottom = '8px';

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.value = run.run_id;
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
            const runIds = Array.from(checkboxes).map(cb => cb.value);

            if (runIds.length < 2) {
                alert('Please select at least 2 runs to compare');
                return;
            }

            for (const runId of runIds) {
                const summary = await loadSummary(runId);
                if (summary) summaries.push(summary);
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

