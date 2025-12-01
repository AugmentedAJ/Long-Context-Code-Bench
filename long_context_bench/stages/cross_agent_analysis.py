"""Cross-agent analysis: Compare multiple agents' solutions for the same PR.

Uses Claude Code CLI for all analysis operations.
"""

import json
import platform
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console

from long_context_bench import __version__
from long_context_bench.models import (
    Sample, Edit, Scores, AgentResult, ComparativeAnalysis, CrossAgentJudge
)
from long_context_bench.stages.judge import (
    load_sample, load_edit, get_ground_truth_diff, compute_llm_scores
)

console = Console()


def find_edits_for_pr(
    pr_number: int,
    repo_url: str,
    output_dir: Path,
    test_label: Optional[str] = None,
) -> List[Tuple[Edit, Path]]:
    """Find all edits for a specific PR.

    Args:
        pr_number: PR number
        repo_url: Repository URL
        output_dir: Output directory (should contain edits/)
        test_label: Optional test label to filter by

    Returns:
        List of (Edit, edit_file_path) tuples (deduplicated by runner:model, preferring official runs)
    """
    edits_dir = output_dir / "edits"
    summaries_dir = output_dir / "summaries"

    if not edits_dir.exists():
        console.print(f"[red]Edits directory not found: {edits_dir}[/red]")
        return []

    # Extract repo identifier
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    owner = repo_url.rstrip("/").split("/")[-2]
    pr_id = f"{owner}_{repo_name}_pr{pr_number}"

    console.print(f"[cyan]Searching for edits for {pr_id}...[/cyan]")

    # Get list of official run IDs (those with summaries)
    official_run_ids = set()
    if summaries_dir.exists():
        for summary_dir in summaries_dir.iterdir():
            if summary_dir.is_dir():
                # Summary dir format: {run_id}_{runner}_{model}
                run_id = summary_dir.name.split("_")[0]
                official_run_ids.add(run_id)

    # Collect all edits, grouped by runner:model
    agent_edits = {}  # Map from "runner:model" to list of (edit, edit_file, is_official)

    for edit_file in edits_dir.rglob(f"*/{pr_id}/edit.json"):
        try:
            edit = load_edit(edit_file)

            # Filter by test_label if specified
            if test_label and edit.test_label != test_label:
                continue

            agent_key = f"{edit.runner}:{edit.model}"

            # Check if this edit is in an official run directory
            # Path format: edits/{runner}/{model}/{run_id}/{pr_id}/edit.json
            # Extract run_id from path (3rd component from edits/)
            path_parts = edit_file.parts
            edits_idx = path_parts.index("edits")
            run_id_from_path = path_parts[edits_idx + 3] if len(path_parts) > edits_idx + 3 else None
            is_official = run_id_from_path in official_run_ids

            if agent_key not in agent_edits:
                agent_edits[agent_key] = []

            agent_edits[agent_key].append((edit, edit_file, is_official, run_id_from_path))
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to load {edit_file}: {e}[/yellow]")

    # For each agent, select the best edit (prefer official runs)
    edits = []
    for agent_key, candidates in sorted(agent_edits.items()):
        # Sort by: official first, then by run_id from path for consistency
        candidates.sort(key=lambda x: (not x[2], x[3] or ""))

        selected_edit, selected_file, is_official, run_id_from_path = candidates[0]
        edits.append((selected_edit, selected_file))

        status = "[official]" if is_official else "[standalone]"
        display_run_id = run_id_from_path or selected_edit.edit_run_id
        console.print(f"  Found: {agent_key} (run {display_run_id}) {status}")

        # Log skipped candidates
        if len(candidates) > 1:
            for edit, _, _, rid in candidates[1:]:
                skipped_run_id = rid or edit.edit_run_id
                console.print(f"    Skipping: run {skipped_run_id} (using {display_run_id} instead)")

    if not edits:
        console.print(f"[yellow]No edits found for PR {pr_number}[/yellow]")
    else:
        console.print(f"[green]Found {len(edits)} agent(s) for PR {pr_number}[/green]")

    return edits


def compute_comparative_analysis(
    agent_results: List[AgentResult],
    task_instructions: str,
    ground_truth_diff: str,
    judge_model: str,
) -> Optional[ComparativeAnalysis]:
    """Use LLM to generate comparative analysis of multiple agents.
    
    Args:
        agent_results: List of agent results
        task_instructions: Task instructions
        ground_truth_diff: Ground truth diff
        judge_model: Judge model name
        
    Returns:
        ComparativeAnalysis or None if failed
    """
    if len(agent_results) < 2:
        console.print("[yellow]Need at least 2 agents for comparative analysis[/yellow]")
        return None
    
    # Build prompt with all agent solutions
    agent_sections = []
    for result in agent_results:
        agent_name = f"{result.runner}:{result.model}"
        agent_sections.append(f"""
**Agent: {agent_name}**
Status: {result.status}
Elapsed: {result.elapsed_ms}ms
Aggregate Score: {result.aggregate:.2f}
Individual Scores:
- Correctness: {result.scores.correctness:.2f}
- Completeness: {result.scores.completeness:.2f}
- Code Reuse: {result.scores.code_reuse:.2f}
- Best Practices: {result.scores.best_practices:.2f}
- Unsolicited Docs: {result.scores.unsolicited_docs:.2f}

Diff:
```diff
{result.patch_unified[:5000]}{"..." if len(result.patch_unified) > 5000 else ""}
```
""")
    
    prompt = f"""You are an expert code reviewer comparing multiple AI coding agents' solutions to the same task.

**Task Instructions:**
{task_instructions}

**Ground Truth Diff (Expected Changes):**
```diff
{ground_truth_diff[:5000]}{"..." if len(ground_truth_diff) > 5000 else ""}
```

**Agent Solutions:**
{"".join(agent_sections)}

**Your Task:**
Compare these agents' approaches and provide a comprehensive analysis.

**Important Guidelines:**
- Always refer to agents by their full name (e.g., "auggie:sonnet4.5", "claude-code:claude-sonnet-4-5", "factory:claude-sonnet-4-5-20250929")
- Do NOT use generic labels like "Agent 1", "Agent 2", etc.
- Use the exact agent names as shown in the "Agent:" headers above

**Output Format:**
Respond with ONLY a valid JSON object (no markdown, no code blocks):

{{
  "summary": "<2-3 sentence overall comparison using agent names, not numbers>",
  "best_agent": "<runner:model of best performing agent>",
  "best_agent_reasoning": "<why this agent performed best, using agent name not number>",
  "approach_differences": "<key differences in how agents approached the problem, using agent names not numbers>",
  "ranking": ["<runner:model>", "<runner:model>", ...]
}}"""

    try:
        console.print(f"[cyan]Generating comparative analysis with Claude Code CLI (model: {judge_model})...[/cyan]")

        # Use Claude Code CLI for analysis
        cmd = [
            "claude",
            "--output-format", "stream-json",
            "--verbose",
            "-p",  # print-and-exit, non-interactive
        ]

        # Add model if not using alias
        if judge_model not in ["sonnet", "opus", "haiku"]:
            cmd.extend(["--model", judge_model])

        # Run Claude CLI (prompt on stdin)
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode != 0:
            raise Exception(f"Claude CLI failed with code {result.returncode}: {result.stderr}")

        # Parse stream-json output
        content = None
        lines = [line for line in result.stdout.split('\n') if line.strip()]
        for line in lines:
            try:
                event = json.loads(line)
                if event.get('type') == 'assistant' and 'message' in event:
                    message = event['message']
                    if 'content' in message and isinstance(message['content'], list):
                        text_parts = []
                        for block in message['content']:
                            if block.get('type') == 'text' and 'text' in block:
                                text_parts.append(block['text'])
                        if text_parts:
                            content = ''.join(text_parts)
                            break
                elif event.get('type') == 'result' and 'result' in event:
                    content = event['result']
                    break
            except json.JSONDecodeError:
                continue

        if not content:
            content = result.stdout.strip()

        # Handle markdown code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            json_lines = []
            in_code_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or (not line.strip().startswith("```")):
                    json_lines.append(line)
            content = "\n".join(json_lines).strip()

        parsed = json.loads(content)

        analysis = ComparativeAnalysis(
            summary=parsed.get("summary", ""),
            best_agent=parsed.get("best_agent", ""),
            best_agent_reasoning=parsed.get("best_agent_reasoning", ""),
            approach_differences=parsed.get("approach_differences", ""),
            ranking=parsed.get("ranking", []),
        )

        console.print(f"[green]✓ Comparative analysis completed[/green]")
        return analysis

    except Exception as e:
        console.print(f"[yellow]Warning: Comparative analysis failed: {e}[/yellow]")
        return None


def run_cross_agent_analysis(
    pr_number: int,
    output_dir: Path,
    judge_model: str,
    comparative: bool = False,
    test_label: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    force: bool = False,
) -> Optional[str]:
    """Run cross-agent analysis for a specific PR using Claude Code CLI.

    Args:
        pr_number: PR number to analyze
        output_dir: Output directory (should contain samples/ and edits/)
        judge_model: Judge model for Claude Code CLI (e.g., claude-sonnet-4-5)
        comparative: If True, generate comparative analysis across agents
        test_label: Optional test label to filter edits
        cache_dir: Optional cache directory for repositories
        force: If True, re-analyze even if output exists

    Returns:
        Analysis run ID or None if failed
    """
    analysis_run_id = str(uuid.uuid4())[:8]

    console.print(f"[bold]Starting cross-agent analysis for PR {pr_number}[/bold]")
    console.print(f"  Analysis run ID: {analysis_run_id}")
    console.print(f"  Judge model: {judge_model}")
    if comparative:
        console.print(f"  Comparative analysis: enabled")
    if test_label:
        console.print(f"  Test label: {test_label}")
    
    # Find sample
    samples_dir = output_dir / "samples"
    sample_file = None
    for sf in samples_dir.rglob(f"*/elastic_elasticsearch_pr{pr_number}/sample.json"):
        sample_file = sf
        break
    
    if not sample_file:
        console.print(f"[red]Sample not found for PR {pr_number}[/red]")
        return None
    
    sample = load_sample(sample_file)
    console.print(f"[green]✓ Loaded sample for PR {pr_number}[/green]")
    
    # Find all edits for this PR
    edits = find_edits_for_pr(pr_number, sample.repo_url, output_dir, test_label)
    
    if len(edits) < 2:
        console.print(f"[yellow]Need at least 2 agents to compare (found {len(edits)})[/yellow]")
        return None
    
    # Get ground truth diff
    console.print(f"[cyan]Fetching ground truth diff...[/cyan]")
    ground_truth_diff = get_ground_truth_diff(sample, cache_dir)
    console.print(f"[green]✓ Ground truth diff fetched[/green]")
    
    # Judge each agent's edit
    agent_results = []
    for edit, edit_file in edits:
        console.print(f"[cyan]Judging {edit.runner}:{edit.model}...[/cyan]")

        # Compute scores using Claude Code CLI
        scores, rationale, llm_rating, llm_summary = compute_llm_scores(
            edit.patch_unified,
            ground_truth_diff,
            sample.task_instructions,
            judge_model,
        )

        aggregate = (
            scores.correctness +
            scores.completeness +
            scores.code_reuse +
            scores.best_practices +
            scores.unsolicited_docs
        ) / 5.0

        # Compute relative logs path for web UI
        # edit_file is like: output/edits/{runner}/{model}/{run_id}/{pr_id}/edit.json
        # logs_path should be: edits/{runner}/{model}/{run_id}/{pr_id}/logs.jsonl
        logs_file = edit_file.parent / "logs.jsonl"
        logs_path = None
        if logs_file.exists():
            # Get path relative to output directory
            try:
                # Find 'edits' in the path and construct relative path from there
                path_parts = edit_file.parts
                edits_idx = path_parts.index("edits")
                logs_path = str(Path(*path_parts[edits_idx:]).parent / "logs.jsonl")
            except (ValueError, IndexError):
                # Fallback: use edit.logs_path if available
                logs_path = edit.logs_path if hasattr(edit, 'logs_path') else None

        agent_result = AgentResult(
            runner=edit.runner,
            model=edit.model,
            edit_run_id=edit.edit_run_id,
            status=edit.status,
            elapsed_ms=edit.elapsed_ms,
            patch_unified=edit.patch_unified,
            scores=scores,
            aggregate=aggregate,
            rationale=rationale,
            llm_rating=llm_rating,
            llm_summary=llm_summary,
            errors=edit.errors,
            logs_path=logs_path,
        )
        agent_results.append(agent_result)

        if llm_rating is not None:
            console.print(f"  Aggregate: {aggregate:.2f} | Rating: {llm_rating:.2f} | {llm_summary}")
        else:
            console.print(f"  Aggregate: {aggregate:.2f}")
    
    # Generate comparative analysis if requested
    comparative_analysis = None
    if comparative:
        comparative_analysis = compute_comparative_analysis(
            agent_results,
            sample.task_instructions,
            ground_truth_diff,
            judge_model,
        )

    # Create cross-agent judge artifact
    cross_agent_judge = CrossAgentJudge(
        repo_url=sample.repo_url,
        pr_number=pr_number,
        base_commit=sample.base_commit,
        head_commit=sample.head_commit,
        task_instructions=sample.task_instructions,
        ground_truth_diff=ground_truth_diff,
        judge_mode="llm",
        judge_model=judge_model,
        test_label=test_label,
        agent_results=agent_results,
        comparative_analysis=comparative_analysis,
        timestamp=datetime.utcnow().isoformat(),
        analysis_run_id=analysis_run_id,
    )
    
    # Save output
    output_file = output_dir / "cross_agent_analysis" / f"pr{pr_number}_{analysis_run_id}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w") as f:
        f.write(cross_agent_judge.model_dump_json(indent=2))
    
    console.print(f"[green]✓ Cross-agent analysis saved to {output_file}[/green]")
    
    # Print summary
    console.print("\n[bold]Analysis Summary:[/bold]")
    console.print(f"  Agents compared: {len(agent_results)}")
    for result in sorted(agent_results, key=lambda x: x.aggregate, reverse=True):
        console.print(f"    {result.runner}:{result.model} - Aggregate: {result.aggregate:.2f}")
    
    if comparative_analysis:
        console.print(f"\n[bold]Best Agent:[/bold] {comparative_analysis.best_agent}")
        console.print(f"[bold]Reasoning:[/bold] {comparative_analysis.best_agent_reasoning}")
    
    return analysis_run_id

