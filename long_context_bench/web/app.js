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
let currentHeadToHeadComparison = null;

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
 * Falls back to LLM judge results if no head-to-head results are available.
 */
async function loadHeadToHeadLeaderboard() {
    const tbody = document.getElementById('h2h-leaderboard-body');

    try {
        // Load lightweight metadata instead of all results
        const metadata = await loadHeadToHeadMetadata();

        if (!metadata || metadata.length === 0) {
            // Fall back to LLM judge results
            console.log('No head-to-head results found, falling back to LLM judge results');
            await loadLLMJudgeLeaderboard();
            return;
        }

        // Aggregate stats from metadata (which includes agent_stats)
        headToHeadLeaderboard = aggregateHeadToHeadDataFromMetadata(metadata);
        displayHeadToHeadLeaderboard(headToHeadLeaderboard);
    } catch (error) {
        console.error('Error loading head-to-head leaderboard:', error);
        // Try LLM judge fallback
        try {
            await loadLLMJudgeLeaderboard();
        } catch (fallbackError) {
            console.error('Error loading LLM judge fallback:', fallbackError);
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="7" class="loading">Error loading results</td></tr>';
            }
        }
    }
}

/**
 * Normalize agent ID by removing the hash suffix.
 * Converts "runner:model:hash" to "runner:model"
 */
function normalizeAgentId(agentId) {
    const parts = agentId.split(':');
    // If there are 3+ parts, the last one is likely a hash
    if (parts.length >= 3) {
        // Remove the last part (hash)
        return parts.slice(0, -1).join(':');
    }
    return agentId;
}

/**
 * Aggregate head-to-head data from metadata (lightweight version).
 * This only uses agent_stats from metadata, not full pairwise decisions.
 */
function aggregateHeadToHeadDataFromMetadata(metadata) {
    const agentStats = {};

    // Aggregate stats from metadata
    for (const prMeta of metadata) {
        if (!prMeta.agent_stats) continue;

        for (const stat of prMeta.agent_stats) {
            const fullAgentId = stat.agent_id;
            const normalizedId = normalizeAgentId(fullAgentId);

            if (!agentStats[normalizedId]) {
                agentStats[normalizedId] = {
                    agent_id: normalizedId,
                    wins: 0,
                    losses: 0,
                    ties: 0
                };
            }

            agentStats[normalizedId].wins += stat.wins || 0;
            agentStats[normalizedId].losses += stat.losses || 0;
            agentStats[normalizedId].ties += stat.ties || 0;
        }
    }

    // Convert to leaderboard format
    const leaderboard = Object.values(agentStats).map(stats => {
        const matches = stats.wins + stats.losses + stats.ties;
        const winRate = matches > 0 ? (stats.wins + 0.5 * stats.ties) / matches : 0;

        const parts = stats.agent_id.split(':');
        const runner = parts[0] || '';
        const model = parts[1] || '';

        return {
            agent_id: stats.agent_id,
            runner,
            model,
            wins: stats.wins,
            losses: stats.losses,
            ties: stats.ties,
            matches,
            win_rate: winRate
        };
    });

    // Sort by win rate descending
    leaderboard.sort((a, b) => b.win_rate - a.win_rate);

    return leaderboard;
}

/**
 * Aggregate head-to-head data from all PR results to compute ELO ratings and stats.
 */
function aggregateHeadToHeadData(results) {
    // Collect all pairwise decisions across all PRs
    const allDecisions = [];
    const agentStats = {};

    // Map from full agent_id (with hash) to normalized agent_id (without hash)
    const agentIdMap = {};

    for (const result of results) {
        if (!result.pairwise_decisions) continue;

        // Normalize decisions by mapping agent IDs
        const normalizedDecisions = result.pairwise_decisions.map(decision => ({
            ...decision,
            submission_a_id: normalizeAgentId(decision.submission_a_id),
            submission_b_id: normalizeAgentId(decision.submission_b_id)
        }));

        allDecisions.push(...normalizedDecisions);

        // Aggregate stats from each PR
        if (result.agent_stats) {
            for (const stat of result.agent_stats) {
                const fullAgentId = stat.agent_id;
                const normalizedId = normalizeAgentId(fullAgentId);

                // Track the mapping
                agentIdMap[fullAgentId] = normalizedId;

                if (!agentStats[normalizedId]) {
                    agentStats[normalizedId] = {
                        agent_id: normalizedId,
                        wins: 0,
                        losses: 0,
                        ties: 0
                    };
                }
                agentStats[normalizedId].wins += stat.wins || 0;
                agentStats[normalizedId].losses += stat.losses || 0;
                agentStats[normalizedId].ties += stat.ties || 0;
            }
        }
    }

    // Compute ELO ratings with normalized IDs
    const eloRatings = computeEloRatings(allDecisions);

    // Build leaderboard entries
    const leaderboard = [];
    for (const [agentId, stats] of Object.entries(agentStats)) {
        // Parse agent_id (format: "runner:model")
        const parts = agentId.split(':');
        const runner = parts[0] || agentId;
        const model = parts.slice(1).join(':') || '';

        const totalGames = stats.wins + stats.losses + stats.ties;
        const winRate = totalGames > 0 ? stats.wins / totalGames : 0;

        leaderboard.push({
            agent_id: agentId,
            runner: runner,
            model: model,
            wins: stats.wins,
            losses: stats.losses,
            ties: stats.ties,
            win_rate: winRate,
            elo_rating: eloRatings[agentId] || 1500
        });
    }

    // Sort by win rate (descending), then by total wins as tiebreaker
    leaderboard.sort((a, b) => {
        if (b.win_rate !== a.win_rate) {
            return b.win_rate - a.win_rate;
        }
        return b.wins - a.wins;
    });

    return leaderboard;
}

/**
 * Compute ELO ratings from pairwise decisions.
 */
function computeEloRatings(decisions, initialRating = 1500, kFactor = 32) {
    const ratings = {};

    function getRating(agentId) {
        if (!(agentId in ratings)) {
            ratings[agentId] = initialRating;
        }
        return ratings[agentId];
    }

    for (const decision of decisions) {
        const a = decision.submission_a_id;
        const b = decision.submission_b_id;

        const ra = getRating(a);
        const rb = getRating(b);

        // Expected scores
        const ea = 1 / (1 + Math.pow(10, (rb - ra) / 400));
        const eb = 1 / (1 + Math.pow(10, (ra - rb) / 400));

        // Actual scores
        let sa, sb;
        const winner = (decision.winner || '').toLowerCase();
        if (winner === 'a') {
            sa = 1.0;
            sb = 0.0;
        } else if (winner === 'b') {
            sa = 0.0;
            sb = 1.0;
        } else {
            // Tie
            sa = 0.5;
            sb = 0.5;
        }

        // Update ratings
        ratings[a] = ra + kFactor * (sa - ea);
        ratings[b] = rb + kFactor * (sb - eb);
    }

    return ratings;
}

/**
 * Display head-to-head leaderboard table.
 */
function displayHeadToHeadLeaderboard(leaderboard) {
    const tbody = document.getElementById('h2h-leaderboard-body');
    if (!tbody) return;

    if (!leaderboard || leaderboard.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="loading">No head-to-head results found</td></tr>';
        return;
    }

    tbody.innerHTML = '';

    const medals = ['🥇', '🥈', '🥉'];

    // Helper to format and color-code scores
    const formatScore = (score) => {
        if (score === null || score === undefined) return '<span style="color: #9ca3af;">—</span>';
        const color = score >= 0.5 ? '#10b981' : score >= 0 ? '#f59e0b' : '#ef4444';
        return `<span style="color: ${color}; font-weight: 600;">${score.toFixed(2)}</span>`;
    };

    leaderboard.forEach((agent, index) => {
        const row = document.createElement('tr');
        const rankDisplay = index < 3 ? `${medals[index]} ${index + 1}` : `${index + 1}`;

        row.innerHTML = `
            <td>${rankDisplay}</td>
            <td><strong>${agent.runner || ''}:${agent.model || ''}</strong></td>
            <td>${formatScore(agent.mean_aggregate)}</td>
            <td>${formatScore(agent.mean_correctness)}</td>
            <td>${formatScore(agent.mean_completeness)}</td>
            <td>${formatScore(agent.mean_code_reuse)}</td>
            <td>${formatScore(agent.mean_best_practices)}</td>
            <td>${formatScore(agent.mean_unsolicited_docs)}</td>
            <td>${formatPercentage(agent.success_rate)}</td>
        `;

        tbody.appendChild(row);
    });

    // Create metrics comparison chart
    createMetricsComparisonChart(leaderboard);
}

/**
 * Create horizontal bar chart showing all metrics for all agents
 */
function createMetricsComparisonChart(leaderboard) {
    const canvas = document.getElementById('metrics-bar-chart');
    if (!canvas) return;

    // Destroy existing chart if it exists
    if (window.metricsChart) {
        window.metricsChart.destroy();
    }

    const ctx = canvas.getContext('2d');

    // Take top 5 agents for clarity
    const topAgents = leaderboard.slice(0, Math.min(5, leaderboard.length));

    // Prepare data for each metric
    const metricLabels = ['Correctness', 'Completeness', 'Code Reuse', 'Best Practices', 'Unsol. Docs'];
    const metricKeys = ['mean_correctness', 'mean_completeness', 'mean_code_reuse', 'mean_best_practices', 'mean_unsolicited_docs'];

    const colors = [
        'rgba(79, 70, 229, 0.8)',   // Indigo
        'rgba(16, 185, 129, 0.8)',  // Green
        'rgba(245, 158, 11, 0.8)',  // Amber
        'rgba(239, 68, 68, 0.8)',   // Red
        'rgba(139, 92, 246, 0.8)'   // Purple
    ];

    const datasets = topAgents.map((agent, idx) => {
        return {
            label: `${agent.runner}:${agent.model}`,
            data: metricKeys.map(key => agent[key] || 0),
            backgroundColor: colors[idx],
            borderColor: colors[idx].replace('0.8', '1'),
            borderWidth: 1
        };
    });

    window.metricsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: metricLabels,
            datasets: datasets
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                title: {
                    display: true,
                    text: 'Performance Across All Metrics (Top 5 Agents)',
                    font: {
                        size: 16
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.parsed.x.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    min: -1,
                    max: 1,
                    title: {
                        display: true,
                        text: 'Score (-1 to 1)'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

/**
 * Load and display LLM judge leaderboard (fallback when no head-to-head results).
 */
async function loadLLMJudgeLeaderboard() {
    const tbody = document.getElementById('h2h-leaderboard-body');
    if (!tbody) return;

    try {
        const index = await loadIndex();

        if (!index.runs || index.runs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="loading">No results found</td></tr>';
            return;
        }

        // Load summaries to get detailed metrics
        const llmRuns = [];
        for (const run of index.runs) {
            if (!run.mean_aggregate || run.total_samples < 40) continue;

            try {
                const summary = await loadSummary(run.run_id);
                if (summary) {
                    llmRuns.push({
                        runner: run.runner,
                        model: run.model,
                        mean_aggregate: summary.mean_aggregate || 0,
                        mean_correctness: summary.mean_correctness || 0,
                        mean_completeness: summary.mean_completeness || 0,
                        mean_code_reuse: summary.mean_code_reuse || 0,
                        mean_best_practices: summary.mean_best_practices || 0,
                        mean_unsolicited_docs: summary.mean_unsolicited_docs || 0,
                        success_rate: summary.success_rate || 0,
                        total_samples: run.total_samples
                    });
                }
            } catch (e) {
                console.warn(`Failed to load summary for run ${run.run_id}:`, e);
            }
        }

        llmRuns.sort((a, b) => b.mean_aggregate - a.mean_aggregate);

        if (llmRuns.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="loading">No LLM judge results found</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        const medals = ['🥇', '🥈', '🥉'];

        // Helper to format and color-code scores
        const formatScore = (score) => {
            if (score === null || score === undefined) return '<span style="color: #9ca3af;">—</span>';
            const color = score >= 0.5 ? '#10b981' : score >= 0 ? '#f59e0b' : '#ef4444';
            return `<span style="color: ${color}; font-weight: 600;">${score.toFixed(2)}</span>`;
        };

        llmRuns.forEach((agent, index) => {
            const row = document.createElement('tr');
            const rankDisplay = index < 3 ? `${medals[index]} ${index + 1}` : `${index + 1}`;

            row.innerHTML = `
                <td>${rankDisplay}</td>
                <td><strong>${agent.runner || ''}:${agent.model || ''}</strong></td>
                <td>${formatScore(agent.mean_aggregate)}</td>
                <td>${formatScore(agent.mean_correctness)}</td>
                <td>${formatScore(agent.mean_completeness)}</td>
                <td>${formatScore(agent.mean_code_reuse)}</td>
                <td>${formatScore(agent.mean_best_practices)}</td>
                <td>${formatScore(agent.mean_unsolicited_docs)}</td>
                <td>${formatPercentage(agent.success_rate)}</td>
            `;

            tbody.appendChild(row);
        });

        // Create metrics comparison chart
        createMetricsComparisonChart(llmRuns);
    } catch (error) {
        console.error('Error loading LLM judge leaderboard:', error);
        tbody.innerHTML = '<tr><td colspan="9" class="loading">Error loading LLM judge results</td></tr>';
    }
}

/**
 * Load and display head-to-head PR details
 * Falls back to LLM judge PR details if no head-to-head results are available.
 */
async function loadHeadToHeadPRDetails() {
    try {
        // Load lightweight metadata instead of all results
        const metadata = await loadHeadToHeadMetadata();

        if (!metadata || metadata.length === 0) {
            // Fall back to LLM judge PR details
            console.log('No head-to-head PR details found, falling back to LLM judge PR details');
            await loadLLMJudgePRDetails();
            return;
        }

        // Display list of PRs with head-to-head results
        displayHeadToHeadPRList(metadata);
    } catch (error) {
        console.error('Error loading head-to-head PR details:', error);
        try {
            await loadLLMJudgePRDetails();
        } catch (fallbackError) {
            console.error('Error loading LLM judge PR details fallback:', fallbackError);
            const listContainer = document.getElementById('analysis-list');
            if (listContainer) {
                listContainer.innerHTML = '<p class="loading">Error loading results</p>';
            }
        }
    }
}

/**
 * Load and display LLM judge PR details (fallback when no head-to-head results).
 */
async function loadLLMJudgePRDetails() {
    const listContainer = document.getElementById('analysis-list');
    if (!listContainer) return;

    try {
        const index = await loadIndex();

        if (!index.runs || index.runs.length === 0) {
            listContainer.innerHTML = '<p class="loading">No results found</p>';
            return;
        }

        // Get all PRs from runs with mean_aggregate scores
        const prMap = new Map(); // pr_id -> { pr_id, agents: [{runner, model, run_id, judge_run_id}] }

        for (const run of index.runs) {
            if (!run.mean_aggregate || !run.pr_ids || run.total_samples < 40) continue;

            const agentKey = `${run.runner}:${run.model}`;

            for (const prId of run.pr_ids) {
                if (!prMap.has(prId)) {
                    prMap.set(prId, {
                        pr_id: prId,
                        agents: [],
                        pr_number: extractPRNumber(prId)
                    });
                }

                prMap.get(prId).agents.push({
                    runner: run.runner,
                    model: run.model,
                    agentKey: agentKey,
                    edit_run_id: run.edit_run_id,
                    judge_run_id: run.judge_run_id || run.run_id
                });
            }
        }

        if (prMap.size === 0) {
            listContainer.innerHTML = '<p class="loading">No PR results found</p>';
            return;
        }

        // Get the total number of agents in the benchmark
        const allAgents = new Set();
        for (const run of index.runs) {
            if (run.mean_aggregate && run.pr_ids && run.total_samples >= 40) {
                allAgents.add(`${run.runner}:${run.model}`);
            }
        }
        const expectedAgentCount = allAgents.size;

        // Filter to only PRs where all agents have results
        const filteredPRs = Array.from(prMap.values()).filter(pr => pr.agents.length === expectedAgentCount);

        console.log(`Total PRs: ${prMap.size}, PRs with all ${expectedAgentCount} agents: ${filteredPRs.length}`);

        if (filteredPRs.length === 0) {
            listContainer.innerHTML = '<p class="loading">No PRs found where all agents competed</p>';
            return;
        }

        // Sort PRs by number
        const prList = filteredPRs.sort((a, b) => a.pr_number - b.pr_number);

        // Create table
        const table = document.createElement('table');
        table.style.width = '100%';
        table.innerHTML = `
            <thead>
                <tr>
                    <th>PR Number</th>
                    <th>Agents</th>
                    <th>Winner</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="llm-pr-list-body"></tbody>
        `;

        listContainer.innerHTML = '';
        listContainer.appendChild(table);

        const tbody = document.getElementById('llm-pr-list-body');

        for (const pr of prList) {
            const row = document.createElement('tr');
            const agentCount = pr.agents.length;
            const agentList = pr.agents.map(a => a.agentKey).join(', ');

            // Load judge results to determine winner
            let winnerLabel = '⏳ Loading...';

            // Load winner asynchronously
            (async () => {
                try {
                    const agentScores = [];
                    for (const agent of pr.agents) {
                        try {
                            // Use the correct path structure: judges/llm/claude-sonnet-4-5/{judge_run_id}/{pr_id}/judge.json
                            const judgePath = `judges/llm/claude-sonnet-4-5/${agent.judge_run_id}/${pr.pr_id}/judge.json`;
                            const judgeData = await fetch(`${API_BASE}/${judgePath}`).then(r => r.json());
                            if (judgeData && judgeData.aggregate !== undefined) {
                                agentScores.push({
                                    agent: `${agent.runner}:${agent.model}`,
                                    score: judgeData.aggregate
                                });
                            }
                        } catch (e) {
                            // Skip if judge data not found
                        }
                    }

                    if (agentScores.length > 0) {
                        agentScores.sort((a, b) => b.score - a.score);
                        const best = agentScores[0];
                        const secondBest = agentScores[1];

                        if (secondBest && Math.abs(best.score - secondBest.score) < 0.05) {
                            winnerLabel = '🤝 Tie';
                        } else {
                            winnerLabel = `🏆 ${best.agent}`;
                        }
                    } else {
                        winnerLabel = '—';
                    }

                    // Update the cell
                    const winnerCell = row.querySelector('.winner-cell');
                    if (winnerCell) {
                        winnerCell.textContent = winnerLabel;
                    }
                } catch (e) {
                    const winnerCell = row.querySelector('.winner-cell');
                    if (winnerCell) {
                        winnerCell.textContent = '—';
                    }
                }
            })();

            row.innerHTML = `
                <td><strong>${pr.pr_number}</strong></td>
                <td>${agentCount} agent${agentCount !== 1 ? 's' : ''}</td>
                <td class="winner-cell">${winnerLabel}</td>
                <td>
                    <button class="btn-primary" onclick="showLLMJudgeDetail('${pr.pr_id}')">
                        View Details
                    </button>
                </td>
            `;

            tbody.appendChild(row);
        }

    } catch (error) {
        console.error('Error loading LLM judge PR details:', error);
        listContainer.innerHTML = '<p class="loading">Error loading LLM judge PR details</p>';
    }
}

/**
 * Extract PR number from PR ID (e.g., "elastic_elasticsearch_pr134296" -> 134296)
 */
function extractPRNumber(prId) {
    const match = prId.match(/pr(\d+)$/);
    return match ? parseInt(match[1]) : 0;
}

/**
 * Compute the per-PR winner from lightweight head-to-head metadata.
 *
 * Uses per-agent win/loss/tie stats for that PR. Returns a short label for
 * display in the PR list along with a human-readable tooltip.
 */
function getHeadToHeadPRWinner(prMeta) {
	    const statsList = Array.isArray(prMeta.agent_stats) ? prMeta.agent_stats : [];
	    if (!statsList.length) {
	        return { label: '\u2014', title: 'No agent stats available for this PR' };
	    }

	    let bestEntries = [];
	    let bestWinRate = -1;
	    const EPS = 1e-6;

	    for (const stat of statsList) {
	        const wins = stat.wins || 0;
	        const losses = stat.losses || 0;
	        const ties = stat.ties || 0;
	        const matches = wins + losses + ties;
	        if (matches === 0) continue;

	        const winRate = (wins + 0.5 * ties) / matches;
	        if (winRate > bestWinRate + EPS) {
	            bestWinRate = winRate;
	            bestEntries = [{ stat, matches, winRate }];
	        } else if (Math.abs(winRate - bestWinRate) <= EPS) {
	            bestEntries.push({ stat, matches, winRate });
	        }
	    }

	    if (!bestEntries.length || bestWinRate < 0) {
	        return { label: '\u2014', title: 'No head-to-head matches were played for this PR' };
	    }

	    // If multiple agents share the top win rate, treat as a tie.
	    if (bestEntries.length > 1) {
	        const agentNames = bestEntries.map(({ stat }) => {
	            const rawId = stat.agent_id || '';
	            const normalized = typeof normalizeAgentId === 'function'
	                ? normalizeAgentId(rawId)
	                : rawId;
	            return normalized;
	        });
	        return {
	            label: 'Tie',
	            title: `Top agents are tied on this PR: ${agentNames.join(', ')}`,
	        };
	    }

	    const { stat, matches, winRate } = bestEntries[0];
	    const wins = stat.wins || 0;
	    const losses = stat.losses || 0;
	    const ties = stat.ties || 0;
	    const rawId = stat.agent_id || '';
	    const normalized = typeof normalizeAgentId === 'function'
	        ? normalizeAgentId(rawId)
	        : rawId;

	    const pct = (winRate * 100).toFixed(1);
	    const title = `${normalized}: ${wins}W / ${losses}L / ${ties}T over ${matches} matches (win rate ${pct}%)`;
	    return { label: normalized || '\u2014', title };
}

/**
 * Display list of PRs with head-to-head results (using metadata)
 */
function displayHeadToHeadPRList(metadata) {
	    const listContainer = document.getElementById('analysis-list');
	    if (!listContainer) return;

	    // Sort by PR number
	    const sorted = [...metadata].sort((a, b) => a.pr_number - b.pr_number);

	    // Create table
	    const table = document.createElement('table');
	    table.style.width = '100%';
	    table.innerHTML = `
	        <thead>
	            <tr>
	                <th>PR Number</th>
	                <th>Agents</th>
	                <th>Pairwise Decisions</th>
	                <th>Winner</th>
	                <th>Actions</th>
	            </tr>
	        </thead>
	        <tbody id="h2h-pr-list-body"></tbody>
	    `;

	    listContainer.innerHTML = '';
	    listContainer.appendChild(table);

	    const tbody = document.getElementById('h2h-pr-list-body');

	    sorted.forEach(prMeta => {
	        const row = document.createElement('tr');
		        const agentCount =
		            prMeta.num_agents != null
		                ? prMeta.num_agents
		                : (Array.isArray(prMeta.agent_results) ? prMeta.agent_results.length : 0);
		        const decisionCount =
		            prMeta.num_decisions != null
		                ? prMeta.num_decisions
		                : (Array.isArray(prMeta.pairwise_decisions) ? prMeta.pairwise_decisions.length : 0);

	        const winner = getHeadToHeadPRWinner(prMeta);
	        const winnerLabel = winner.label || '\u2014';
	        const winnerTitle = winner.title || '';

	        row.innerHTML = `
	            <td><strong>${prMeta.pr_number}</strong></td>
	            <td>${agentCount} agents</td>
	            <td>${decisionCount} decisions</td>
	            <td title="${winnerTitle}">${winnerLabel}</td>
	            <td>
	                <button class="btn-primary" onclick="showHeadToHeadDetail('${prMeta.head_to_head_run_id}', ${prMeta.pr_number})">
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
        // Load the specific PR result on demand
        const result = await loadHeadToHeadResult(prNumber);

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

	        // Initialize side-by-side agent/human inspector
	        if (typeof initAgentComparison === 'function') {
	            initAgentComparison(result);
	        }
	    	
	        // Display pairwise decisions
	        displayPairwiseDecisions(result);

    } catch (error) {
        console.error('Error showing head-to-head detail:', error);
        alert('Error loading head-to-head details');
    }
}

/**
 * Show LLM judge detail view for a specific PR
 */
async function showLLMJudgeDetail(prId) {
    try {
        const index = await loadIndex();

        // Find all runs that have this PR
        const runsWithPR = index.runs.filter(run =>
            run.pr_ids && run.pr_ids.includes(prId) && run.total_samples >= 40
        );

        if (runsWithPR.length === 0) {
            alert('No results found for PR ' + prId);
            return;
        }

        // Load judge results for each agent
        const agentResults = [];
        const prNumber = extractPRNumber(prId);

        // Try to load sample.json for task instructions
        let taskInstructions = 'N/A';
        let humanDiff = '';
        try {
            const samplePath = `/api/samples/v1/${prId}/sample.json`;
            const sampleResponse = await fetch(samplePath);
            if (sampleResponse.ok) {
                const sampleData = await sampleResponse.json();
                taskInstructions = sampleData.task_instructions ||
                                  sampleData.synthesized_task_instructions ||
                                  'N/A';
            }
        } catch (err) {
            console.warn(`Could not load sample.json for ${prId}:`, err);
        }

        for (const run of runsWithPR) {
            const agentKey = `${run.runner}:${run.model}`;
            const judgeRunId = run.judge_run_id || run.run_id;
            const editRunId = run.edit_run_id;

            // Load judge result - use /api/ prefix for server endpoint
            const judgePath = `/api/judges/llm/claude-sonnet-4-5/${judgeRunId}/${prId}/judge.json`;
            const editPath = `/api/edits/${run.runner}/${run.model}/${editRunId}/${prId}/edit.json`;

            try {
                const [judgeResponse, editResponse] = await Promise.all([
                    fetch(judgePath),
                    fetch(editPath)
                ]);

                if (judgeResponse.ok && editResponse.ok) {
                    const judgeData = await judgeResponse.json();
                    const editData = await editResponse.json();

                    // Get human diff from judge data if available
                    if (judgeData.ground_truth_patch && !humanDiff) {
                        humanDiff = judgeData.ground_truth_patch;
                    }

                    agentResults.push({
                        runner: run.runner,
                        model: run.model,
                        agentKey: agentKey,
                        judge: judgeData,
                        edit: editData,
                        edit_run_id: editRunId
                    });
                }
            } catch (err) {
                console.error(`Error loading data for ${agentKey}:`, err);
            }
        }

        if (agentResults.length === 0) {
            alert('Could not load judge results for PR ' + prId);
            return;
        }

        // Hide list, show detail
        document.getElementById('analysis-list').style.display = 'none';
        document.getElementById('analysis-detail').style.display = 'block';

        // Set title
        document.getElementById('detail-title').textContent = `PR ${prNumber} - LLM Judge Results`;

        // Show task instructions
        document.getElementById('task-instructions').textContent = taskInstructions;

        // Hide pairwise decisions section (not used in LLM judge)
        const pairwiseSection = document.getElementById('pairwise-decisions-section');
        if (pairwiseSection) {
            pairwiseSection.style.display = 'none';
        }

        // Display agent results with LLM judge scores
        displayLLMJudgeAgentResults(agentResults);

        // Initialize side-by-side comparison
        if (typeof initAgentComparison === 'function') {
            // Adapt the data structure for the comparison viewer
            const adaptedResult = {
                pr_number: prNumber,
                pr_id: prId,
                task_instructions: taskInstructions,
                agent_results: agentResults.map(ar => ({
                    runner: ar.runner,
                    model: ar.model,
                    edit_run_id: ar.edit_run_id,
                    patch_unified: ar.edit.patch_unified || ar.edit.diff || '',
                    elapsed_ms: ar.edit.elapsed_ms || 0,
                    logs_path: ar.edit.logs_path || '',
                    llm_summary: ar.judge.rationale || 'No judge rationale available',
                    judge_scores: ar.judge.scores || {}
                })),
                human_diff: humanDiff,
                repo_url: agentResults[0].judge.repo_url || '',
                base_commit: agentResults[0].judge.base_commit || '',
                head_commit: agentResults[0].judge.head_commit || ''
            };
            initAgentComparison(adaptedResult);
        }

    } catch (error) {
        console.error('Error showing LLM judge detail:', error);
        alert('Error loading LLM judge details');
    }
}

/**
 * Display agent results for LLM judge
 */
function displayLLMJudgeAgentResults(agentResults) {
    const tbody = document.getElementById('agent-results-body');
    if (!tbody) return;

    tbody.innerHTML = '';

    // Sort by aggregate score (descending)
    const sorted = [...agentResults].sort((a, b) => {
        const scoreA = a.judge.aggregate || 0;
        const scoreB = b.judge.aggregate || 0;
        return scoreB - scoreA;
    });

    sorted.forEach((agentResult, index) => {
        const agentId = agentResult.agentKey;
        const judge = agentResult.judge;

        const aggregateScore = judge.aggregate?.toFixed(3) || 'N/A';
        const correctness = judge.scores?.correctness?.toFixed(3) || 'N/A';
        const completeness = judge.scores?.completeness?.toFixed(3) || 'N/A';
        const codeQuality = judge.scores?.best_practices?.toFixed(3) || 'N/A';
        const elapsedSec = (agentResult.edit.elapsed_ms / 1000).toFixed(1);

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${index + 1}</td>
            <td><strong>${agentId}</strong></td>
            <td>${aggregateScore}</td>
            <td title="Correctness: ${correctness}, Completeness: ${completeness}, Quality: ${codeQuality}">
                ${correctness} / ${completeness} / ${codeQuality}
            </td>
            <td>${elapsedSec}s</td>
        `;

        tbody.appendChild(row);
    });

    // Update table header for LLM judge mode
    const thead = tbody.closest('table')?.querySelector('thead tr');
    if (thead) {
        thead.innerHTML = `
            <th>Rank</th>
            <th>Agent</th>
            <th>Aggregate</th>
            <th>Scores (C/C/Q)</th>
            <th>Time</th>
        `;
    }

    // Create scores chart
    createAgentScoresChart(sorted);
}

/**
 * Create grouped bar chart showing all metrics for all agents (PR detail view)
 * Matches the style of the landing page metrics chart
 */
function createAgentScoresChart(agentResults) {
    const chartContainer = document.getElementById('agent-scores-charts-container');

    if (!chartContainer) return;

    // Show the chart container
    chartContainer.style.display = 'block';

    // Destroy existing chart if any
    if (window.agentScoresChartInstance) {
        window.agentScoresChartInstance.destroy();
    }

    const canvas = document.getElementById('agent-scores-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    // Prepare data
    const metricLabels = ['Correctness', 'Completeness', 'Code Reuse', 'Best Practices', 'Unsol. Docs'];
    const metricKeys = ['correctness', 'completeness', 'code_reuse', 'best_practices', 'unsolicited_docs'];

    // Agent colors (matching landing page style)
    const colors = [
        'rgba(79, 70, 229, 0.8)',   // Indigo
        'rgba(16, 185, 129, 0.8)',  // Green
        'rgba(245, 158, 11, 0.8)',  // Amber
        'rgba(239, 68, 68, 0.8)',   // Red
        'rgba(139, 92, 246, 0.8)'   // Purple
    ];

    // Create datasets - one per agent
    const datasets = agentResults.map((agentResult, idx) => {
        return {
            label: agentResult.agentKey,
            data: metricKeys.map(key => agentResult.judge.scores?.[key] || 0),
            backgroundColor: colors[idx % colors.length],
            borderColor: colors[idx % colors.length].replace('0.8', '1'),
            borderWidth: 1
        };
    });

    window.agentScoresChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: metricLabels,
            datasets: datasets
        },
        options: {
            indexAxis: 'y', // Horizontal bars
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                title: {
                    display: true,
                    text: 'Agent Performance Across All Metrics',
                    font: {
                        size: 16,
                        weight: 'bold'
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.parsed.x.toFixed(3)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    min: -1,
                    max: 1,
                    title: {
                        display: true,
                        text: 'Score (-1 to 1)'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
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

	        const wins = stats?.wins ?? 0;
	        const losses = stats?.losses ?? 0;
	        const ties = stats?.ties ?? 0;
	        const matches = wins + losses + ties;
	        const winRate = matches > 0 ? (wins + 0.5 * ties) / matches : 0;

	        const row = document.createElement('tr');
	        row.innerHTML = `
	            <td>${index + 1}</td>
	            <td><strong>${agentId}</strong></td>
	            <td>${wins}W / ${losses}L / ${ties}T</td>
	            <td>${matches}</td>
	            <td>${formatPercentage(winRate)}</td>
	            <td>${(agentResult.elapsed_ms / 1000).toFixed(1)}</td>
	        `;

        tbody.appendChild(row);
    });
}

/**
 * Display diff and logs sections for each agent
 */
function displayAgentDiffsAndLogs(agentResults) {
    const container = document.getElementById('agent-details-sections');
    if (!container) return;

    container.innerHTML = agentResults.map(agentResult => {
        const agentId = `${agentResult.runner}:${agentResult.model}`;
        const agentIdSafe = agentId.replace(/[^a-zA-Z0-9]/g, '_');

        return `
            <div class="card" style="margin-top: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h5 style="margin: 0;">${agentId}</h5>
                    <div>
                        <button class="btn-action" onclick="showAgentView('${agentIdSafe}', 'summary')">
                            <span class="btn-icon">📝</span> Summary
                        </button>
                        <button class="btn-action" onclick="showAgentView('${agentIdSafe}', 'diff')">
                            <span class="btn-icon">📄</span> Diff
                        </button>
                        ${agentResult.logs_path ? `
                            <button class="btn-action" onclick="showAgentView('${agentIdSafe}', 'logs', '${agentResult.logs_path}')">
                                <span class="btn-icon">📋</span> Logs
                            </button>
                        ` : ''}
                    </div>
                </div>
                <div id="summary-${agentIdSafe}" class="agent-view-section">
                    <p style="padding: 10px; background: var(--bg-secondary); border-radius: 4px; line-height: 1.6; margin: 0;">
                        ${agentResult.llm_summary || 'No summary available'}
                    </p>
                </div>
                <div id="diff-${agentIdSafe}" class="agent-view-section" style="display: none;">
                    <pre class="code-block">${colorizeDiff(agentResult.patch_unified || 'No diff available')}</pre>
                </div>
                ${agentResult.logs_path ? `
                    <div id="logs-${agentIdSafe}" class="agent-view-section logs-container" style="display: none;">
                        <div style="text-align: center; padding: 20px; color: #666;">
                            <em>Click "Logs" button to load...</em>
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

	/**
	 * Initialize the side-by-side agent/human inspector for a head-to-head PR.
	 */
	function initAgentComparison(result) {
	    const card = document.getElementById('agent-comparison-card');
	    const leftColumn = document.getElementById('agent-comparison-left');
	    const rightColumn = document.getElementById('agent-comparison-right');
	    if (!card || !leftColumn || !rightColumn) return;

	    const agentOptions = (result.agent_results || []).map(agentResult => {
	        const label = `${agentResult.runner}:${agentResult.model}`;
	        const value = `agent:${agentResult.runner}:${agentResult.model}:${agentResult.edit_run_id}`;
	        return {
	            type: 'agent',
	            label,
	            value,
	            agentResult,
	        };
	    });

	    if (agentOptions.length === 0) {
	        card.style.display = 'none';
	        currentHeadToHeadComparison = null;
	        return;
	    }

	    const optionsByValue = {};
	    // Human option
	    optionsByValue['human'] = {
	        type: 'human',
	        label: 'Human (ground truth)',
	        value: 'human',
	    };
	    // Agent options
	    agentOptions.forEach(opt => {
	        optionsByValue[opt.value] = opt;
	    });

	    // Pick sensible defaults: first and second agents when available
	    const agentValues = agentOptions.map(o => o.value);
	    const defaultLeft = agentValues[0] || 'human';
	    const defaultRight = agentValues[1] || agentValues[0] || 'human';

	    currentHeadToHeadComparison = {
	        result,
	        optionsByValue,
	        selection: {
	            left: defaultLeft,
	            right: defaultRight,
	        },
	        view: {
	            left: 'diff',
	            right: 'diff',
	        },
	    };

	    buildAgentComparisonColumn('left');
	    buildAgentComparisonColumn('right');

	    card.style.display = 'block';

	    // Render initial content
	    updateAgentComparisonSide('left');
	    updateAgentComparisonSide('right');
	}

	/**
	 * Build one side (left/right) of the comparison UI.
	 */
	function buildAgentComparisonColumn(side) {
	    if (!currentHeadToHeadComparison) return;
	    const state = currentHeadToHeadComparison;

	    const columnId = side === 'left' ? 'agent-comparison-left' : 'agent-comparison-right';
	    const column = document.getElementById(columnId);
	    if (!column) return;

	    const selectId = `comparison-${side}-entity`;
	    const viewToggleId = `comparison-${side}-view-toggle`;
	    const contentId = `comparison-${side}-content`;
	    const sideLabelText = side === 'left' ? 'Left side' : 'Right side';

	    const optionValues = Object.keys(state.optionsByValue);
	    const optionsHtml = optionValues.map(value => {
	        const opt = state.optionsByValue[value];
	        const label = opt.label || value;
	        const selected = value === state.selection[side] ? 'selected' : '';
	        const safeValue = typeof escapeHtml === 'function' ? escapeHtml(value) : value;
	        const safeLabel = typeof escapeHtml === 'function' ? escapeHtml(label) : label;
	        return `<option value="${safeValue}" ${selected}>${safeLabel}</option>`;
	    }).join('');

	    column.innerHTML = `
	        <div class="agent-comparison-header">
	            <label class="agent-comparison-label">
	                <span>${sideLabelText}</span>
	                <select id="${selectId}" class="agent-comparison-select">
	                    ${optionsHtml}
	                </select>
	            </label>
	            <div class="agent-comparison-view-toggle" id="${viewToggleId}">
	                <button class="btn-action" data-view="summary"><span class="btn-icon">📝</span> Summary</button>
	                <button class="btn-action" data-view="diff"><span class="btn-icon">📄</span> Diff</button>
	                <button class="btn-action" data-view="logs"><span class="btn-icon">📋</span> Logs</button>
	            </div>
	        </div>
	        <div id="${contentId}" class="agent-comparison-content code-block">
	            <em>Select a view to load details…</em>
	        </div>
	    `;

	    const selectEl = document.getElementById(selectId);
	    const viewToggleEl = document.getElementById(viewToggleId);

	    if (selectEl) {
	        selectEl.addEventListener('change', () => {
	            state.selection[side] = selectEl.value;
	            updateAgentComparisonSide(side);
	        });
	    }

	    if (viewToggleEl) {
	        viewToggleEl.addEventListener('click', (event) => {
	            const btn = event.target.closest('button[data-view]');
	            if (!btn) return;

	            const viewType = btn.getAttribute('data-view');
	            state.view[side] = viewType;

	            // Update active state
	            viewToggleEl.querySelectorAll('button[data-view]').forEach(b => b.classList.remove('active'));
	            btn.classList.add('active');

	            updateAgentComparisonSide(side);
	        });

	        // Set initial active button based on state
	        const initialView = state.view[side] || 'diff';
	        const initialBtn = viewToggleEl.querySelector(`button[data-view="${initialView}"]`) ||
	            viewToggleEl.querySelector('button[data-view="diff"]');
	        if (initialBtn) {
	            initialBtn.classList.add('active');
	        }
	    }
	}

	/**
	 * Render the selected entity and view type for one side of the comparison.
	 */
	async function updateAgentComparisonSide(side) {
	    if (!currentHeadToHeadComparison) return;
	    const state = currentHeadToHeadComparison;
	    const { result, optionsByValue } = state;

	    const contentId = side === 'left' ? 'comparison-left-content' : 'comparison-right-content';
	    const contentEl = document.getElementById(contentId);
	    const selectId = `comparison-${side}-entity`;
	    const selectEl = document.getElementById(selectId);
	    if (!contentEl || !selectEl) return;

	    const selectedValue = selectEl.value || state.selection[side];
	    const selection = optionsByValue[selectedValue] || optionsByValue['human'];
	    state.selection[side] = selection.value;

	    const viewToggleId = `comparison-${side}-view-toggle`;
	    const viewToggleEl = document.getElementById(viewToggleId);
	    let viewType = state.view[side] || 'diff';
	    if (viewToggleEl) {
	        const activeBtn = viewToggleEl.querySelector('button.active[data-view]');
	        if (activeBtn) {
	            viewType = activeBtn.getAttribute('data-view');
	            state.view[side] = viewType;
	        }
	    }

	    // Clear content while loading
	    contentEl.innerHTML = '<em>Loading…</em>';

	    if (selection.type === 'agent') {
	        const agentResult = selection.agentResult;
	        if (viewType === 'summary') {
	            const summaryText = agentResult.llm_summary || 'No summary available';
	            const safe = typeof escapeHtml === 'function' ? escapeHtml(summaryText) : summaryText;
	            contentEl.innerHTML = `<div style="line-height: 1.6;">${safe}</div>`;
	        } else if (viewType === 'diff') {
	            const diffText = agentResult.patch_unified || 'No diff available';
	            if (typeof colorizeDiff === 'function') {
	                contentEl.innerHTML = `<pre class="code-block">${colorizeDiff(diffText)}</pre>`;
	            } else {
	                contentEl.textContent = diffText;
	            }
	        } else if (viewType === 'logs') {
	            const logsPath = agentResult.logs_path;
	            if (!logsPath) {
	                contentEl.innerHTML = '<em>No logs available for this agent.</em>';
	                return;
	            }
	            try {
	                const response = await fetch(`${API_BASE}/${logsPath}`);
	                if (!response.ok) {
	                    contentEl.innerHTML = '<em>Failed to load logs.</em>';
	                    return;
	                }
	                const text = await response.text();
	                const logEntries = text.trim().split('\n').map(line => {
	                    try {
	                        return JSON.parse(line);
	                    } catch {
	                        return { raw: line };
	                    }
	                });
	                if (typeof formatLogs === 'function') {
	                    contentEl.innerHTML = formatLogs(logEntries);
	                } else {
	                    contentEl.textContent = text;
	                }
	            } catch (error) {
	                console.error('Error loading logs for comparison view:', error);
	                contentEl.innerHTML = '<em>Error loading logs.</em>';
	            }
	        }
	    } else {
	        // Human (ground truth) selection
	        if (viewType === 'summary') {
	            const repoUrl = result.repo_url || '';
	            const prLink = repoUrl ? `${repoUrl.replace('.git', '')}/pull/${result.pr_number}` : '';
	            const repoName = repoUrl ? repoUrl.split('/').slice(-2).join('/').replace('.git', '') : '';
	            const safeRepo = typeof escapeHtml === 'function' ? escapeHtml(repoName) : repoName;
	            const safeLink = typeof escapeHtml === 'function' ? escapeHtml(prLink) : prLink;
	            contentEl.innerHTML = `
	                <div style="line-height: 1.6;">
	                    <p><strong>Human ground truth</strong> for PR #${result.pr_number}${safeRepo ? ` on ${safeRepo}` : ''}.</p>
	                    ${safeLink ? `<p><a href="${safeLink}" target="_blank">Open PR on GitHub</a></p>` : ''}
	                    <p>This is the reference patch used as the human baseline when judging agent submissions.</p>
	                </div>
	            `;
	        } else if (viewType === 'diff') {
	            // Try to use the human_diff from the result first
	            let diff = result.human_diff;

	            // If not available, try to load from GitHub API
	            if (!diff) {
	                try {
	                    diff = await loadGroundTruthDiffFromCommits(
	                        result.repo_url,
	                        result.base_commit,
	                        result.head_commit,
	                    );
	                } catch (error) {
	                    console.error('Error loading human diff from GitHub:', error);
	                }
	            }

	            if (!diff) {
	                contentEl.innerHTML = '<em>No human diff available.</em>';
	                return;
	            }

	            if (typeof colorizeDiff === 'function') {
	                contentEl.innerHTML = `<pre class="code-block">${colorizeDiff(diff)}</pre>`;
	            } else {
	                contentEl.textContent = diff;
	            }
	        } else if (viewType === 'logs') {
	            contentEl.innerHTML = '<em>Human baseline has no execution logs.</em>';
	        }
	    }
	}

/**
 * Show a specific view (summary, diff, or logs) for an agent
 */
async function showAgentView(agentIdSafe, viewType, logsPath = null) {
    // Hide all views for this agent
    const summarySection = document.getElementById(`summary-${agentIdSafe}`);
    const diffSection = document.getElementById(`diff-${agentIdSafe}`);
    const logsSection = document.getElementById(`logs-${agentIdSafe}`);

    if (summarySection) summarySection.style.display = 'none';
    if (diffSection) diffSection.style.display = 'none';
    if (logsSection) logsSection.style.display = 'none';

    // Show the requested view
    if (viewType === 'summary' && summarySection) {
        summarySection.style.display = 'block';
    } else if (viewType === 'diff' && diffSection) {
        diffSection.style.display = 'block';
    } else if (viewType === 'logs' && logsSection) {
        logsSection.style.display = 'block';

        // Load logs if not yet loaded
        if (logsPath && logsSection.querySelector('em')) {
            logsSection.innerHTML = '<div style="text-align: center; padding: 20px;"><em>Loading logs...</em></div>';

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

                logsSection.innerHTML = formatLogs(logEntries);
            } catch (error) {
                logsSection.innerHTML = `
                    <div style="color: #d32f2f; padding: 10px;">
                        <strong>Error loading logs:</strong> ${error.message}
                    </div>
                `;
            }
        }
    }
}

    /**
     * Render compact metric comparison for a pairwise decision.
     * Uses decision.raw_scores["A"|"B"] when available.
     */
    function renderPairwiseMetrics(rawScores) {
        if (!rawScores || (Object.keys(rawScores).length === 0)) {
            return '<span style="color: var(--text-muted);">N/A</span>';
        }

        const scoresA = rawScores.A || rawScores.a || null;
        const scoresB = rawScores.B || rawScores.b || null;

        if (!scoresA && !scoresB) {
            return '<span style="color: var(--text-muted);">N/A</span>';
        }

        const metricOrder = [
            'matches_human',
            'correctness',
            'completeness',
            'code_reuse',
            'best_practices',
            'unsolicited_docs',
            'code_quality',
            'integration',
        ];

        const labels = {
            matches_human: 'matches_human',
            correctness: 'correctness',
            completeness: 'completeness',
            code_reuse: 'code_reuse',
            best_practices: 'best_practices',
            unsolicited_docs: 'unsolicited_docs',
            code_quality: 'code_quality',
            integration: 'integration',
        };

        const rows = [];

        metricOrder.forEach(key => {
            const aVal = scoresA && scoresA[key] !== undefined && scoresA[key] !== null
                ? formatScore(scoresA[key])
                : '-';
            const bVal = scoresB && scoresB[key] !== undefined && scoresB[key] !== null
                ? formatScore(scoresB[key])
                : '-';

            if (aVal === '-' && bVal === '-') return;

            rows.push(`
                <div style="display: flex; justify-content: space-between; gap: 4px;">
                    <span style="flex: 0 0 40%; font-size: 0.8em; color: var(--text-muted);">${labels[key] || key}</span>
                    <span style="flex: 0 0 30%; font-size: 0.8em;">A: ${aVal}</span>
                    <span style="flex: 0 0 30%; font-size: 0.8em;">B: ${bVal}</span>
                </div>
            `);
        });

        if (rows.length === 0) {
            return '<span style="color: var(--text-muted);">N/A</span>';
        }

        return rows.join('');
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
                    <th>Key Metrics (A vs B)</th>
                    <th>Rationale & Notes</th>
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

            const metricsHtml = renderPairwiseMetrics(decision.raw_scores || {});

            const notes = decision.comparison_to_human_notes || {};
            const notesParts = [];
            if (notes.A) {
                notesParts.push(`<div style="margin-top: 4px;"><strong>A notes:</strong> ${notes.A}</div>`);
            }
            if (notes.B) {
                notesParts.push(`<div style="margin-top: 2px;"><strong>B notes:</strong> ${notes.B}</div>`);
            }
            const notesHtml = notesParts.join('');

            row.innerHTML = `
                <td style="font-size: 0.85em;">${decision.submission_a_id}</td>
                <td style="font-size: 0.85em;">${decision.submission_b_id}</td>
                <td>${judgeDisplay}</td>
                <td><strong>${winnerDisplay}</strong></td>
                <td>${metricsHtml}</td>
                <td style="font-size: 0.9em; max-width: 420px;">
                    <div>${decision.rationale || 'N/A'}</div>
                    ${notesHtml}
                </td>
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

