"""Judge stage: Score agent edits against ground truth."""

import logging
import tempfile
from pathlib import Path
from typing import Optional

import git

from long_context_bench.models import EditResult, JudgeResult, JudgeScores, Sample
from long_context_bench.utils import (
    clone_repo,
    get_pr_id,
    get_unified_diff,
    save_json,
)

logger = logging.getLogger(__name__)


class Judge:
    """Judge for scoring agent edits."""

    def __init__(
        self,
        judge_mode: str = "deterministic",
        judge_model: Optional[str] = None,
        run_id: Optional[str] = None,
    ):
        """Initialize judge.
        
        Args:
            judge_mode: Judge mode ('deterministic' or 'llm')
            judge_model: Model for LLM judge (required if mode is 'llm')
            run_id: Run identifier
        """
        self.judge_mode = judge_mode
        self.judge_model = judge_model
        self.run_id = run_id or "default"
        
        if judge_mode == "llm" and not judge_model:
            raise ValueError("judge_model is required for LLM judge mode")

    def compute_deterministic_scores(
        self,
        agent_patch: str,
        ground_truth_patch: str,
    ) -> JudgeScores:
        """Compute scores using deterministic baseline judge.
        
        This is a simple heuristic-based judge that compares patches.
        
        Args:
            agent_patch: Patch produced by agent
            ground_truth_patch: Ground truth patch from PR
            
        Returns:
            JudgeScores
        """
        # Simple heuristic: compare line overlap
        agent_lines = set(agent_patch.splitlines())
        gt_lines = set(ground_truth_patch.splitlines())
        
        if not gt_lines:
            # Empty ground truth
            if not agent_lines:
                # Both empty - perfect match
                return JudgeScores(
                    correctness=1.0,
                    completeness=1.0,
                    code_reuse=1.0,
                    best_practices=1.0,
                    unsolicited_docs=1.0,
                )
            else:
                # Agent added content when none expected
                return JudgeScores(
                    correctness=0.0,
                    completeness=-1.0,
                    code_reuse=0.0,
                    best_practices=0.0,
                    unsolicited_docs=-1.0,
                )
        
        if not agent_lines:
            # Agent produced nothing
            return JudgeScores(
                correctness=-1.0,
                completeness=-1.0,
                code_reuse=0.0,
                best_practices=0.0,
                unsolicited_docs=1.0,
            )
        
        # Compute overlap
        intersection = agent_lines & gt_lines
        union = agent_lines | gt_lines
        
        overlap_ratio = len(intersection) / len(union) if union else 0.0
        
        # Compute recall (how much of GT is covered)
        recall = len(intersection) / len(gt_lines) if gt_lines else 0.0
        
        # Compute precision (how much of agent output is in GT)
        precision = len(intersection) / len(agent_lines) if agent_lines else 0.0
        
        # Map to scores
        # Correctness: based on overlap
        correctness = 2 * overlap_ratio - 1  # Map [0, 1] to [-1, 1]
        
        # Completeness: based on recall
        completeness = 2 * recall - 1
        
        # Code reuse: neutral for deterministic judge
        code_reuse = 0.0
        
        # Best practices: based on precision (penalize extra changes)
        best_practices = 2 * precision - 1
        
        # Unsolicited docs: check for doc-like patterns in extra lines
        extra_lines = agent_lines - gt_lines
        doc_patterns = ["/**", "/*", "//", "#", '"""', "'''", "README", "CHANGELOG"]
        doc_count = sum(
            1 for line in extra_lines if any(pattern in line for pattern in doc_patterns)
        )
        
        if extra_lines:
            doc_ratio = doc_count / len(extra_lines)
            unsolicited_docs = 1.0 - 2 * doc_ratio  # Penalize docs
        else:
            unsolicited_docs = 1.0
        
        return JudgeScores(
            correctness=max(-1.0, min(1.0, correctness)),
            completeness=max(-1.0, min(1.0, completeness)),
            code_reuse=code_reuse,
            best_practices=max(-1.0, min(1.0, best_practices)),
            unsolicited_docs=max(-1.0, min(1.0, unsolicited_docs)),
        )

    def compute_llm_scores(
        self,
        agent_patch: str,
        ground_truth_patch: str,
        task_instructions: str,
    ) -> tuple[JudgeScores, str]:
        """Compute scores using LLM judge.
        
        Args:
            agent_patch: Patch produced by agent
            ground_truth_patch: Ground truth patch from PR
            task_instructions: Original task instructions
            
        Returns:
            Tuple of (JudgeScores, rationale)
        """
        # TODO: Implement LLM judge
        # This would call an LLM API with a structured prompt
        raise NotImplementedError("LLM judge not yet implemented")

    def judge_edit(
        self,
        sample: Sample,
        edit_result: EditResult,
        output_dir: Path,
    ) -> Optional[JudgeResult]:
        """Judge an agent's edit against ground truth.
        
        Args:
            sample: Original sample
            edit_result: Edit result from agent
            output_dir: Output directory for artifacts
            
        Returns:
            JudgeResult or None if judging failed
        """
        pr_id = get_pr_id(sample.repo_url, sample.pr_number)
        logger.info(f"Judging edit: {pr_id}")
        
        try:
            # Get ground truth patch
            with tempfile.TemporaryDirectory() as tmpdir:
                repo_path = Path(tmpdir) / "repo"
                logger.info(f"Cloning repository to {repo_path}")
                
                repo = clone_repo(sample.repo_url, repo_path)
                
                logger.info("Computing ground truth diff")
                ground_truth_patch = get_unified_diff(
                    repo, sample.base_commit, sample.head_commit
                )
            
            # Compute scores
            if self.judge_mode == "deterministic":
                scores = self.compute_deterministic_scores(
                    edit_result.patch_unified,
                    ground_truth_patch,
                )
                rationale = None
            else:
                scores, rationale = self.compute_llm_scores(
                    edit_result.patch_unified,
                    ground_truth_patch,
                    sample.task_instructions,
                )
            
            # Compute aggregate score
            aggregate = (
                scores.correctness
                + scores.completeness
                + scores.code_reuse
                + scores.best_practices
                + scores.unsolicited_docs
            ) / 5.0
            
            # Create judge result
            judge_result = JudgeResult(
                repo_url=sample.repo_url,
                pr_number=sample.pr_number,
                base_commit=sample.base_commit,
                head_commit=sample.head_commit,
                judge_mode=self.judge_mode,
                judge_model=self.judge_model,
                scores=scores,
                aggregate=aggregate,
                rationale=rationale,
            )
            
            # Save judge result
            judge_dir = (
                output_dir
                / "judges"
                / self.judge_mode
                / (self.judge_model or "none")
                / self.run_id
                / pr_id
            )
            judge_dir.mkdir(parents=True, exist_ok=True)
            
            judge_path = judge_dir / "judge.json"
            save_json(judge_result.model_dump(), judge_path)
            
            logger.info(f"Judge result saved to {judge_path}")
            logger.info(f"Aggregate score: {aggregate:.3f}")
            
            return judge_result
            
        except Exception as e:
            logger.error(f"Failed to judge edit {pr_id}: {e}", exc_info=True)
            return None

    def judge_edits(
        self,
        samples: list[Sample],
        edit_results: list[EditResult],
        output_dir: Path,
    ) -> list[JudgeResult]:
        """Judge multiple edits.
        
        Args:
            samples: List of samples
            edit_results: List of edit results
            output_dir: Output directory for artifacts
            
        Returns:
            List of successfully generated JudgeResults
        """
        # Match samples with edit results
        sample_map = {
            (s.repo_url, s.pr_number): s for s in samples
        }
        
        results = []
        
        for edit_result in edit_results:
            key = (edit_result.repo_url, edit_result.pr_number)
            if key not in sample_map:
                logger.warning(f"No sample found for edit: {key}")
                continue
            
            sample = sample_map[key]
            result = self.judge_edit(sample, edit_result, output_dir)
            if result:
                results.append(result)
        
        return results

