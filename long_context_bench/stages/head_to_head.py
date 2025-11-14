"""Head-to-head LLM judging stage.

Implements pairwise comparisons between agent submissions for a single PR.
"""

from __future__ import annotations

import json
import hashlib
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
)
from long_context_bench.stages.judge import (
    load_sample,
    get_ground_truth_diff,
    compute_llm_scores,
)
from long_context_bench.stages.cross_agent_analysis import find_edits_for_pr
from long_context_bench.stages.edit import materialize_workspace

console = Console()


def load_judge_config(config_path: Path) -> Tuple[Dict[str, str], List[str]]:
    """Load judge model mapping and neutral judges from JSON config.

    The config may either be of the form:
        {"judge_models": {"runner:model": "model-id"}, "neutral_judges": [...]}  # noqa: E501
    or a flat mapping plus optional "neutral_judges" key.
    """

    if not config_path.exists():
        raise FileNotFoundError(f"Judge config not found: {config_path}")

    with open(config_path) as f:
        data = json.load(f)

    mapping: Dict[str, str]
    neutral: List[str]

    if isinstance(data, dict) and "judge_models" in data:
        mapping = dict(data.get("judge_models", {}) or {})
        neutral = list(data.get("neutral_judges", []) or [])
    elif isinstance(data, dict):
        mapping = {k: v for k, v in data.items() if k != "neutral_judges"}
        neutral = list(data.get("neutral_judges", []) or [])
    else:
        mapping = {}
        neutral = []

    return mapping, neutral


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




def _call_llm_json(prompt: str, judge_model: str) -> dict:
    """Call LLM with deterministic settings and parse JSON response."""

    litellm.drop_params = True  # Drop unsupported params instead of erroring
    response = litellm.completion(
        model=judge_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        seed=42,
    )

    content = response.choices[0].message.content.strip()

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

    return json.loads(content)


def run_pairwise_llm_judge(
    sample: Sample,
    edit_a: Edit,
    edit_b: Edit,
    submission_a_id: str,
    submission_b_id: str,
    ground_truth_diff: str,
    judge_model: str,
    order_seed: int,
    codebase_context: Optional[Dict[str, str]] = None,
    codebase_context_paths: Optional[List[str]] = None,
) -> PairwiseJudgeDecision:
    """Run a single LLM-based pairwise judgment and return the decision model."""

    # Build codebase context block
    context_block = ""
    if codebase_context:
        parts = []
        for path, content in codebase_context.items():
            parts.append(f"### {path}\n```\n{_truncate(content, 2000)}\n```")
        context_block = "\n**Codebase Context (Base Commit):**\n" + "\n\n".join(parts)

    prompt = f"""You are an expert code reviewer comparing two AI coding agents' diffs
for the same GitHub pull request task.

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

Respond with ONLY a valid JSON object in this exact format (no prose):

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
        result = _call_llm_json(prompt, judge_model)
    except Exception as e:  # pragma: no cover - network/LLM failures
        console.print(f"[yellow]Warning: Pairwise LLM judge failed: {e}[/yellow]")
        result = {
            "winner": "tie",
            "correctness_preference": "tie",
            "completeness_preference": "tie",
            "code_quality_preference": "tie",
            "integration_preference": "tie",
            "rationale": f"LLM judge failed: {e}",
            "raw_scores": None,
        }

    winner = str(result.get("winner", "tie")).lower()
    if winner not in {"a", "b", "tie"}:
        winner = "tie"

    decision = PairwiseJudgeDecision(
        repo_url=sample.repo_url,
        pr_number=sample.pr_number,
        submission_a_id=submission_a_id,
        submission_b_id=submission_b_id,
        judge_model=judge_model,
        judge_runner=None,
        order_seed=order_seed,
        winner="A" if winner == "a" else "B" if winner == "b" else "tie",
        correctness_preference=result.get("correctness_preference"),
        completeness_preference=result.get("completeness_preference"),
        code_quality_preference=result.get("code_quality_preference"),
        integration_preference=result.get("integration_preference"),
        raw_scores=result.get("raw_scores"),
        rationale=result.get("rationale"),
        timestamp=datetime.utcnow().isoformat(),
        codebase_context_files=codebase_context_paths,
    )

    return decision


def run_head_to_head_for_pr(
    pr_number: int,
    output_dir: Path,
    judge_config_path: Path,
    include_codebase_context: bool = False,
    test_label: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    force: bool = False,
) -> Optional[str]:
    """Run head-to-head judging for a single PR.

    Returns the head-to-head run ID, or None if no result was produced.
    """

    head_to_head_run_id = str(uuid.uuid4())[:8]
    console.print(f"[bold]Starting head-to-head run {head_to_head_run_id} for PR {pr_number}[/bold]")

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

    # Load judge config
    judge_models_map, neutral_judges = load_judge_config(judge_config_path)
    console.print(f"  Loaded {len(judge_models_map)} agent judge mappings, {len(neutral_judges)} neutral judge(s)")

    # Build submissions list
    submissions = []
    for edit, _ in edits:
        agent_id = f"{edit.runner}:{edit.model}:{edit.edit_run_id}"
        submissions.append({
            "agent_id": agent_id,
            "edit": edit,
            "runner_model": f"{edit.runner}:{edit.model}",
        })

    # Optional baseline scores per submission (using first neutral judge if available)
    baseline_judge_model = neutral_judges[0] if neutral_judges else (next(iter(judge_models_map.values())) if judge_models_map else None)
    agent_results: List[AgentResult] = []

    for sub in submissions:
        edit = sub["edit"]
        if baseline_judge_model:
            console.print(f"  Scoring {edit.runner}:{edit.model} with {baseline_judge_model}...")
            scores, rationale, llm_rating, llm_summary = compute_llm_scores(
                edit.patch_unified,
                ground_truth_diff,
                sample.task_instructions,
                baseline_judge_model,
            )
            aggregate = (
                scores.correctness
                + scores.completeness
                + scores.code_reuse
                + scores.best_practices
                + scores.unsolicited_docs
            ) / 5.0
        else:
            scores = Scores(
                correctness=0.0,
                completeness=0.0,
                code_reuse=0.0,
                best_practices=0.0,
                unsolicited_docs=0.0,
            )
            rationale = None
            llm_rating = None
            llm_summary = None
            aggregate = 0.0

        agent_results.append(
            AgentResult(
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

    # Pairwise decisions
    pairwise_decisions: List[PairwiseJudgeDecision] = []
    for i in range(len(submissions)):
        for j in range(i + 1, len(submissions)):
            sub_i = submissions[i]
            sub_j = submissions[j]
            key_i = sub_i["runner_model"]
            key_j = sub_j["runner_model"]

            judge_models_for_pair: List[str] = []
            for key in (key_i, key_j):
                jm = judge_models_map.get(key)
                if jm and jm not in judge_models_for_pair:
                    judge_models_for_pair.append(jm)
            for jm in neutral_judges:
                if jm not in judge_models_for_pair:
                    judge_models_for_pair.append(jm)

            if not judge_models_for_pair:
                console.print(
                    f"[yellow]Warning: No judge models configured for pair {key_i} vs {key_j}, skipping[/yellow]"
                )
                continue

            for jm in judge_models_for_pair:
                seed_input = f"{sub_i['agent_id']}|{sub_j['agent_id']}|{jm}"
                order_seed = int(hashlib.sha256(seed_input.encode("utf-8")).hexdigest()[:8], 16)
                if order_seed % 2 == 0:
                    a_sub, b_sub = sub_i, sub_j
                else:
                    a_sub, b_sub = sub_j, sub_i

                console.print(
                    f"  Judging pair {a_sub['agent_id']} vs {b_sub['agent_id']} with {jm}"
                )
                decision = run_pairwise_llm_judge(
                    sample=sample,
                    edit_a=a_sub["edit"],
                    edit_b=b_sub["edit"],
                    submission_a_id=a_sub["agent_id"],
                    submission_b_id=b_sub["agent_id"],
                    ground_truth_diff=ground_truth_diff,
                    judge_model=jm,
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

