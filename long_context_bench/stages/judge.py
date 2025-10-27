"""Judge stage: Score agent edits against ground truth."""

import json
import tempfile
from pathlib import Path
from typing import Optional
import difflib

import git
from rich.console import Console

from long_context_bench.models import Sample, Edit, Judge, Scores

console = Console()


def load_edit(edit_path: Path) -> Edit:
    """Load edit from JSON file.
    
    Args:
        edit_path: Path to edit.json
        
    Returns:
        Edit object
    """
    with open(edit_path) as f:
        data = json.load(f)
    return Edit(**data)


def get_ground_truth_diff(sample: Sample, cache_dir: Optional[Path] = None) -> str:
    """Get ground truth diff from base to head commit.

    Args:
        sample: Sample object
        cache_dir: Optional cache directory for repositories

    Returns:
        Ground truth unified diff
    """
    if cache_dir:
        # Extract repo name from URL
        repo_name = sample.repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        owner = sample.repo_url.rstrip("/").split("/")[-2]
        cache_path = cache_dir / f"{owner}_{repo_name}"

        if cache_path.exists():
            console.print(f"  Using cached repository for ground truth")
            repo = git.Repo(cache_path)
            try:
                repo.git.fetch("origin", sample.base_commit)
                repo.git.fetch("origin", sample.head_commit)
            except Exception as e:
                console.print(f"  [yellow]Warning: Failed to fetch commits: {e}[/yellow]")
        else:
            console.print(f"  Cloning repository for ground truth...")
            cache_path.mkdir(parents=True, exist_ok=True)
            repo = git.Repo.clone_from(sample.repo_url, cache_path)
            try:
                repo.git.fetch("origin", sample.base_commit)
                repo.git.fetch("origin", sample.head_commit)
            except Exception as e:
                console.print(f"  [yellow]Warning: Failed to fetch commits: {e}[/yellow]")

        diff = repo.git.diff(sample.base_commit, sample.head_commit, unified=True)
        return diff
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = git.Repo.clone_from(sample.repo_url, tmpdir)
            repo.git.fetch("origin", sample.base_commit)
            repo.git.fetch("origin", sample.head_commit)

            diff = repo.git.diff(sample.base_commit, sample.head_commit, unified=True)
            return diff


def compute_deterministic_scores(agent_diff: str, ground_truth_diff: str) -> Scores:
    """Compute deterministic scores based on diff comparison.
    
    Per R-3.12: Deterministic baseline judge using exact-match/overlap heuristics.
    
    Args:
        agent_diff: Agent-produced diff
        ground_truth_diff: Ground truth diff
        
    Returns:
        Scores object
    """
    # Normalize diffs (remove whitespace variations)
    agent_lines = [line.strip() for line in agent_diff.split("\n") if line.strip()]
    gt_lines = [line.strip() for line in ground_truth_diff.split("\n") if line.strip()]
    
    # Exact match
    if agent_diff.strip() == ground_truth_diff.strip():
        return Scores(
            correctness=1.0,
            completeness=1.0,
            code_reuse=1.0,
            best_practices=1.0,
            unsolicited_docs=1.0,
        )
    
    # Empty agent diff
    if not agent_lines:
        return Scores(
            correctness=-1.0,
            completeness=-1.0,
            code_reuse=0.0,
            best_practices=0.0,
            unsolicited_docs=1.0,
        )
    
    # Compute similarity using SequenceMatcher
    matcher = difflib.SequenceMatcher(None, agent_lines, gt_lines)
    similarity = matcher.ratio()
    
    # Compute line overlap
    agent_set = set(agent_lines)
    gt_set = set(gt_lines)
    
    if gt_set:
        overlap = len(agent_set & gt_set) / len(gt_set)
    else:
        overlap = 0.0
    
    # Heuristic scoring
    # Correctness: Based on similarity
    correctness = 2 * similarity - 1  # Map [0, 1] to [-1, 1]
    
    # Completeness: Based on overlap
    completeness = 2 * overlap - 1
    
    # Code reuse: Penalize if agent diff is much larger than ground truth
    if gt_lines:
        size_ratio = len(agent_lines) / len(gt_lines)
        if size_ratio > 2.0:
            code_reuse = -0.5
        elif size_ratio > 1.5:
            code_reuse = 0.0
        else:
            code_reuse = 0.5
    else:
        code_reuse = 0.0
    
    # Best practices: Neutral for deterministic judge
    best_practices = 0.0
    
    # Unsolicited docs: Check for documentation patterns
    doc_patterns = ["README", "CHANGELOG", "TODO", "# Documentation", "## Documentation"]
    has_unsolicited_docs = any(pattern in agent_diff for pattern in doc_patterns)
    unsolicited_docs = -0.5 if has_unsolicited_docs else 1.0
    
    return Scores(
        correctness=max(-1.0, min(1.0, correctness)),
        completeness=max(-1.0, min(1.0, completeness)),
        code_reuse=max(-1.0, min(1.0, code_reuse)),
        best_practices=max(-1.0, min(1.0, best_practices)),
        unsolicited_docs=max(-1.0, min(1.0, unsolicited_docs)),
    )


def compute_llm_scores(
    agent_diff: str,
    ground_truth_diff: str,
    task_instructions: str,
    judge_model: str,
) -> tuple[Scores, str]:
    """Compute scores using LLM judge.
    
    Per R-3.12: LLM-based judge with temperature 0.0, top_p 0, fixed prompt and seed.
    
    Args:
        agent_diff: Agent-produced diff
        ground_truth_diff: Ground truth diff
        task_instructions: Task instructions
        judge_model: Judge model name
        
    Returns:
        Tuple of (Scores, rationale)
    """
    # TODO: Implement LLM judge
    # For now, fall back to deterministic
    console.print("[yellow]LLM judge not yet implemented, using deterministic[/yellow]")
    scores = compute_deterministic_scores(agent_diff, ground_truth_diff)
    rationale = "LLM judge not yet implemented"
    return scores, rationale


def judge_edit(
    sample: Sample,
    edit: Edit,
    judge_mode: str,
    judge_model: Optional[str],
    output_dir: Path,
    run_id: str,
    cache_dir: Optional[Path] = None,
) -> Judge:
    """Judge a single edit.

    Args:
        sample: Sample object
        edit: Edit object
        judge_mode: Judge mode (deterministic|llm)
        judge_model: Optional judge model
        output_dir: Output directory
        run_id: Run ID
        cache_dir: Optional cache directory for repositories

    Returns:
        Judge object
    """
    pr_id = f"{sample.repo_url.split('/')[-2]}_{sample.repo_url.split('/')[-1].replace('.git', '')}_pr{sample.pr_number}"

    console.print(f"[cyan]Judging {pr_id}...[/cyan]")

    # Create output directory
    judge_dir = output_dir / judge_mode / (judge_model or "default") / run_id / pr_id
    judge_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Get ground truth diff
        console.print(f"  Fetching ground truth diff...")
        ground_truth_diff = get_ground_truth_diff(sample, cache_dir)
        
        # Compute scores
        console.print(f"  Computing scores...")
        if judge_mode == "llm" and judge_model:
            scores, rationale = compute_llm_scores(
                edit.patch_unified,
                ground_truth_diff,
                sample.task_instructions,
                judge_model,
            )
        else:
            scores = compute_deterministic_scores(edit.patch_unified, ground_truth_diff)
            rationale = None
        
        # Compute aggregate score
        aggregate = (
            scores.correctness +
            scores.completeness +
            scores.code_reuse +
            scores.best_practices +
            scores.unsolicited_docs
        ) / 5.0
        
        # Create judge artifact
        judge = Judge(
            repo_url=sample.repo_url,
            pr_number=sample.pr_number,
            base_commit=sample.base_commit,
            head_commit=sample.head_commit,
            judge_mode=judge_mode,
            judge_model=judge_model,
            scores=scores,
            aggregate=aggregate,
            rationale=rationale,
        )
        
        # Write judge.json
        judge_file = judge_dir / "judge.json"
        with open(judge_file, "w") as f:
            f.write(judge.model_dump_json(indent=2))
        
        console.print(f"[green]✓ Judged {pr_id} (aggregate: {aggregate:.2f})[/green]")
        return judge
        
    except Exception as e:
        console.print(f"[red]✗ Judge failed for {pr_id}: {e}[/red]")
        
        # Create error judge artifact with neutral scores
        judge = Judge(
            repo_url=sample.repo_url,
            pr_number=sample.pr_number,
            base_commit=sample.base_commit,
            head_commit=sample.head_commit,
            judge_mode=judge_mode,
            judge_model=judge_model,
            scores=Scores(
                correctness=0.0,
                completeness=0.0,
                code_reuse=0.0,
                best_practices=0.0,
                unsolicited_docs=0.0,
            ),
            aggregate=0.0,
            rationale=f"Error: {str(e)}",
        )
        
        judge_file = judge_dir / "judge.json"
        with open(judge_file, "w") as f:
            f.write(judge.model_dump_json(indent=2))
        
        return judge


def load_sample(sample_path: Path) -> Sample:
    """Load sample from JSON file.

    Args:
        sample_path: Path to sample.json

    Returns:
        Sample object
    """
    with open(sample_path) as f:
        data = json.load(f)
    return Sample(**data)


def run_judge_stage(
    sample_path: Path,
    edit_path: Path,
    judge_mode: str,
    judge_model: Optional[str],
    output_dir: Path,
) -> None:
    """Run the judge stage.

    Args:
        sample_path: Path to sample.json or directory of samples
        edit_path: Path to edit.json or directory of edits
        judge_mode: Judge mode
        judge_model: Optional judge model
        output_dir: Output directory
    """
    import uuid

    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())[:8]

    # Load sample and edit
    if sample_path.is_file() and edit_path.is_file():
        sample = load_sample(sample_path)
        edit = load_edit(edit_path)

        judge_edit(sample, edit, judge_mode, judge_model, output_dir, run_id)
    else:
        console.print("[red]Directory-based judging not yet implemented[/red]")

    console.print(f"\n[bold]Judge stage complete[/bold]")

