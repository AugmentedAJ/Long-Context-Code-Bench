"""Judge stage: Evaluate agent outputs against ground truth."""

import logging
from pathlib import Path
from typing import Optional

from git import Repo

from .config import BenchmarkConfig
from .schemas import Judge, Scores, Sample, Edit, get_pr_id
from .utils import save_json

logger = logging.getLogger(__name__)


class DeterministicJudge:
    """Deterministic baseline judge using diff overlap metrics."""
    
    def __init__(self, config: BenchmarkConfig):
        """Initialize judge.
        
        Args:
            config: Benchmark configuration
        """
        self.config = config
    
    def compute_diff_overlap(self, agent_diff: str, ground_truth_diff: str) -> float:
        """Compute overlap between agent diff and ground truth.
        
        Args:
            agent_diff: Agent-produced diff
            ground_truth_diff: Ground truth diff
            
        Returns:
            Overlap score in [0, 1]
        """
        if not agent_diff or not ground_truth_diff:
            return 0.0
        
        # Split into lines and normalize
        agent_lines = set(line.strip() for line in agent_diff.split('\n') if line.strip())
        gt_lines = set(line.strip() for line in ground_truth_diff.split('\n') if line.strip())
        
        if not gt_lines:
            return 0.0
        
        # Compute Jaccard similarity
        intersection = len(agent_lines & gt_lines)
        union = len(agent_lines | gt_lines)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def count_documentation_additions(self, diff: str) -> int:
        """Count documentation additions in diff.
        
        Args:
            diff: Unified diff
            
        Returns:
            Number of documentation lines added
        """
        doc_count = 0
        
        for line in diff.split('\n'):
            # Look for added lines that are comments or documentation
            if line.startswith('+'):
                stripped = line[1:].strip()
                # Simple heuristic: lines starting with #, //, /*, *, """
                if any(stripped.startswith(marker) for marker in ['#', '//', '/*', '*', '"""', "'''"]):
                    doc_count += 1
        
        return doc_count
    
    def evaluate(
        self,
        sample: Sample,
        edit: Edit,
        ground_truth_diff: str
    ) -> Judge:
        """Evaluate an agent edit against ground truth.
        
        Args:
            sample: Sample artifact
            edit: Edit artifact
            ground_truth_diff: Ground truth diff from PR
            
        Returns:
            Judge artifact with scores
        """
        agent_diff = edit.patch_unified
        
        # Compute overlap score
        overlap = self.compute_diff_overlap(agent_diff, ground_truth_diff)
        
        # Correctness: based on overlap
        correctness = overlap
        
        # Completeness: penalize if agent diff is much smaller than ground truth
        agent_lines = len([l for l in agent_diff.split('\n') if l.strip()])
        gt_lines = len([l for l in ground_truth_diff.split('\n') if l.strip()])
        
        if gt_lines > 0:
            completeness = min(1.0, agent_lines / gt_lines) * overlap
        else:
            completeness = 0.0
        
        # Code reuse: assume neutral for deterministic judge
        code_reuse = 0.0
        
        # Best practices: assume neutral for deterministic judge
        best_practices = 0.0
        
        # Unsolicited documentation: penalize if docs added when not in ground truth
        gt_doc_count = self.count_documentation_additions(ground_truth_diff)
        agent_doc_count = self.count_documentation_additions(agent_diff)
        
        if agent_doc_count > gt_doc_count:
            unsolicited_docs = -0.5  # Penalty
        else:
            unsolicited_docs = 0.0
        
        scores = Scores(
            correctness=correctness,
            completeness=completeness,
            code_reuse=code_reuse,
            best_practices=best_practices,
            unsolicited_docs=unsolicited_docs
        )
        
        # Compute aggregate
        aggregate = (
            scores.correctness +
            scores.completeness +
            scores.code_reuse +
            scores.best_practices +
            scores.unsolicited_docs
        ) / 5.0
        
        return Judge(
            repo_url=sample.repo_url,
            pr_number=sample.pr_number,
            base_commit=sample.base_commit,
            head_commit=sample.head_commit,
            judge_mode='deterministic',
            judge_model=None,
            scores=scores,
            aggregate=aggregate,
            rationale=f"Deterministic judge: overlap={overlap:.2f}"
        )


class LLMJudge:
    """LLM-based judge for more nuanced evaluation."""
    
    def __init__(self, config: BenchmarkConfig):
        """Initialize LLM judge.
        
        Args:
            config: Benchmark configuration
        """
        self.config = config
        # TODO: Initialize LLM client based on config.judge_model
    
    def evaluate(
        self,
        sample: Sample,
        edit: Edit,
        ground_truth_diff: str
    ) -> Judge:
        """Evaluate using LLM.
        
        Args:
            sample: Sample artifact
            edit: Edit artifact
            ground_truth_diff: Ground truth diff from PR
            
        Returns:
            Judge artifact with scores
        """
        # TODO: Implement LLM-based evaluation
        # For now, fall back to deterministic
        logger.warning("LLM judge not yet implemented, using deterministic")
        deterministic = DeterministicJudge(self.config)
        return deterministic.evaluate(sample, edit, ground_truth_diff)


def get_judge(config: BenchmarkConfig):
    """Get judge instance based on configuration.
    
    Args:
        config: Benchmark configuration
        
    Returns:
        Judge instance
    """
    if config.judge_mode == 'deterministic':
        return DeterministicJudge(config)
    elif config.judge_mode == 'llm':
        return LLMJudge(config)
    else:
        raise ValueError(f"Unknown judge mode: {config.judge_mode}")


def get_ground_truth_diff(
    repo_url: str,
    base_commit: str,
    head_commit: str,
    workspace_path: Path
) -> str:
    """Get ground truth diff from PR.
    
    Args:
        repo_url: Repository URL
        base_commit: Base commit hash
        head_commit: Head commit hash
        workspace_path: Temporary workspace path
        
    Returns:
        Unified diff as string
    """
    # Clone repository
    repo = Repo.clone_from(repo_url, workspace_path)
    
    # Fetch both commits
    repo.git.fetch('origin', base_commit)
    repo.git.fetch('origin', head_commit)
    
    # Get diff
    diff = repo.git.diff(base_commit, head_commit)
    
    return diff

