"""Judge stage: Score agent edits against ground truth."""

import json
import platform
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import difflib

import git
from rich.console import Console
import litellm

from long_context_bench import __version__
from long_context_bench.models import Sample, Edit, Judge, Scores, JudgeRunManifest, RunManifest

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
                # Shallow fetch just the required commits (no history, no tags)
                repo.git.fetch("--no-tags", "--depth=1", "origin", sample.base_commit)
                repo.git.fetch("--no-tags", "--depth=1", "origin", sample.head_commit)
            except Exception as e:
                console.print(f"  [yellow]Warning: Failed to shallow-fetch commits: {e}[/yellow]")
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
            # Shallow fetch just the required commits (no history, no tags)
            repo.git.fetch("--no-tags", "--depth=1", "origin", sample.base_commit)
            repo.git.fetch("--no-tags", "--depth=1", "origin", sample.head_commit)

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
) -> tuple[Scores, str, float, str]:
    """Compute scores using LLM judge.

    Per R-3.12: LLM-based judge with temperature 0.0, fixed prompt and seed.

    Args:
        agent_diff: Agent-produced diff
        ground_truth_diff: Ground truth diff
        task_instructions: Task instructions
        judge_model: Judge model name

    Returns:
        Tuple of (Scores, rationale, rating, summary)
        - Scores: Individual metric scores
        - rationale: Detailed explanation
        - rating: Overall rating from 0.00 to 1.00
        - summary: One-line summary
    """
    # Construct the judge prompt
    prompt = f"""You are an expert code reviewer evaluating an AI coding agent's output against ground truth.

**Task Instructions:**
{task_instructions}

**Ground Truth Diff (Expected Changes):**
```diff
{ground_truth_diff}
```

**Agent's Diff (Actual Changes):**
```diff
{agent_diff}
```

**Evaluation Criteria:**

Evaluate the agent's diff against the ground truth on the following 5 metrics. Each score must be between -1.0 and 1.0:

1. **Correctness** (-1.0 to 1.0): Does the agent's change implement the intended behavior correctly?
   - 1.0: Perfectly correct, matches ground truth semantics
   - 0.0: Partially correct or neutral
   - -1.0: Incorrect or breaks functionality

2. **Completeness** (-1.0 to 1.0): Does the agent achieve all requested changes?
   - 1.0: All changes from ground truth are present
   - 0.0: Some changes present, some missing
   - -1.0: Most or all changes missing

3. **Code Reuse** (-1.0 to 1.0): Does the agent leverage existing code appropriately?
   - 1.0: Excellent reuse, minimal duplication
   - 0.0: Neutral, some duplication
   - -1.0: Excessive duplication or unnecessary code

4. **Best Practices** (-1.0 to 1.0): Does the code follow style, structure, and idiomatic patterns?
   - 1.0: Excellent style and practices
   - 0.0: Acceptable or neutral
   - -1.0: Poor style, anti-patterns

5. **Unsolicited Documentation** (-1.0 to 1.0): Penalizes documentation added when not requested.
   - 1.0: No unsolicited documentation
   - 0.0: Minor documentation additions
   - -1.0: Significant unsolicited documentation (README, CHANGELOG, etc.)

**Rating Calculation (0.00 to 1.00):**

The rating should be an objective measure of solution quality based on this formula:
- Start with base score = (sum of 5 metrics + 5) / 10  (converts -1..1 range to 0..1)
- Apply penalties:
  - Critical errors (breaks functionality, deletes required code): -0.3 to -0.5
  - Major omissions (missing core functionality): -0.2 to -0.3
  - Minor issues (style, incomplete edge cases): -0.05 to -0.1
- Final rating = max(0.0, min(1.0, base_score - penalties))

**Summary Guidelines:**

The summary must be a single sentence that:
1. States what the agent DID (not what it failed to do)
2. Highlights the SPECIFIC approach or changes made
3. Mentions KEY DIFFERENCES from ground truth (if any)
4. Uses concrete technical terms (file names, function names, patterns)

Good example: "Renamed test file and added try-catch in RestBulkAction but used instance variable instead of local variable for randomization"
Bad example: "Agent partially implemented the changes but missed some requirements"

**Output Format:**

Respond with ONLY a valid JSON object in this exact format (no markdown, no code blocks, no additional text):

{{
  "correctness": <float between -1.0 and 1.0>,
  "completeness": <float between -1.0 and 1.0>,
  "code_reuse": <float between -1.0 and 1.0>,
  "best_practices": <float between -1.0 and 1.0>,
  "unsolicited_docs": <float between -1.0 and 1.0>,
  "rationale": "<brief explanation of your scoring>",
  "rating": <float between 0.00 and 1.00, calculated using the formula above>,
  "summary": "<one-line summary following the guidelines above>"
}}"""

    try:
        # Call LLM with deterministic settings
        # Note: Some providers (e.g., Anthropic) don't support seed parameter
        litellm.drop_params = True  # Drop unsupported params instead of erroring
        response = litellm.completion(
            model=judge_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            seed=42,  # Fixed seed for reproducibility (dropped if unsupported)
        )

        # Extract response content
        content = response.choices[0].message.content.strip()

        # Try to parse JSON from response
        # Handle cases where LLM wraps JSON in markdown code blocks
        if content.startswith("```"):
            # Extract JSON from code block
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

        # Parse JSON
        result = json.loads(content)

        # Extract scores with validation
        scores = Scores(
            correctness=max(-1.0, min(1.0, float(result.get("correctness", 0.0)))),
            completeness=max(-1.0, min(1.0, float(result.get("completeness", 0.0)))),
            code_reuse=max(-1.0, min(1.0, float(result.get("code_reuse", 0.0)))),
            best_practices=max(-1.0, min(1.0, float(result.get("best_practices", 0.0)))),
            unsolicited_docs=max(-1.0, min(1.0, float(result.get("unsolicited_docs", 1.0)))),
        )

        rationale = result.get("rationale", "No rationale provided")
        rating = max(0.0, min(1.0, float(result.get("rating", 0.5))))
        summary = result.get("summary", "No summary provided")

        console.print(f"[green]✓ LLM judge completed[/green]")
        return scores, rationale, rating, summary

    except json.JSONDecodeError as e:
        console.print(f"[yellow]Warning: Failed to parse LLM response as JSON: {e}[/yellow]")
        console.print(f"[yellow]Response content: {content[:200]}...[/yellow]")
        # Fall back to deterministic
        scores = compute_deterministic_scores(agent_diff, ground_truth_diff)
        rationale = f"LLM judge failed (JSON parse error), fell back to deterministic: {str(e)}"
        rating = 0.0
        summary = "LLM judge failed"
        return scores, rationale, rating, summary

    except Exception as e:
        console.print(f"[yellow]Warning: LLM judge failed: {e}[/yellow]")
        # Fall back to deterministic
        scores = compute_deterministic_scores(agent_diff, ground_truth_diff)
        rationale = f"LLM judge failed, fell back to deterministic: {str(e)}"
        rating = 0.0
        summary = "LLM judge failed"
        return scores, rationale, rating, summary


def judge_edit(
    sample: Sample,
    edit: Edit,
    judge_mode: str,
    judge_model: Optional[str],
    output_dir: Path,
    judge_run_id: str,
    cache_dir: Optional[Path] = None,
    force: bool = False,
    test_label: Optional[str] = None,
) -> Judge:
    """Judge a single edit.

    Args:
        sample: Sample object
        edit: Edit object
        judge_mode: Judge mode (deterministic|llm)
        judge_model: Optional judge model
        output_dir: Output directory
        judge_run_id: Judge run ID
        cache_dir: Optional cache directory for repositories
        force: If True, re-judge even if judge.json already exists
        test_label: Optional test label for grouping runs

    Returns:
        Judge object
    """
    pr_id = f"{sample.repo_url.split('/')[-2]}_{sample.repo_url.split('/')[-1].replace('.git', '')}_pr{sample.pr_number}"

    # Create output directory
    judge_dir = output_dir / judge_mode / (judge_model or "default") / judge_run_id / pr_id
    judge_dir.mkdir(parents=True, exist_ok=True)

    # Check if judge already exists (current run)
    judge_file = judge_dir / "judge.json"

    if judge_file.exists() and not force:
        console.print(f"[yellow]⊙ Skipping {pr_id} (already judged in this run)[/yellow]")
        # Load and return existing judge
        with open(judge_file) as f:
            judge_data = json.load(f)
            return Judge(**judge_data)

    # If test_label is provided, check if this PR was already judged in any run with the same test_label
    if test_label and not force:
        # Check in staged mode (judge_run_manifest.json in judge_mode/model/run_id/)
        judge_mode_dir = output_dir / judge_mode / (judge_model or "default")
        if judge_mode_dir.exists():
            for other_run_dir in judge_mode_dir.iterdir():
                if not other_run_dir.is_dir() or other_run_dir.name == judge_run_id:
                    continue

                # Check if this run has the same test_label
                manifest_file = other_run_dir / "judge_run_manifest.json"
                if manifest_file.exists():
                    with open(manifest_file) as f:
                        manifest = JudgeRunManifest(**json.load(f))
                        if manifest.test_label == test_label:
                            # Check if this PR was judged in that run
                            other_judge_file = other_run_dir / pr_id / "judge.json"
                            if other_judge_file.exists():
                                console.print(f"[yellow]⊙ Skipping {pr_id} (already judged in run {other_run_dir.name} with test label '{test_label}')[/yellow]")
                                # Load and return existing judge
                                with open(other_judge_file) as f:
                                    judge_data = json.load(f)
                                    return Judge(**judge_data)

        # Check in pipeline mode (run_manifest.json in summaries/run_id/)
        summaries_dir = output_dir.parent / "summaries"
        if summaries_dir.exists():
            for other_run_dir in summaries_dir.iterdir():
                if not other_run_dir.is_dir() or other_run_dir.name == judge_run_id:
                    continue

                # Check if this run has the same test_label
                manifest_file = other_run_dir / "run_manifest.json"
                if manifest_file.exists():
                    with open(manifest_file) as f:
                        manifest = RunManifest(**json.load(f))
                        if manifest.test_label == test_label and manifest.judge_mode == judge_mode:
                            # Check if this PR was judged in that run
                            other_judge_file = output_dir / judge_mode / (judge_model or "default") / other_run_dir.name / pr_id / "judge.json"
                            if other_judge_file.exists():
                                console.print(f"[yellow]⊙ Skipping {pr_id} (already judged in run {other_run_dir.name} with test label '{test_label}')[/yellow]")
                                # Load and return existing judge
                                with open(other_judge_file) as f:
                                    judge_data = json.load(f)
                                    return Judge(**judge_data)

    console.print(f"[cyan]Judging {pr_id}...[/cyan]")

    try:
        # Get ground truth diff
        console.print(f"  Fetching ground truth diff...")
        ground_truth_diff = get_ground_truth_diff(sample, cache_dir)

        # Compute scores
        console.print(f"  Computing scores...")
        if judge_mode == "llm" and judge_model:
            scores, rationale, _, _ = compute_llm_scores(
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
            edit_run_id=edit.edit_run_id,
            judge_run_id=judge_run_id,
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
            edit_run_id=edit.edit_run_id,
            judge_run_id=judge_run_id,
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
    sample_path: Optional[Path],
    edit_path: Optional[Path],
    judge_mode: str,
    judge_model: Optional[str],
    output_dir: Path,
    edit_run_ids: Optional[List[str]] = None,
    test_label: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    force: bool = False,
) -> str:
    """Run the judge stage.

    Args:
        sample_path: Path to sample.json or directory of samples (optional if edit_run_ids provided)
        edit_path: Path to edit.json or directory of edits (optional if edit_run_ids provided)
        judge_mode: Judge mode
        judge_model: Optional judge model
        output_dir: Output directory
        edit_run_ids: Optional list of edit run IDs to evaluate (for batch mode)
        test_label: Optional label for grouping runs for comparison
        cache_dir: Optional cache directory for repositories
        force: If True, re-judge even if judge.json already exists

    Returns:
        Judge run ID
    """
    import uuid

    output_dir.mkdir(parents=True, exist_ok=True)
    judge_run_id = str(uuid.uuid4())[:8]

    console.print(f"[bold]Starting judge run {judge_run_id}[/bold]")
    console.print(f"  Judge mode: {judge_mode}")
    if judge_model:
        console.print(f"  Judge model: {judge_model}")
    if test_label:
        console.print(f"  Test label: {test_label}")

    # Collect edit run IDs being evaluated
    evaluated_edit_run_ids = []
    judges = []

    # Batch mode: evaluate specific edit runs
    if edit_run_ids:
        console.print(f"[bold]Evaluating {len(edit_run_ids)} edit run(s)...[/bold]")

        # Find all edits from the specified edit runs
        edits_dir = output_dir.parent / "edits"
        samples_dir = output_dir.parent / "samples"

        for edit_run_id in edit_run_ids:
            console.print(f"\n[cyan]Processing edit run: {edit_run_id}[/cyan]")
            evaluated_edit_run_ids.append(edit_run_id)

            # Find all edit.json files with this edit_run_id
            for edit_file in edits_dir.rglob("edit.json"):
                edit = load_edit(edit_file)

                if edit.edit_run_id != edit_run_id:
                    continue

                # Find corresponding sample
                pr_id = f"{edit.repo_url.split('/')[-2]}_{edit.repo_url.split('/')[-1].replace('.git', '')}_pr{edit.pr_number}"
                sample_file = samples_dir.rglob(f"*/{pr_id}/sample.json")
                sample_file = next(sample_file, None)

                if not sample_file:
                    console.print(f"[yellow]Warning: Sample not found for {pr_id}[/yellow]")
                    continue

                sample = load_sample(sample_file)

                # Judge this edit
                judge = judge_edit(
                    sample=sample,
                    edit=edit,
                    judge_mode=judge_mode,
                    judge_model=judge_model,
                    output_dir=output_dir,
                    judge_run_id=judge_run_id,
                    cache_dir=cache_dir,
                    force=force,
                    test_label=test_label,
                )
                judges.append(judge)

    # Single file mode
    elif sample_path and edit_path:
        if sample_path.is_file() and edit_path.is_file():
            sample = load_sample(sample_path)
            edit = load_edit(edit_path)

            if edit.edit_run_id:
                evaluated_edit_run_ids.append(edit.edit_run_id)

            judge = judge_edit(
                sample=sample,
                edit=edit,
                judge_mode=judge_mode,
                judge_model=judge_model,
                output_dir=output_dir,
                judge_run_id=judge_run_id,
                cache_dir=cache_dir,
                force=force,
                test_label=test_label,
            )
            judges.append(judge)
        else:
            console.print("[red]Both sample_path and edit_path must be files[/red]")
            return judge_run_id
    else:
        console.print("[red]Must provide either (sample_path and edit_path) or edit_run_ids[/red]")
        return judge_run_id

    # Create and save manifest
    manifest = JudgeRunManifest(
        harness_version=__version__,
        judge_mode=judge_mode,
        judge_model=judge_model,
        edit_run_ids=evaluated_edit_run_ids,
        os=platform.system(),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        timestamp=datetime.utcnow().isoformat(),
        judge_run_id=judge_run_id,
    )

    # Save manifest in the judge_mode/model/run_id directory
    manifest_dir = output_dir / judge_mode / (judge_model or "default") / judge_run_id
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = manifest_dir / "judge_run_manifest.json"
    with open(manifest_file, "w") as f:
        f.write(manifest.model_dump_json(indent=2))

    console.print(f"\n[bold green]Judge run {judge_run_id} complete![/bold green]")
    console.print(f"  Evaluated {len(judges)} edit(s)")
    console.print(f"Results saved to: {manifest_dir}")

    return judge_run_id

