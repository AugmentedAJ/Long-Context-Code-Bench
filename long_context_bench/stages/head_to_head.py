"""Head-to-head agent-based judging stage.

Implements pairwise comparisons between agent submissions for a single PR.
"""

from __future__ import annotations

import json
import hashlib
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console

from long_context_bench.models import (
    Sample,
    Edit,
    Scores,
    AgentResult,
    AgentVsHumanDecision,
    PairwiseJudgeDecision,
    HeadToHeadAgentStats,
    HeadToHeadPRResult,
    CrossAgentJudge,
)
from long_context_bench.stages.judge import (
    load_sample,
    get_ground_truth_diff,
)
from long_context_bench.stages.cross_agent_analysis import find_edits_for_pr
from long_context_bench.stages.edit import materialize_workspace
from long_context_bench.runners import get_runner_adapter

console = Console()


def _extract_changed_files_from_diff(diff: str, max_files: int) -> List[str]:
    """Extract changed file paths from a unified diff (b/ paths)."""

    paths: List[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            if path != "/dev/null" and path not in paths:
                paths.append(path)
                if len(paths) >= max_files:
                    break
    return paths


def get_codebase_context_for_pr(
    sample: Sample,
    ground_truth_diff: str,
    max_files: int = 20,
    max_bytes: int = 200_000,
    cache_dir: Optional[Path] = None,
) -> Tuple[Dict[str, str], List[str]]:
    """Load contents of changed files at the base commit for additional context.

    Returns a mapping of relative file paths to file contents, plus the list of
    included paths (for metadata).
    """

    changed_files = _extract_changed_files_from_diff(ground_truth_diff, max_files)
    if not changed_files:
        return {}, []

    context: Dict[str, str] = {}
    selected: List[str] = []
    total_bytes = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        _ = materialize_workspace(sample, workspace, cache_dir)

        for rel_path in changed_files:
            file_path = workspace / rel_path
            if not file_path.is_file():
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            encoded = content.encode("utf-8")
            if total_bytes + len(encoded) > max_bytes:
                remaining = max_bytes - total_bytes
                if remaining <= 0:
                    break
                encoded = encoded[:remaining]
                content = encoded.decode("utf-8", errors="ignore")

            context[rel_path] = content
            selected.append(rel_path)
            total_bytes += len(encoded)

            if total_bytes >= max_bytes:
                break

    return context, selected


def _truncate(text: str, max_chars: int = 8000) -> str:
    """Truncate long text for prompts."""

    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated] ..."




def _load_agent_stdout_from_logs(logs_path: Path) -> str:
    """Load stdout from the last agent_run event in a logs.jsonl file."""

    if not logs_path.is_file():
        return ""

    last_stdout = ""
    with open(logs_path) as f:
        for line in f:
            try:
                record = json.loads(line)
            except Exception:
                continue
            if record.get("event") == "agent_run":
                last_stdout = str(record.get("stdout", ""))
    return last_stdout


def _parse_agent_judge_output(stdout: str) -> dict:
    """Best-effort extraction of a JSON object from agent stdout.

    Agents typically emit a long, chatty transcript with a final JSON code block
    containing the decision. This helper tries several strategies, from most to
    least specific, to recover that JSON.
    """

    content = stdout.strip()
    if not content:
        raise ValueError("Empty stdout from judge runner")

    # 1) Some runners emit pure JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2) Extract JSON from markdown code blocks, preferring the last block which
    # is usually the final answer.
    #
    # There are two common patterns we need to handle:
    #   a) Classic multi-line markdown fences:
    #        ```json\n{...}\n```
    #   b) Runners like claude-code that log their own JSON envelope where the
    #      assistant's markdown response (including ```json code blocks) appears
    #      inside a larger JSON string on a single line. In that case the
    #      content between fences is itself JSON-escaped.
    if "```" in content:
        inline_snippets: List[str] = []

        # 2a) First look for inline ```...``` segments that live on a single
        #     line (common in structured logs).
        for line in content.splitlines():
            if "```" not in line:
                continue
            start = 0
            while True:
                open_idx = line.find("```", start)
                if open_idx == -1:
                    break
                close_idx = line.find("```", open_idx + 3)
                if close_idx == -1:
                    break
                snippet = line[open_idx + 3 : close_idx].strip()
                if snippet:
                    inline_snippets.append(snippet)
                start = close_idx + 3

        # Try inline snippets from last to first
        for snippet in reversed(inline_snippets):
            cand = snippet.strip()
            if not cand:
                continue
            # Drop optional language tag like "json"
            if cand.lower().startswith("json"):
                cand = cand[4:].lstrip()
            # First try as-is
            try:
                return json.loads(cand)
            except json.JSONDecodeError:
                # Then try interpreting backslash escapes inside the snippet,
                # which is what we get when the JSON block itself has been
                # JSON-encoded into a log line.
                try:
                    decoded = cand.encode("utf-8").decode("unicode_escape")
                    return json.loads(decoded)
                except Exception:
                    pass

        # 2b) Fall back to classic multi-line fenced blocks.
        blocks: List[str] = []
        in_block = False
        current: List[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                if in_block:
                    blocks.append("\n".join(current).strip())
                    current = []
                    in_block = False
                else:
                    in_block = True
                continue
            if in_block:
                current.append(line)

        if current:
            blocks.append("\n".join(current).strip())

        for block in reversed(blocks):
            cand = block.strip()
            if not cand:
                continue
            if cand.lower().startswith("json"):
                cand = cand[4:].lstrip()
            try:
                return json.loads(cand)
            except json.JSONDecodeError:
                try:
                    decoded = cand.encode("utf-8").decode("unicode_escape")
                    return json.loads(decoded)
                except Exception:
                    continue

        # If we saw any fenced regions at all, restrict subsequent heuristics
        # to their combined content rather than the full transcript.
        if inline_snippets or blocks:
            content = "\n".join(blocks or inline_snippets)

    # 3) Fallback: search for the first brace-delimited JSON object that parses.
    # This handles cases where multiple JSON objects or extra text are present
    # in the same stream.
    text = content
    length = len(text)
    idx = 0
    while idx < length:
        if text[idx] != "{":
            idx += 1
            continue
        end = idx + 1
        while end < length:
            if text[end] == "}":
                candidate = text[idx : end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # keep searching for a later closing brace
                    pass
            end += 1
        idx += 1

    raise ValueError("Could not parse JSON from judge runner stdout")


def _load_cross_agent_results_for_pr(
    pr_number: int,
    output_dir: Path,
    test_label: Optional[str],
    judge_model: str,
) -> Dict[str, AgentResult]:
    """Load AgentResult entries from an existing CrossAgentJudge artifact.

    Returns a mapping from agent_id (runner:model:edit_run_id) to AgentResult.
    If no suitable artifact is found, returns an empty dict.
    """

    ca_dir = output_dir / "cross_agent_analysis"
    if not ca_dir.exists():
        return {}

    # Prefer artifacts that match both test_label and judge_model
    for ca_file in sorted(ca_dir.glob(f"pr{pr_number}_*.json")):
        try:
            with open(ca_file) as f:
                data = json.load(f)
            ca = CrossAgentJudge(**data)
        except Exception:
            continue

        if test_label is not None and ca.test_label != test_label:
            continue
        if ca.judge_model is not None and ca.judge_model != judge_model:
            continue

        result: Dict[str, AgentResult] = {}
        for ar in ca.agent_results:
            agent_id = f"{ar.runner}:{ar.model}:{ar.edit_run_id}"
            result[agent_id] = ar
        return result

    return {}


def run_agent_vs_human_judge(
    sample: Sample,
    judge_runner: str,
    judge_runner_model: Optional[str],
    edit: Edit,
    agent_id: str,
    ground_truth_diff: str,
    output_dir: Path,
    head_to_head_run_id: str,
    codebase_context: Optional[Dict[str, str]] = None,
    codebase_context_paths: Optional[List[str]] = None,
    cache_dir: Optional[Path] = None,
) -> AgentVsHumanDecision:
    """Use a CLI agent as judge to evaluate a single submission against human diff.

    judge_runner_model is the model string passed through to the CLI judge runner
    (e.g., "claude-sonnet-4.5"). It is also recorded on the resulting
    AgentVsHumanDecision.judge_model field for traceability.
    """

    console = Console()

    # Build codebase context block (optional)
    context_block = ""
    if codebase_context:
        parts = []
        for path, content in codebase_context.items():
            parts.append(f"### {path}\n```\n{_truncate(content, 2000)}\n```")
        context_block = "\n**Codebase Context (Base Commit):**\n" + "\n\n".join(parts)

    prompt = f"""You are an expert code reviewer acting as an automated judge evaluating an AI coding
agent's diff against the HUMAN ground truth diff for a GitHub pull request task.

You are in a read-only evaluation mode:
- Do NOT modify any files.
- Do NOT run git push or create new branches.
- Your job is only to evaluate how well the AI submission matches the HUMAN ground truth diff.

You have a materialized workspace at the PR's base commit. To inspect the FULL
diffs, open these files in the workspace:
- HUMAN.diff          (ground truth / human reference diff)
- AGENT.diff          (AI agent's submission to evaluate)

You may also inspect other files in the workspace if that helps you reason, but
you must not make any edits.

Task Instructions:
{sample.task_instructions}

Human Ground Truth Diff (excerpt):
```diff
{_truncate(ground_truth_diff, 8000)}
```
{context_block}

Agent Submission Diff (excerpt):
```diff
{_truncate(edit.patch_unified, 8000)}
```

Your goal is to evaluate how well the agent's submission matches the HUMAN diff
while satisfying the task instructions. Evaluate on these metrics:

Score interpretation: -1 = much worse than human, 0 = human level (ground truth), 1 = better than human

1. **correctness** (-1.0 to 1.0): Does it implement the right behavior?
   - 1.0: Better than ground truth (e.g., fixes additional bugs, more robust)
   - 0.0: Matches ground truth quality (human level)
   - -1.0: Much worse than ground truth (incorrect or breaks functionality)

2. **completeness** (-1.0 to 1.0): Does it cover all important changes?
   - 1.0: Better than ground truth (includes all changes plus beneficial extras)
   - 0.0: Matches ground truth (human level completeness)
   - -1.0: Much worse than ground truth (missing critical functionality)

3. **code_reuse** (-1.0 to 1.0): Does it reuse existing helpers/patterns appropriately?
   - 1.0: Better than ground truth (superior reuse, less duplication)
   - 0.0: Matches ground truth quality (human level)
   - -1.0: Much worse than ground truth (unnecessary duplication)

4. **best_practices** (-1.0 to 1.0): Readability, maintainability, safety
   - 1.0: Better than ground truth (superior practices)
   - 0.0: Matches ground truth quality (human level)
   - -1.0: Much worse than ground truth (poor practices)

5. **unsolicited_docs** (-1.0 to 1.0): Penalizes documentation added when not requested
   - 1.0: Better than ground truth (no unsolicited documentation)
   - 0.0: Matches ground truth (human level)
   - -1.0: Much worse than ground truth (significant unsolicited documentation)

6. **matches_human** (0.0 to 1.0): Overall similarity to human diff
   - 1.0: Nearly identical to human approach
   - 0.5: Different approach but equivalent
   - 0.0: Completely different or wrong

Respond with ONLY a valid JSON object in this exact format (no markdown, no
code blocks, no additional text before or after):

{{
  "correctness": <float -1.0 to 1.0>,
  "completeness": <float -1.0 to 1.0>,
  "code_reuse": <float -1.0 to 1.0>,
  "best_practices": <float -1.0 to 1.0>,
  "unsolicited_docs": <float -1.0 to 1.0>,
  "matches_human": <float 0.0 to 1.0>,
  "rationale": "<brief explanation of your evaluation>",
  "notes": "<short notes about how the submission compares to the human diff>"
}}"""

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir) / "workspace"
            _ = materialize_workspace(sample, workspace_path, cache_dir)

            # Write full diff files for the judge to inspect.
            (workspace_path / "HUMAN.diff").write_text(ground_truth_diff or "", encoding="utf-8")
            (workspace_path / "AGENT.diff").write_text(
                edit.patch_unified or "", encoding="utf-8"
            )

            logs_dir = output_dir / "head_to_head" / "logs" / f"pr{sample.pr_number}_{head_to_head_run_id}"
            logs_dir.mkdir(parents=True, exist_ok=True)
            logs_hash = hashlib.sha256(
                f"{agent_id}|{judge_runner}".encode("utf-8")
            ).hexdigest()[:8]
            logs_path = logs_dir / f"{judge_runner}_{logs_hash}.jsonl"

            adapter = get_runner_adapter(
                judge_runner,
                model=judge_runner_model or "",
                agent_binary=None,
                timeout=1800,
                disable_retrieval=False,
                disable_shell=False,
                enable_mcp_codebase_qa=False,
                stream_output=False,
            )
            result = adapter.run(
                workspace_path=workspace_path,
                task_instructions=prompt,
                logs_path=logs_path,
                env=os.environ.copy(),
            )

            if result.status != "success":
                raise RuntimeError(f"Judge runner exited with status {result.status}")

            stdout = _load_agent_stdout_from_logs(logs_path)
            if not stdout.strip():
                raise RuntimeError("No stdout captured from judge runner")

            raw = _parse_agent_judge_output(stdout)

    except Exception as e:
        console.print(f"[yellow]Warning: Agent judge {judge_runner} failed: {e}[/yellow]")
        return AgentVsHumanDecision(
            repo_url=sample.repo_url,
            pr_number=sample.pr_number,
            agent_id=agent_id,
            judge_model=judge_runner_model,
            judge_runner=judge_runner,
            correctness=0.0,
            completeness=0.0,
            code_reuse=0.0,
            best_practices=0.0,
            unsolicited_docs=0.0,
            matches_human=0.0,
            aggregate=0.0,
            rationale=f"Agent judge {judge_runner} failed: {e}",
            notes=None,
            timestamp=datetime.utcnow().isoformat(),
            codebase_context_files=codebase_context_paths,
        )

    # Extract scores from the judge's response
    try:
        correctness = max(-1.0, min(1.0, float(raw.get("correctness", 0.0))))
        completeness = max(-1.0, min(1.0, float(raw.get("completeness", 0.0))))
        code_reuse = max(-1.0, min(1.0, float(raw.get("code_reuse", 0.0))))
        best_practices = max(-1.0, min(1.0, float(raw.get("best_practices", 0.0))))
        unsolicited_docs = max(-1.0, min(1.0, float(raw.get("unsolicited_docs", 1.0))))
        matches_human = max(0.0, min(1.0, float(raw.get("matches_human", 0.0))))
    except (TypeError, ValueError) as e:
        console.print(f"[yellow]Warning: Failed to parse scores: {e}[/yellow]")
        correctness = completeness = code_reuse = best_practices = 0.0
        unsolicited_docs = 1.0
        matches_human = 0.0

    # Calculate aggregate score (average of the 5 main metrics)
    aggregate = (correctness + completeness + code_reuse + best_practices + unsolicited_docs) / 5.0

    return AgentVsHumanDecision(
        repo_url=sample.repo_url,
        pr_number=sample.pr_number,
        agent_id=agent_id,
        judge_model=judge_runner_model,
        judge_runner=judge_runner,
        correctness=correctness,
        completeness=completeness,
        code_reuse=code_reuse,
        best_practices=best_practices,
        unsolicited_docs=unsolicited_docs,
        matches_human=matches_human,
        aggregate=aggregate,
        rationale=raw.get("rationale"),
        notes=raw.get("notes"),
        timestamp=datetime.utcnow().isoformat(),
        codebase_context_files=codebase_context_paths,
    )


def run_head_to_head_for_pr(
    pr_number: int,
    output_dir: Path,
    judge_model: str,
    include_codebase_context: bool = False,
    test_label: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    force: bool = False,
    judge_runner: str = "claude-code",
    judge_runner_model: str = "claude-sonnet-4-5",
) -> Optional[str]:
    """Run head-to-head judging for a single PR.

    Returns the head-to-head run ID, or None if no result was produced.
    """

    head_to_head_run_id = str(uuid.uuid4())[:8]
    console.print(
        f"[bold]Starting head-to-head run {head_to_head_run_id} for PR {pr_number} "
        f"(pairwise judge: {judge_runner}/{judge_runner_model}, scalar scores from {judge_model})[/bold]"
    )

    # Resolve sample
    samples_dir = output_dir / "samples"
    if not samples_dir.exists():
        console.print(f"[red]Samples directory not found: {samples_dir}[/red]")
        return None

    sample_file: Optional[Path] = None
    for candidate in samples_dir.rglob("sample.json"):
        sample = load_sample(candidate)
        if sample.pr_number == pr_number:
            sample_file = candidate
            break
    if not sample_file:
        console.print(f"[red]Sample not found for PR {pr_number}[/red]")
        return None

    sample = load_sample(sample_file)
    console.print(f"  Repo: {sample.repo_url}")

    # Check for existing result
    h2h_dir = output_dir / "head_to_head"
    if not force and h2h_dir.exists():
        existing = list(h2h_dir.glob(f"pr{pr_number}_*.json"))
        if existing:
            console.print(
                f"[yellow]⊙ Skipping PR {pr_number} (head-to-head result already exists: {existing[0].name})[/yellow]"
            )
            return None

    # Find edits
    edits = find_edits_for_pr(pr_number, sample.repo_url, output_dir, test_label)
    if len(edits) < 2:
        console.print(f"[yellow]Need at least 2 agents for head-to-head (found {len(edits)})[/yellow]")
        return None

    console.print(f"  Found {len(edits)} agent submissions")

    # Ground truth diff
    console.print("  Fetching ground truth diff...")
    ground_truth_diff = get_ground_truth_diff(sample, cache_dir)

    console.print(f"  Judge runner: {judge_runner} (model={judge_runner_model})")
    console.print(f"  Judging each agent individually against human diff")

    # Build submissions list
    submissions = []
    for edit, _ in edits:
        agent_id = f"{edit.runner}:{edit.model}:{edit.edit_run_id}"
        submissions.append({
            "agent_id": agent_id,
            "edit": edit,
            "runner_model": f"{edit.runner}:{edit.model}",
        })

    # Baseline scores per submission using existing cross-agent results (if any)
    agent_results: List[AgentResult] = []
    cross_agent_results = _load_cross_agent_results_for_pr(
        pr_number=pr_number,
        output_dir=output_dir,
        test_label=test_label,
        judge_model=judge_model,
    )
    if cross_agent_results:
        console.print(f"  Loaded cross-agent scores for {len(cross_agent_results)} agent(s)")
    else:
        console.print("  No cross-agent scores found; using neutral placeholder scores")

    for sub in submissions:
        edit = sub["edit"]
        agent_id = sub["agent_id"]
        existing = cross_agent_results.get(agent_id)

        if existing is not None:
            agent_results.append(existing)
        else:
            # Neutral placeholder scores when no prior LLM judge outputs are available
            scores = Scores(
                correctness=0.0,
                completeness=0.0,
                code_reuse=0.0,
                best_practices=0.0,
                unsolicited_docs=0.0,
            )
            agent_results.append(
                AgentResult(
                    runner=edit.runner,
                    model=edit.model,
                    edit_run_id=edit.edit_run_id,
                    status=edit.status,
                    elapsed_ms=edit.elapsed_ms,
                    patch_unified=edit.patch_unified,
                    scores=scores,
                    aggregate=0.0,
                    rationale="No cross-agent LLM scores available; neutral scores used.",
                    llm_rating=None,
                    llm_summary=None,
                    errors=edit.errors,
                    logs_path=edit.logs_path,
                )
            )

    # Optional codebase context
    context: Optional[Dict[str, str]] = None
    context_paths: Optional[List[str]] = None
    if include_codebase_context:
        console.print("  Building codebase context...")
        context, context_paths = get_codebase_context_for_pr(
            sample,
            ground_truth_diff,
            max_files=20,
            max_bytes=200_000,
            cache_dir=cache_dir,
        )
        console.print(f"  Included {len(context_paths or [])} context file(s)")

    # Judge each agent individually against human diff
    agent_decisions: List[AgentVsHumanDecision] = []
    for sub in submissions:
        console.print(f"  Judging {sub['agent_id']} against human diff with judge runner {judge_runner}")
        decision = run_agent_vs_human_judge(
            sample=sample,
            judge_runner=judge_runner,
            judge_runner_model=judge_runner_model,
            edit=sub["edit"],
            agent_id=sub["agent_id"],
            ground_truth_diff=ground_truth_diff,
            output_dir=output_dir,
            head_to_head_run_id=head_to_head_run_id,
            codebase_context=context,
            codebase_context_paths=context_paths,
            cache_dir=cache_dir,
        )
        agent_decisions.append(decision)

    if not agent_decisions:
        console.print("[yellow]No agent decisions produced[/yellow]")
        return None

    # Calculate per-agent stats by comparing scores
    # For each agent, count wins/losses/ties against all other agents
    stats_map: Dict[str, Dict[str, int]] = {
        decision.agent_id: {"wins": 0, "losses": 0, "ties": 0} for decision in agent_decisions
    }

    # Create a mapping of agent_id to aggregate score for easy lookup
    score_map: Dict[str, float] = {
        decision.agent_id: decision.aggregate for decision in agent_decisions
    }

    # Compare each agent against every other agent based on scores
    for i, decision_i in enumerate(agent_decisions):
        for j, decision_j in enumerate(agent_decisions):
            if i == j:
                continue  # Don't compare agent to itself

            agent_i = decision_i.agent_id
            agent_j = decision_j.agent_id
            score_i = score_map[agent_i]
            score_j = score_map[agent_j]

            # Determine win/loss/tie based on score comparison
            # Use a small epsilon for tie detection
            if abs(score_i - score_j) < 1e-3:
                stats_map[agent_i]["ties"] += 1
            elif score_i > score_j:
                stats_map[agent_i]["wins"] += 1
            else:
                stats_map[agent_i]["losses"] += 1

    agent_stats = [
        HeadToHeadAgentStats(
            agent_id=agent_id,
            wins=vals["wins"],
            losses=vals["losses"],
            ties=vals["ties"],
        )
        for agent_id, vals in sorted(stats_map.items())
    ]

    # Assemble result and write to disk
    h2h_result = HeadToHeadPRResult(
        repo_url=sample.repo_url,
        pr_number=sample.pr_number,
        base_commit=sample.base_commit,
        head_commit=sample.head_commit,
        task_instructions=sample.task_instructions,
        test_label=test_label,
        agent_results=agent_results,
        agent_decisions=agent_decisions,
        agent_stats=agent_stats,
        pairwise_decisions=None,  # Deprecated, kept for backward compatibility
        head_to_head_run_id=head_to_head_run_id,
        timestamp=datetime.utcnow().isoformat(),
    )

    h2h_dir.mkdir(parents=True, exist_ok=True)
    output_file = h2h_dir / f"pr{pr_number}_{head_to_head_run_id}.json"
    with open(output_file, "w") as f:
        f.write(h2h_result.model_dump_json(indent=2))

    console.print(f"[green]✓ Head-to-head results written to {output_file}[/green]")
    return head_to_head_run_id

