"""Judge stage: Score agent edits against ground truth."""

import json
import os
import platform
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional, List

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
    # Construct the judge prompt (keep output schema the same, strengthen guidance)
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

**Evaluation Criteria (scores between -1.0 and 1.0):**

1. **Correctness**: Does the agent's change implement the intended behavior correctly?
   - 1.0: Perfectly correct, matches ground truth semantics
   - 0.0: Partially correct or neutral
   - -1.0: Incorrect or breaks functionality

2. **Completeness**: Does the agent achieve all requested changes?
   - 1.0: All changes from ground truth are present
   - 0.0: Some changes present, some missing
   - -1.0: Most or all changes missing

3. **Code Reuse**: Does the agent leverage existing code appropriately?
   - 1.0: Excellent reuse, minimal duplication
   - 0.0: Neutral, some duplication
   - -1.0: Excessive duplication or unnecessary code

4. **Best Practices**: Does the code follow style, structure, and idiomatic patterns?
   - 1.0: Excellent style and practices
   - 0.0: Acceptable or neutral
   - -1.0: Poor style, anti-patterns

5. **Unsolicited Documentation**: Penalizes documentation added when not requested.
   - 1.0: No unsolicited documentation
   - 0.0: Minor documentation additions
   - -1.0: Significant unsolicited documentation (README, CHANGELOG, etc.)

**Guidelines:**
- Judge strictly against the task instructions and the ground truth diff; do not reward extra or unrelated changes.
- Analyze the full diff before deciding; call out critical correctness or omission issues explicitly in rationale.
- Penalize added files or markdown/commentary not requested by the task (unsolicited docs metric).
- Favor minimal, targeted changes over broad refactors unless clearly required by the task.
- Avoid hallucinating behavior or files not present in the diffs; base all reasoning on the provided changes.
- Keep output to the exact JSON schema below — no markdown, no code fences, no extra text.

**Rating Calculation (0.00 to 1.00):**
- Base score = (sum of 5 metrics + 5) / 10  (maps -1..1 to 0..1)
- Apply penalties:
  - Critical errors (breaks functionality, deletes required code): -0.3 to -0.5
  - Major omissions (missing core functionality): -0.2 to -0.3
  - Minor issues (style, incomplete edge cases): -0.05 to -0.1
- Final rating = max(0.0, min(1.0, base_score - penalties))

**Summary Guidelines:**
- One sentence; state what the agent DID, name the main files/functions touched, and note key differences from ground truth.
- Use concrete technical terms; avoid vague language.

**Output Format (JSON only, no markdown):**
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
        # Determine if we should use Claude CLI or litellm
        use_claude_cli = judge_model in ["claude-sonnet-4-5", "sonnet", "claude-sonnet-4"]

        if use_claude_cli:
            # Use Claude CLI for subscription-based auth
            console.print(f"  [dim]Using Claude CLI for judging...[/dim]")

            # Call Claude CLI with the prompt
            cmd = [
                "claude",
                "-p",  # Print mode (non-interactive)
                prompt,
                "--output-format", "stream-json",
                "--verbose",
            ]

            # Add model if not using alias
            if judge_model not in ["sonnet", "opus", "haiku"]:
                cmd.extend(["--model", judge_model])

            # Run Claude CLI
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout for judge
            )

            if result.returncode != 0:
                error_msg = f"Claude CLI failed with code {result.returncode}"
                if result.stderr:
                    error_msg += f"\nstderr: {result.stderr}"
                if result.stdout:
                    error_msg += f"\nstdout: {result.stdout}"
                raise Exception(error_msg)

            # Parse stream-json output
            # Claude CLI outputs JSONL with events, we want the assistant message content
            content = None
            lines = [line for line in result.stdout.split('\n') if line.strip()]
            for line in lines:
                try:
                    event = json.loads(line)
                    # Look for assistant message with content
                    if event.get('type') == 'assistant' and 'message' in event:
                        message = event['message']
                        if 'content' in message and isinstance(message['content'], list):
                            # Extract text from content blocks
                            text_parts = []
                            for block in message['content']:
                                if block.get('type') == 'text' and 'text' in block:
                                    text_parts.append(block['text'])
                            if text_parts:
                                content = ''.join(text_parts)
                                break
                    # Also check for result type with result field
                    elif event.get('type') == 'result' and 'result' in event:
                        content = event['result']
                        break
                except json.JSONDecodeError:
                    continue

            # If we couldn't parse stream-json, use raw stdout as fallback
            if not content:
                content = result.stdout.strip()
        else:
            # Use litellm for other models
            console.print(f"  [dim]Using litellm for judging...[/dim]")
            litellm.drop_params = True  # Drop unsupported params instead of erroring
            response = litellm.completion(
                model=judge_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                seed=42,  # Fixed seed for reproducibility (dropped if unsupported)
            )
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
        # Return zero scores on failure
        scores = Scores(
            correctness=0.0,
            completeness=0.0,
            code_reuse=0.0,
            best_practices=0.0,
            unsolicited_docs=0.0,
        )
        rationale = f"LLM judge failed (JSON parse error): {str(e)}"
        rating = 0.0
        summary = "LLM judge failed"
        return scores, rationale, rating, summary

    except Exception as e:
        console.print(f"[yellow]Warning: LLM judge failed: {e}[/yellow]")
        # Return zero scores on failure
        scores = Scores(
            correctness=0.0,
            completeness=0.0,
            code_reuse=0.0,
            best_practices=0.0,
            unsolicited_docs=0.0,
        )
        rationale = f"LLM judge failed: {str(e)}"
        rating = 0.0
        summary = "LLM judge failed"
        return scores, rationale, rating, summary


def judge_edit(
    sample: Sample,
    edit: Edit,
    judge_model: str,
    output_dir: Path,
    judge_run_id: str,
    cache_dir: Optional[Path] = None,
    force: bool = False,
    test_label: Optional[str] = None,
) -> Judge:
    """Judge a single edit using LLM.

    Args:
        sample: Sample object
        edit: Edit object
        judge_model: Judge model (required)
        output_dir: Output directory
        judge_run_id: Judge run ID
        cache_dir: Optional cache directory for repositories
        force: If True, re-judge even if judge.json already exists
        test_label: Optional test label for grouping runs

    Returns:
        Judge object
    """
    pr_id = f"{sample.repo_url.split('/')[-2]}_{sample.repo_url.split('/')[-1].replace('.git', '')}_pr{sample.pr_number}"

    # Create output directory (always use "llm" subdirectory)
    judge_dir = output_dir / "llm" / judge_model / judge_run_id / pr_id
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
        # Check in staged mode (judge_run_manifest.json in llm/model/run_id/)
        judge_mode_dir = output_dir / "llm" / judge_model
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
                        if manifest.test_label == test_label:
                            # Check if this PR was judged in that run
                            other_judge_file = output_dir / "llm" / judge_model / other_run_dir.name / pr_id / "judge.json"
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

        # Compute scores using LLM
        console.print(f"  Computing scores with {judge_model}...")
        scores, rationale, _, _ = compute_llm_scores(
            edit.patch_unified,
            ground_truth_diff,
            sample.task_instructions,
            judge_model,
        )

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
            judge_mode="llm",
            judge_model=judge_model,
            scores=scores,
            aggregate=aggregate,
            rationale=rationale,
            edit_run_id=edit.edit_run_id,
            judge_run_id=judge_run_id,
            ground_truth_patch=ground_truth_diff,
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
            judge_mode="llm",
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
            ground_truth_patch=None,  # Not available on error
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
    judge_model: str,
    output_dir: Path,
    edit_run_ids: Optional[List[str]] = None,
    test_label: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    force: bool = False,
    samples_dir: Optional[Path] = None,
    concurrency: int = 1,
    resume_judge_run_id: Optional[str] = None,
) -> str:
    """Run the judge stage using LLM.

    Args:
        sample_path: Path to sample.json or directory of samples (optional if edit_run_ids provided)
        edit_path: Path to edit.json or directory of edits (optional if edit_run_ids provided)
        judge_model: Judge model (required)
        output_dir: Output directory
        edit_run_ids: Optional list of edit run IDs to evaluate (for batch mode)
        test_label: Optional label for grouping runs for comparison
        cache_dir: Optional cache directory for repositories
        force: If True, re-judge even if judge.json already exists
        samples_dir: Optional samples directory (defaults to data/samples, falls back to output/samples)
        concurrency: Number of concurrent judge tasks (default: 1)
        resume_judge_run_id: Optional judge run ID to resume (skips already-judged PRs)

    Returns:
        Judge run ID
    """
    import uuid

    output_dir.mkdir(parents=True, exist_ok=True)

    # Use provided judge_run_id for resume, or generate new one
    if resume_judge_run_id:
        judge_run_id = resume_judge_run_id
        console.print(f"[bold]Resuming judge run {judge_run_id}[/bold]")

        # Load existing manifest to get test_label and edit_run_ids if not provided
        manifest_file = output_dir / "llm" / judge_model / judge_run_id / "judge_run_manifest.json"
        if manifest_file.exists():
            with open(manifest_file) as f:
                manifest_data = json.load(f)
                if not test_label and manifest_data.get("test_label"):
                    test_label = manifest_data["test_label"]
                    console.print(f"  Loaded test_label from manifest: {test_label}")
                if not edit_run_ids and manifest_data.get("edit_run_ids"):
                    edit_run_ids = manifest_data["edit_run_ids"]
                    console.print(f"  Loaded edit_run_ids from manifest: {edit_run_ids}")
    else:
        judge_run_id = str(uuid.uuid4())[:8]
        console.print(f"[bold]Starting judge run {judge_run_id}[/bold]")

    console.print(f"  Judge model: {judge_model}")
    console.print(f"  Concurrency: {concurrency}")
    if test_label:
        console.print(f"  Test label: {test_label}")

    # Collect edit run IDs being evaluated
    evaluated_edit_run_ids = []
    judges = []

    # Batch mode: evaluate specific edit runs
    if edit_run_ids:
        console.print(f"[bold]Evaluating {len(edit_run_ids)} edit run(s)...[/bold]")

        # Find all edits from the specified edit runs
        edits_dir = output_dir / "edits"

        # Determine samples directory
        if samples_dir is None:
            # Try data/samples first (preferred), fall back to output/samples
            data_samples = Path("data/samples")
            output_samples = output_dir / "samples"
            if data_samples.exists():
                samples_dir = data_samples
            else:
                samples_dir = output_samples

        console.print(f"  Using samples directory: {samples_dir}")

        for edit_run_id in edit_run_ids:
            console.print(f"\n[cyan]Processing edit run: {edit_run_id}[/cyan]")
            evaluated_edit_run_ids.append(edit_run_id)

            # Collect all (sample, edit) pairs to judge
            tasks = []
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
                tasks.append((sample, edit))

            console.print(f"[bold]Found {len(tasks)} edits to judge[/bold]")

            # Judge edits with concurrency
            if concurrency > 1:
                # Parallel execution
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    futures = {
                        executor.submit(
                            judge_edit,
                            sample=sample,
                            edit=edit,
                            judge_model=judge_model,
                            output_dir=output_dir,
                            judge_run_id=judge_run_id,
                            cache_dir=cache_dir,
                            force=force,
                            test_label=test_label,
                        ): (sample, edit)
                        for sample, edit in tasks
                    }

                    for future in as_completed(futures):
                        try:
                            judge = future.result()
                            judges.append(judge)
                        except Exception as e:
                            sample, edit = futures[future]
                            pr_id = f"{edit.repo_url.split('/')[-2]}_{edit.repo_url.split('/')[-1].replace('.git', '')}_pr{edit.pr_number}"
                            console.print(f"[red]✗ Failed to judge {pr_id}: {e}[/red]")
            else:
                # Sequential execution
                for sample, edit in tasks:
                    judge = judge_edit(
                        sample=sample,
                        edit=edit,
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
        judge_mode="llm",
        judge_model=judge_model,
        edit_run_ids=evaluated_edit_run_ids,
        os=platform.system(),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        timestamp=datetime.utcnow().isoformat(),
        judge_run_id=judge_run_id,
        test_label=test_label,
    )

    # Save manifest in the llm/model/run_id directory
    manifest_dir = output_dir / "llm" / judge_model / judge_run_id
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = manifest_dir / "judge_run_manifest.json"
    with open(manifest_file, "w") as f:
        f.write(manifest.model_dump_json(indent=2))

    console.print(f"\n[bold green]Judge run {judge_run_id} complete![/bold green]")
    console.print(f"  Evaluated {len(judges)} edit(s)")
    console.print(f"Results saved to: {manifest_dir}")

    return judge_run_id

