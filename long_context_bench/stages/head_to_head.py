"""Head-to-head LLM-judge stage.

Implements pairwise comparisons between agent submissions for a single PR using a
single LLM judge model, plus per-agent scalar scores reused from prior judge runs
when available.
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

import litellm
from rich.console import Console

from long_context_bench.models import (
    Sample,
    Edit,
    Scores,
    AgentResult,
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
    if "```" in content:
        blocks: List[str] = []
        in_block = False
        current: List[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                if in_block:
                    # end current block
                    blocks.append("\n".join(current).strip())
                    current = []
                    in_block = False
                else:
                    # start new block
                    in_block = True
                continue
            if in_block:
                current.append(line)
        if current:
            blocks.append("\n".join(current).strip())

        # Try each block from last to first
        for block in reversed(blocks):
            if not block:
                continue
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue

        # If we saw blocks at all, restrict subsequent heuristics to their
        # combined content rather than the full transcript.
        if blocks:
            content = "\n".join(blocks)

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


def run_agent_pairwise_judge(
    sample: Sample,
    judge_runner: str,
    judge_model: Optional[str],
    edit_a: Edit,
    edit_b: Edit,
    submission_a_id: str,
    submission_b_id: str,
    ground_truth_diff: str,
    order_seed: int,
    output_dir: Path,
    head_to_head_run_id: str,
    codebase_context: Optional[Dict[str, str]] = None,
    codebase_context_paths: Optional[List[str]] = None,
    cache_dir: Optional[Path] = None,
) -> PairwiseJudgeDecision:
    """Use a CLI agent as judge to compare two submissions and return a decision."""

    # Build codebase context block (optional)
    context_block = ""
    if codebase_context:
        parts = []
        for path, content in codebase_context.items():
            parts.append(f"### {path}\n```\n{_truncate(content, 2000)}\n```")
        context_block = "\n**Codebase Context (Base Commit):**\n" + "\n\n".join(parts)

    prompt = f"""You are an expert code reviewer acting as an automated judge for TWO AI coding agents' diffs
for the same GitHub pull request task.

You are in a read-only evaluation mode:
- Do NOT modify any files.
- You may inspect the repository in the workspace if that helps you reason.
- Your job is only to decide which diff is better and explain why.

**Task Instructions:**
{sample.task_instructions}

**Ground Truth Diff (Expected Changes):**
```diff
{_truncate(ground_truth_diff, 8000)}
```
{context_block}

**Submission A Diff:**
```diff
{_truncate(edit_a.patch_unified, 8000)}
```

**Submission B Diff:**
```diff
{_truncate(edit_b.patch_unified, 8000)}
```

You must decide which submission better implements the task according to the
following criteria: correctness, completeness, code quality, and integration
with the existing codebase.

Respond with ONLY a valid JSON object in this exact format (no markdown, no prose before or after):

{{
  "winner": "A" | "B" | "tie",
  "correctness_preference": "A" | "B" | "tie",
  "completeness_preference": "A" | "B" | "tie",
  "code_quality_preference": "A" | "B" | "tie",
  "integration_preference": "A" | "B" | "tie",
  "rationale": "<brief explanation>",
  "raw_scores": {{
    "A": {{"correctness": <float>, "completeness": <float>, "code_quality": <float>, "integration": <float>}},
    "B": {{"correctness": <float>, "completeness": <float>, "code_quality": <float>, "integration": <float>}}
  }}
}}"""

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir) / "workspace"
            _ = materialize_workspace(sample, workspace_path, cache_dir)

            logs_dir = output_dir / "head_to_head" / "logs" / f"pr{sample.pr_number}_{head_to_head_run_id}"
            logs_dir.mkdir(parents=True, exist_ok=True)
            logs_hash = hashlib.sha256(
                f"{submission_a_id}|{submission_b_id}|{judge_runner}|{order_seed}".encode("utf-8")
            ).hexdigest()[:8]
            logs_path = logs_dir / f"{judge_runner}_{logs_hash}.jsonl"

            adapter = get_runner_adapter(
                judge_runner,
                model=judge_model or "",
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
        return PairwiseJudgeDecision(
            repo_url=sample.repo_url,
            pr_number=sample.pr_number,
            submission_a_id=submission_a_id,
            submission_b_id=submission_b_id,
            judge_model=judge_model,
            judge_runner=judge_runner,
            order_seed=order_seed,
            winner="tie",
            correctness_preference="tie",
            completeness_preference="tie",
            code_quality_preference="tie",
            integration_preference="tie",
            raw_scores=None,
            rationale=f"Agent judge {judge_runner} failed: {e}",
            timestamp=datetime.utcnow().isoformat(),
            codebase_context_files=codebase_context_paths,
        )

    winner = str(raw.get("winner", "tie")).upper()
    if winner not in {"A", "B", "TIE"}:
        winner = "TIE"

    return PairwiseJudgeDecision(
        repo_url=sample.repo_url,
        pr_number=sample.pr_number,
        submission_a_id=submission_a_id,
        submission_b_id=submission_b_id,
        judge_model=judge_model,
        judge_runner=judge_runner,
        order_seed=order_seed,
        winner="A" if winner == "A" else "B" if winner == "B" else "tie",
        correctness_preference=raw.get("correctness_preference"),
        completeness_preference=raw.get("completeness_preference"),
        code_quality_preference=raw.get("code_quality_preference"),
        integration_preference=raw.get("integration_preference"),
        raw_scores=raw.get("raw_scores"),
        rationale=raw.get("rationale"),
        timestamp=datetime.utcnow().isoformat(),
        codebase_context_files=codebase_context_paths,
    )


def run_llm_pairwise_judge(
    sample: Sample,
    judge_model: str,
    edit_a: Edit,
    edit_b: Edit,
    submission_a_id: str,
    submission_b_id: str,
    ground_truth_diff: str,
    order_seed: int,
    codebase_context: Optional[Dict[str, str]] = None,
    codebase_context_paths: Optional[List[str]] = None,
) -> PairwiseJudgeDecision:
    """Use a single LLM judge to compare two submissions and return a decision.

    The LLM sees:
    - Task instructions
    - Human ground truth diff (expected changes)
    - Submission A and B diffs
    - Optional codebase context from the base commit

    It must respond with JSON matching the schema described in the user-facing
    head-to-head judge prompt.
    """

    # Build optional codebase context block
    context_block = ""
    if codebase_context:
        parts: List[str] = []
        for path, content in codebase_context.items():
            parts.append(f"### {path}\n```\n{_truncate(content, 2000)}\n```")
        context_block = "\nOptional Codebase Context (Base Commit):\n" + "\n\n".join(parts)

    prompt = f"""You are in a read-only evaluation mode:
- Do NOT modify any files.
- Your job is only to compare the diffs and decide which AI submission is better.

Task Instructions:
{sample.task_instructions}

Human Ground Truth Diff (Expected Changes):
```diff
{_truncate(ground_truth_diff, 8000)}
```

Submission A Diff (Agent A):
```diff
{_truncate(edit_a.patch_unified, 8000)}
```

Submission B Diff (Agent B):
```diff
{_truncate(edit_b.patch_unified, 8000)}
```{context_block}

Using the human ground truth diff as the reference, decide which submission better
implements the task.

When deciding, consider at least:
- Correctness: how well each submission matches the intended behavior and the human diff.
- Completeness: how much of the required change (from the human diff) is implemented.
- Code quality: clarity, maintainability, idiomatic style.
- Unnecessary changes: penalize code that diverges from the human diff without good reason.

### Your job
1. Compare Submission A and Submission B to the human diff.
2. Choose a winner: "A", "B", or "tie" if they are roughly equivalent.
3. Briefly justify your choice, explicitly referencing how each compares to the human diff.
4. Provide simple numeric "match to human" scores for each submission between 0.0 and 1.0.

### Output format (MUST follow exactly)

Respond with ONLY a valid JSON object in this exact format (no markdown, no code blocks, no additional text):
{{
  "winner": "A" | "B" | "tie",
  "rationale": "<brief explanation referencing differences vs the human diff>",
  "comparison_to_human": {{
    "A": {{ "matches_human": <float 0.0-1.0>, "notes": "<short notes>" }},
    "B": {{ "matches_human": <float 0.0-1.0>, "notes": "<short notes>" }}
  }}
}}"""

    try:
        # Call LLM with deterministic settings
        litellm.drop_params = True  # Drop unsupported params instead of erroring
        response = litellm.completion(
            model=judge_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            seed=42,
        )

        content = response.choices[0].message.content.strip()

        # Handle markdown code fences just in case
        if content.startswith("```"):
            lines = content.split("\n")
            json_lines: List[str] = []
            in_code_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or (not line.strip().startswith("```")):
                    json_lines.append(line)
            content = "\n".join(json_lines).strip()

        result = json.loads(content)

    except json.JSONDecodeError as e:
        console.print(
            f"[yellow]Warning: Failed to parse LLM pairwise judge response as JSON: {e}[/yellow]"
        )
        console.print(f"[yellow]Response content: {content[:200]}...[/yellow]")
        return PairwiseJudgeDecision(
            repo_url=sample.repo_url,
            pr_number=sample.pr_number,
            submission_a_id=submission_a_id,
            submission_b_id=submission_b_id,
            judge_model=judge_model,
            judge_runner=None,
            order_seed=order_seed,
            winner="tie",
            correctness_preference=None,
            completeness_preference=None,
            code_quality_preference=None,
            integration_preference=None,
            raw_scores=None,
            rationale=f"LLM pairwise judge failed (JSON parse error): {str(e)}",
            timestamp=datetime.utcnow().isoformat(),
            codebase_context_files=codebase_context_paths,
        )
    except Exception as e:  # pragma: no cover - defensive
        console.print(f"[yellow]Warning: LLM pairwise judge failed: {e}[/yellow]")
        return PairwiseJudgeDecision(
            repo_url=sample.repo_url,
            pr_number=sample.pr_number,
            submission_a_id=submission_a_id,
            submission_b_id=submission_b_id,
            judge_model=judge_model,
            judge_runner=None,
            order_seed=order_seed,
            winner="tie",
            correctness_preference=None,
            completeness_preference=None,
            code_quality_preference=None,
            integration_preference=None,
            raw_scores=None,
            rationale=f"LLM pairwise judge failed: {str(e)}",
            timestamp=datetime.utcnow().isoformat(),
            codebase_context_files=codebase_context_paths,
        )

    winner = str(result.get("winner", "tie")).upper()
    if winner not in {"A", "B", "TIE"}:
        winner = "TIE"

    # Map comparison_to_human into raw_scores with numeric matches_human values
    raw_scores: Optional[Dict[str, Dict[str, float]]] = None
    comparison = result.get("comparison_to_human") or {}
    if isinstance(comparison, dict):
        scores: Dict[str, Dict[str, float]] = {}
        for side in ("A", "B"):
            side_data = comparison.get(side)
            if not isinstance(side_data, dict):
                continue
            try:
                match_val = float(side_data.get("matches_human", 0.0))
            except (TypeError, ValueError):
                match_val = 0.0
            scores[side] = {"matches_human": max(0.0, min(1.0, match_val))}
        if scores:
            raw_scores = scores

    rationale = str(
        result.get("rationale", "No rationale provided (LLM pairwise judge)")
    )

    return PairwiseJudgeDecision(
        repo_url=sample.repo_url,
        pr_number=sample.pr_number,
        submission_a_id=submission_a_id,
        submission_b_id=submission_b_id,
        judge_model=judge_model,
        judge_runner=None,
        order_seed=order_seed,
        winner="A" if winner == "A" else "B" if winner == "B" else "tie",
        correctness_preference=None,
        completeness_preference=None,
        code_quality_preference=None,
        integration_preference=None,
        raw_scores=raw_scores,
        rationale=rationale,
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
) -> Optional[str]:
    """Run head-to-head judging for a single PR.

    Returns the head-to-head run ID, or None if no result was produced.
    """

    head_to_head_run_id = str(uuid.uuid4())[:8]
    console.print(
        f"[bold]Starting head-to-head run {head_to_head_run_id} for PR {pr_number} (LLM judge: {judge_model})[/bold]"
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

    console.print("  Using single LLM judge for pairwise comparisons")
    console.print(f"  Judge model for scalar scores and pairwise decisions: {judge_model}")

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

    # Pairwise decisions using a single LLM judge
    pairwise_decisions: List[PairwiseJudgeDecision] = []
    for i in range(len(submissions)):
        for j in range(i + 1, len(submissions)):
            sub_i = submissions[i]
            sub_j = submissions[j]

            # Deterministically randomize A/B order to reduce position bias
            seed_input = f"{sub_i['agent_id']}|{sub_j['agent_id']}|{judge_model}"
            order_seed = int(hashlib.sha256(seed_input.encode("utf-8")).hexdigest()[:8], 16)
            if order_seed % 2 == 0:
                a_sub, b_sub = sub_i, sub_j
            else:
                a_sub, b_sub = sub_j, sub_i

            console.print(
                f"  Judging pair {a_sub['agent_id']} vs {b_sub['agent_id']} with LLM judge {judge_model}"
            )
            decision = run_llm_pairwise_judge(
                sample=sample,
                judge_model=judge_model,
                edit_a=a_sub["edit"],
                edit_b=b_sub["edit"],
                submission_a_id=a_sub["agent_id"],
                submission_b_id=b_sub["agent_id"],
                ground_truth_diff=ground_truth_diff,
                order_seed=order_seed,
                codebase_context=context,
                codebase_context_paths=context_paths,
            )
            pairwise_decisions.append(decision)

    if not pairwise_decisions:
        console.print("[yellow]No pairwise decisions produced[/yellow]")
        return None

    # Per-agent stats for this PR
    stats_map: Dict[str, Dict[str, int]] = {
        sub["agent_id"]: {"wins": 0, "losses": 0, "ties": 0} for sub in submissions
    }
    for decision in pairwise_decisions:
        a = decision.submission_a_id
        b = decision.submission_b_id
        stats_map.setdefault(a, {"wins": 0, "losses": 0, "ties": 0})
        stats_map.setdefault(b, {"wins": 0, "losses": 0, "ties": 0})

        if decision.winner == "A":
            stats_map[a]["wins"] += 1
            stats_map[b]["losses"] += 1
        elif decision.winner == "B":
            stats_map[a]["losses"] += 1
            stats_map[b]["wins"] += 1
        else:
            stats_map[a]["ties"] += 1
            stats_map[b]["ties"] += 1

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
        pairwise_decisions=pairwise_decisions,
        agent_stats=agent_stats,
        head_to_head_run_id=head_to_head_run_id,
        timestamp=datetime.utcnow().isoformat(),
    )

    h2h_dir.mkdir(parents=True, exist_ok=True)
    output_file = h2h_dir / f"pr{pr_number}_{head_to_head_run_id}.json"
    with open(output_file, "w") as f:
        f.write(h2h_result.model_dump_json(indent=2))

    console.print(f"[green]✓ Head-to-head results written to {output_file}[/green]")
    return head_to_head_run_id

