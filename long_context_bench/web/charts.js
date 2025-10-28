/**
 * Chart rendering utilities using Chart.js
 */

// Chart instances (for cleanup)
const chartInstances = {};

/**
 * Destroy a chart if it exists
 */
function destroyChart(chartId) {
    if (chartInstances[chartId]) {
        chartInstances[chartId].destroy();
        delete chartInstances[chartId];
    }
}

/**
 * Create score distribution chart
 */
function createScoreDistributionChart(canvasId, summaries) {
    destroyChart(canvasId);
    
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const scores = summaries.map(s => s.mean_aggregate);
    
    // Create histogram bins
    const bins = [-1, -0.5, 0, 0.5, 1];
    const counts = new Array(bins.length - 1).fill(0);
    
    scores.forEach(score => {
        for (let i = 0; i < bins.length - 1; i++) {
            if (score >= bins[i] && score < bins[i + 1]) {
                counts[i]++;
                break;
            }
        }
    });

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['-1 to -0.5', '-0.5 to 0', '0 to 0.5', '0.5 to 1'],
            datasets: [{
                label: 'Number of Runs',
                data: counts,
                backgroundColor: 'rgba(0, 102, 204, 0.7)',
                borderColor: 'rgba(0, 102, 204, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

/**
 * Create success rate chart
 */
function createSuccessRateChart(canvasId, summaries) {
    destroyChart(canvasId);
    
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const labels = summaries.map(s => `${s.runner || 'Unknown'} (${s.model || 'Unknown'})`);
    const data = summaries.map(s => s.success_rate * 100);

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Success Rate (%)',
                data: data,
                backgroundColor: 'rgba(40, 167, 69, 0.7)',
                borderColor: 'rgba(40, 167, 69, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });
}

/**
 * Create score breakdown chart (for single run)
 */
function createScoreBreakdownChart(canvasId, summary) {
    destroyChart(canvasId);
    
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Correctness', 'Completeness', 'Code Reuse', 'Best Practices', 'Unsolicited Docs'],
            datasets: [{
                label: 'Score',
                data: [
                    summary.mean_correctness,
                    summary.mean_completeness,
                    summary.mean_code_reuse,
                    summary.mean_best_practices,
                    summary.mean_unsolicited_docs
                ],
                backgroundColor: [
                    'rgba(0, 102, 204, 0.7)',
                    'rgba(40, 167, 69, 0.7)',
                    'rgba(255, 193, 7, 0.7)',
                    'rgba(108, 117, 125, 0.7)',
                    'rgba(220, 53, 69, 0.7)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    min: -1,
                    max: 1
                }
            }
        }
    });
}

/**
 * Create score distribution histogram (for single run)
 */
function createRunScoreDistribution(canvasId, judges) {
    destroyChart(canvasId);
    
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const scores = judges.map(j => j.aggregate);
    
    // Create histogram bins
    const bins = [-1, -0.5, 0, 0.5, 1];
    const counts = new Array(bins.length - 1).fill(0);
    
    scores.forEach(score => {
        for (let i = 0; i < bins.length - 1; i++) {
            if (score >= bins[i] && score < bins[i + 1]) {
                counts[i]++;
                break;
            }
        }
    });

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['-1 to -0.5', '-0.5 to 0', '0 to 0.5', '0.5 to 1'],
            datasets: [{
                label: 'Number of PRs',
                data: counts,
                backgroundColor: 'rgba(0, 102, 204, 0.7)',
                borderColor: 'rgba(0, 102, 204, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

/**
 * Create radar chart for comparison
 */
function createRadarChart(canvasId, summaries) {
    destroyChart(canvasId);
    
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const colors = [
        'rgba(0, 102, 204, 0.5)',
        'rgba(40, 167, 69, 0.5)',
        'rgba(255, 193, 7, 0.5)',
        'rgba(220, 53, 69, 0.5)',
        'rgba(108, 117, 125, 0.5)'
    ];

    const datasets = summaries.map((summary, index) => ({
        label: `${summary.runner || 'Unknown'} (${summary.model || 'Unknown'})`,
        data: [
            summary.mean_correctness,
            summary.mean_completeness,
            summary.mean_code_reuse,
            summary.mean_best_practices,
            summary.mean_unsolicited_docs
        ],
        backgroundColor: colors[index % colors.length],
        borderColor: colors[index % colors.length].replace('0.5', '1'),
        borderWidth: 2
    }));

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Correctness', 'Completeness', 'Code Reuse', 'Best Practices', 'Unsolicited Docs'],
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                r: {
                    min: -1,
                    max: 1,
                    ticks: {
                        stepSize: 0.5
                    }
                }
            }
        }
    });
}

/**
 * Create bar comparison chart
 */
function createBarComparisonChart(canvasId, summaries) {
    destroyChart(canvasId);
    
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const labels = summaries.map(s => `${s.runner || 'Unknown'} (${s.model || 'Unknown'})`);
    const aggregateScores = summaries.map(s => s.mean_aggregate);
    const successRates = summaries.map(s => s.success_rate);

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Aggregate Score',
                    data: aggregateScores,
                    backgroundColor: 'rgba(0, 102, 204, 0.7)',
                    borderColor: 'rgba(0, 102, 204, 1)',
                    borderWidth: 1,
                    yAxisID: 'y'
                },
                {
                    label: 'Success Rate',
                    data: successRates,
                    backgroundColor: 'rgba(40, 167, 69, 0.7)',
                    borderColor: 'rgba(40, 167, 69, 1)',
                    borderWidth: 1,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    min: -1,
                    max: 1,
                    title: {
                        display: true,
                        text: 'Aggregate Score'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    min: 0,
                    max: 1,
                    title: {
                        display: true,
                        text: 'Success Rate'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
}

