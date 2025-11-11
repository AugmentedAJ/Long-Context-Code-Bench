/**
 * Task detail page logic
 */

// Global state
window.currentLogs = null;
window.currentLogsRaw = null;
window.currentGroundTruthDiff = null;

/**
 * Load task details
 */
async function loadTaskDetails(runId, prNumber) {
    try {
        const index = await loadIndex();

        // Find the run in the index
        // runId can be either a run_id or a summary_path
        const runEntry = index.runs.find(r =>
            r.run_id === runId || r.summary_path === runId
        );
        if (!runEntry) {
            throw new Error(`Run ${runId} not found`);
        }

        // Load sample data
        const sample = await loadTaskSample(prNumber);
        
        // Load edit data
        const edit = await loadTaskEdit(runEntry, prNumber);
        
        // Load judge data
        const judge = await loadTaskJudge(runEntry, prNumber);
        
        // Load logs
        const logs = await loadTaskLogs(runEntry, prNumber);
        
        // Load ground truth diff
        const groundTruthDiff = await loadGroundTruthDiff(sample);
        
        // Display all data
        displayTaskHeader(sample, edit, runEntry);
        displayTaskScores(judge);
        displayTaskInstructions(sample);
        displayTaskStats(sample);
        displayDiffs(groundTruthDiff, edit);
        displayLogs(logs);
        displayJudgeRationale(judge);
        
        // Update timestamp
        document.getElementById('last-updated').textContent = formatTimestamp(index.last_updated);
    } catch (error) {
        console.error('Error loading task details:', error);
        document.getElementById('task-title').textContent = 'Error loading task';
        alert('Error loading task details: ' + error.message);
    }
}

/**
 * Load sample data for a specific PR
 */
async function loadTaskSample(prNumber) {
    // Samples are stored in samples/v0/{owner}_{repo}_pr{number}/sample.json
    // For now, hardcode v0 and elastic_elasticsearch
    const prId = `elastic_elasticsearch_pr${prNumber}`;
    const samplePath = `samples/v0/${prId}/sample.json`;

    const response = await fetch(`${API_BASE}/${samplePath}`);
    if (!response.ok) {
        throw new Error(`Failed to load sample: ${response.statusText}`);
    }

    return await response.json();
}

/**
 * Load edit data for a specific task
 */
async function loadTaskEdit(runEntry, prNumber) {
    // Use edit_run_id if available, otherwise fall back to run_id
    const runIdToUse = runEntry.edit_run_id || runEntry.run_id;
    const editPath = `edits/${runEntry.runner}/${runEntry.model}/${runIdToUse}`;
    const prId = `elastic_elasticsearch_pr${prNumber}`; // TODO: Make this more generic
    
    try {
        // Load edit.json (contains all edit data)
        const editResponse = await fetch(`${API_BASE}/${editPath}/${prId}/edit.json`);
        if (!editResponse.ok) {
            throw new Error(`Failed to load edit: ${editResponse.statusText}`);
        }
        const edit = await editResponse.json();

        // Load patch file if not already in edit.json
        if (!edit.patch_unified) {
            const patchResponse = await fetch(`${API_BASE}/${editPath}/${prId}/edit.patch`);
            if (patchResponse.ok) {
                edit.patch_unified = await patchResponse.text();
            } else {
                edit.patch_unified = '';
            }
        }

        return edit;
    } catch (error) {
        console.error('Error loading edit:', error);
        return null;
    }
}

/**
 * Load judge data for a specific task
 */
async function loadTaskJudge(runEntry, prNumber) {
    // Judge path: judges/llm/{judge_model}/{judge_run_id}/{pr_id}/judge.json
    // judge_mode is always 'llm' now (kept in data for backward compatibility)
    const judgeModel = runEntry.judge_model || 'default';
    // Use judge_run_id if available, otherwise fall back to run_id
    const runIdToUse = runEntry.judge_run_id || runEntry.run_id;
    const judgePath = `judges/llm/${judgeModel}/${runIdToUse}`;
    const prId = `elastic_elasticsearch_pr${prNumber}`; // TODO: Make this more generic

    try {
        const response = await fetch(`${API_BASE}/${judgePath}/${prId}/judge.json`);
        if (!response.ok) {
            throw new Error(`Failed to load judge: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error loading judge:', error);
        return null;
    }
}

/**
 * Load logs for a specific task
 */
async function loadTaskLogs(runEntry, prNumber) {
    // Use edit_run_id if available, otherwise fall back to run_id
    const runIdToUse = runEntry.edit_run_id || runEntry.run_id;
    const editPath = `edits/${runEntry.runner}/${runEntry.model}/${runIdToUse}`;
    const prId = `elastic_elasticsearch_pr${prNumber}`; // TODO: Make this more generic
    
    try {
        const response = await fetch(`${API_BASE}/${editPath}/${prId}/logs.jsonl`);
        if (!response.ok) {
            console.warn('Logs not found');
            return [];
        }
        
        const text = await response.text();
        window.currentLogsRaw = text;
        
        // Parse JSONL
        const lines = text.trim().split('\n');
        const logs = lines.map(line => {
            try {
                return JSON.parse(line);
            } catch (e) {
                console.warn('Failed to parse log line:', line);
                return null;
            }
        }).filter(log => log !== null);
        
        window.currentLogs = logs;
        return logs;
    } catch (error) {
        console.error('Error loading logs:', error);
        return [];
    }
}

/**
 * Load ground truth diff
 */
async function loadGroundTruthDiff(sample) {
    // For now, we'll compute this on the fly using the GitHub API
    // In production, this should be cached or pre-computed
    try {
        const owner = sample.repo_url.split('/')[3];
        const repo = sample.repo_url.split('/')[4].replace('.git', '');
        
        const url = `https://api.github.com/repos/${owner}/${repo}/compare/${sample.base_commit}...${sample.head_commit}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`Failed to fetch diff: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Convert to unified diff format
        let diff = '';
        for (const file of data.files) {
            if (file.patch) {
                diff += `diff --git a/${file.filename} b/${file.filename}\n`;
                diff += `--- a/${file.filename}\n`;
                diff += `+++ b/${file.filename}\n`;
                diff += file.patch + '\n';
            }
        }
        
        window.currentGroundTruthDiff = diff;
        return diff;
    } catch (error) {
        console.error('Error loading ground truth diff:', error);
        return 'Error loading ground truth diff. This may require GitHub API access.';
    }
}

/**
 * Display task header
 */
function displayTaskHeader(sample, edit, runEntry) {
    const repoName = sample.repo_url.split('/').slice(-2).join('/').replace('.git', '');
    
    document.getElementById('task-title').textContent = `PR #${sample.pr_number}`;
    document.getElementById('task-repo').textContent = repoName;
    document.getElementById('task-pr-number').innerHTML = `<a href="${sample.repo_url.replace('.git', '')}/pull/${sample.pr_number}" target="_blank">${sample.pr_number}</a>`;
    document.getElementById('task-agent').textContent = runEntry.runner || '-';
    document.getElementById('task-model').textContent = runEntry.model || '-';
    
    if (edit) {
        document.getElementById('task-status').textContent = edit.status || '-';
        document.getElementById('task-elapsed').textContent = edit.elapsed_ms ? `${(edit.elapsed_ms / 1000).toFixed(1)}s` : '-';
    }
}

/**
 * Display task scores
 */
function displayTaskScores(judge) {
    if (!judge) {
        return;
    }
    
    document.getElementById('score-aggregate').textContent = judge.aggregate.toFixed(2);
    document.getElementById('score-correctness').textContent = judge.scores.correctness.toFixed(2);
    document.getElementById('score-completeness').textContent = judge.scores.completeness.toFixed(2);
    document.getElementById('score-code-reuse').textContent = judge.scores.code_reuse.toFixed(2);
    document.getElementById('score-best-practices').textContent = judge.scores.best_practices.toFixed(2);
    document.getElementById('score-unsolicited-docs').textContent = judge.scores.unsolicited_docs.toFixed(2);
    
    // Color code the scores
    const scoreElements = document.querySelectorAll('.task-scores .metric-value');
    scoreElements.forEach(el => {
        const score = parseFloat(el.textContent);
        if (!isNaN(score)) {
            if (score >= 0.7) {
                el.style.color = '#22c55e';
            } else if (score >= 0.3) {
                el.style.color = '#eab308';
            } else if (score >= 0) {
                el.style.color = '#f97316';
            } else {
                el.style.color = '#ef4444';
            }
        }
    });
}

/**
 * Display task instructions
 */
function displayTaskInstructions(sample) {
    document.getElementById('task-instructions-content').textContent = sample.task_instructions;
}

/**
 * Display task statistics
 */
function displayTaskStats(sample) {
    document.getElementById('stat-files-changed').textContent = sample.stats.files_changed;
    document.getElementById('stat-lines-added').textContent = sample.stats.lines_added;
    document.getElementById('stat-lines-deleted').textContent = sample.stats.lines_deleted;
    document.getElementById('stat-diff-hunks').textContent = sample.stats.total_diff_hunks;
    document.getElementById('stat-context-size').textContent = formatBytes(sample.stats.context_size_bytes);
    document.getElementById('stat-base-commit').textContent = sample.base_commit.substring(0, 8);
    document.getElementById('stat-head-commit').textContent = sample.head_commit.substring(0, 8);
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

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Display diffs
 */
function displayDiffs(groundTruthDiff, edit) {
    const submissionDiff = edit ? edit.patch_unified : '';

    // Ground truth diff
    const gtPre = document.querySelector('#ground-truth-diff pre');
    gtPre.innerHTML = groundTruthDiff ? colorizeDiff(groundTruthDiff) : 'No ground truth diff available';

    // Submission diff
    const subPre = document.querySelector('#submission-diff pre');
    subPre.innerHTML = submissionDiff ? colorizeDiff(submissionDiff) : 'No submission diff available';

    // Side-by-side
    const sideBySideContainer = document.querySelector('#side-by-side-diff .side-by-side-container');
    sideBySideContainer.querySelector('.diff-column:first-child pre').innerHTML =
        groundTruthDiff ? colorizeDiff(groundTruthDiff) : 'No ground truth diff available';
    sideBySideContainer.querySelector('.diff-column:last-child pre').innerHTML =
        submissionDiff ? colorizeDiff(submissionDiff) : 'No submission diff available';
}

/**
 * Display logs
 */
function displayLogs(logs) {
    const container = document.getElementById('logs-content');

    if (!logs || logs.length === 0) {
        container.innerHTML = '<p class="loading">No logs available</p>';
        return;
    }

    const showAll = document.getElementById('show-all-logs').checked;
    const showStdout = document.getElementById('show-stdout').checked;

    // Filter logs
    let filteredLogs = logs;
    if (!showAll) {
        filteredLogs = filteredLogs.filter(log =>
            log.event === 'agent_start' ||
            log.event === 'agent_run' ||
            log.event === 'agent_complete' ||
            log.event === 'agent_error'
        );
    }

    // Build HTML
    let html = '<div class="log-entries">';

    for (const log of filteredLogs) {
        const timestamp = new Date(log.timestamp * 1000).toLocaleString();
        const eventClass = log.event ? log.event.replace('_', '-') : 'unknown';

        html += `<div class="log-entry log-${eventClass}">`;
        html += `<div class="log-header">`;
        html += `<span class="log-timestamp">${timestamp}</span>`;
        html += `<span class="log-event">${log.event || 'unknown'}</span>`;
        html += `</div>`;

        if (log.stdout && showStdout) {
            html += `<div class="log-stdout"><pre>${escapeHtml(log.stdout)}</pre></div>`;
        }

        if (log.stderr) {
            html += `<div class="log-stderr"><pre>${escapeHtml(log.stderr)}</pre></div>`;
        }

        // Show other properties
        const otherProps = Object.keys(log).filter(k =>
            k !== 'timestamp' && k !== 'event' && k !== 'stdout' && k !== 'stderr'
        );

        if (otherProps.length > 0) {
            html += `<div class="log-details">`;
            for (const prop of otherProps) {
                const value = typeof log[prop] === 'object' ? JSON.stringify(log[prop], null, 2) : log[prop];
                html += `<div class="log-detail"><strong>${prop}:</strong> ${escapeHtml(String(value))}</div>`;
            }
            html += `</div>`;
        }

        html += `</div>`;
    }

    html += '</div>';
    container.innerHTML = html;
}

/**
 * Display judge rationale
 */
function displayJudgeRationale(judge) {
    if (!judge || !judge.rationale) {
        document.getElementById('judge-rationale-section').style.display = 'none';
        return;
    }

    document.getElementById('judge-rationale-section').style.display = 'block';
    document.getElementById('judge-rationale-content').textContent = judge.rationale;
}

/**
 * Format bytes
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

