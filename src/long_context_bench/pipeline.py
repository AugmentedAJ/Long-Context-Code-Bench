"""Pipeline orchestration for end-to-end benchmark execution."""

import logging
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from .config import BenchmarkConfig
from .judge import get_judge, get_ground_truth_diff
from .runners import get_runner
from .sampler import PRSampler
from .schemas import Edit, Sample, get_pr_id
from .utils import get_shard_index, load_json, save_json

logger = logging.getLogger(__name__)


class BenchmarkPipeline:
    """Orchestrates the complete benchmark pipeline."""
    
    def __init__(self, config: BenchmarkConfig):
        """Initialize pipeline.
        
        Args:
            config: Benchmark configuration
        """
        self.config = config
        self.run_id = str(uuid.uuid4())[:8]
        
        # Initialize components
        self.sampler = PRSampler(config)
        self.runner = get_runner(config.runner, config)
        self.judge = get_judge(config)
    
    def should_process_pr(self, repo_url: str, pr_number: int) -> bool:
        """Check if PR should be processed by this shard.
        
        Args:
            repo_url: Repository URL
            pr_number: PR number
            
        Returns:
            True if this shard should process the PR
        """
        if self.config.total_shards == 1:
            return True
        
        shard = get_shard_index(repo_url, pr_number, self.config.total_shards)
        return shard == self.config.shard_index
    
    def run_sample_stage(self, pr_url: str) -> Optional[Sample]:
        """Run sample stage for a single PR.
        
        Args:
            pr_url: GitHub PR URL
            
        Returns:
            Sample object, or None if failed
        """
        logger.info(f"[Sample] Processing {pr_url}")
        return self.sampler.sample_pr(pr_url)
    
    def run_edit_stage(self, sample: Sample) -> Optional[Edit]:
        """Run edit stage for a sample.
        
        Args:
            sample: Sample artifact
            
        Returns:
            Edit object, or None if failed
        """
        pr_id = get_pr_id(sample.repo_url, sample.pr_number)
        logger.info(f"[Edit] Processing {pr_id}")
        
        try:
            # Create temporary workspace
            with tempfile.TemporaryDirectory() as tmpdir:
                workspace_path = Path(tmpdir) / "workspace"
                
                # Prepare workspace at base commit
                self.runner.prepare_workspace(
                    sample.repo_url,
                    sample.base_commit,
                    workspace_path
                )
                
                # Set up logs path
                edit_dir = self.config.get_edit_path(pr_id, self.run_id).parent
                logs_path = edit_dir / "logs.jsonl"
                
                # Run agent
                result = self.runner.run(
                    workspace_path,
                    sample.task_instructions,
                    logs_path
                )
                
                # Create edit artifact
                edit = Edit(
                    repo_url=sample.repo_url,
                    pr_number=sample.pr_number,
                    base_commit=sample.base_commit,
                    runner=self.config.runner,
                    model=self.config.model,
                    timeout_s=self.config.timeout,
                    status=result.status,
                    elapsed_ms=result.elapsed_ms,
                    patch_unified=result.patch_unified,
                    logs_path=result.logs_path,
                    errors=result.errors
                )
                
                # Save edit artifact
                edit_path = self.config.get_edit_path(pr_id, self.run_id)
                save_json(edit.model_dump(), edit_path)
                
                logger.info(f"[Edit] Saved to {edit_path}")
                return edit
                
        except Exception as e:
            logger.error(f"[Edit] Failed for {pr_id}: {e}", exc_info=True)
            return None
    
    def run_judge_stage(self, sample: Sample, edit: Edit) -> Optional[dict]:
        """Run judge stage for a sample and edit.
        
        Args:
            sample: Sample artifact
            edit: Edit artifact
            
        Returns:
            Judge artifact as dict, or None if failed
        """
        pr_id = get_pr_id(sample.repo_url, sample.pr_number)
        logger.info(f"[Judge] Processing {pr_id}")
        
        try:
            # Get ground truth diff
            with tempfile.TemporaryDirectory() as tmpdir:
                workspace_path = Path(tmpdir) / "workspace"
                ground_truth_diff = get_ground_truth_diff(
                    sample.repo_url,
                    sample.base_commit,
                    sample.head_commit,
                    workspace_path
                )
            
            # Evaluate
            judge_result = self.judge.evaluate(sample, edit, ground_truth_diff)
            
            # Save judge artifact
            judge_path = self.config.get_judge_path(pr_id, self.run_id)
            save_json(judge_result.model_dump(), judge_path)
            
            logger.info(f"[Judge] Saved to {judge_path}")
            return judge_result.model_dump()
            
        except Exception as e:
            logger.error(f"[Judge] Failed for {pr_id}: {e}", exc_info=True)
            return None
    
    def process_single_pr(self, pr_url: str) -> Optional[dict]:
        """Process a single PR through the entire pipeline.
        
        Args:
            pr_url: GitHub PR URL
            
        Returns:
            Judge result, or None if any stage failed
        """
        # Sample stage
        sample = self.run_sample_stage(pr_url)
        if not sample:
            return None
        
        # Check if this shard should process this PR
        if not self.should_process_pr(sample.repo_url, sample.pr_number):
            logger.info(f"Skipping PR (belongs to different shard): {pr_url}")
            return None
        
        # Edit stage
        edit = self.run_edit_stage(sample)
        if not edit:
            return None
        
        # Judge stage
        judge_result = self.run_judge_stage(sample, edit)
        return judge_result
    
    def run_pipeline(self, pr_urls: list[str]) -> dict:
        """Run the complete pipeline on a list of PRs.
        
        Args:
            pr_urls: List of GitHub PR URLs
            
        Returns:
            Summary statistics
        """
        logger.info(f"Starting pipeline with {len(pr_urls)} PRs")
        logger.info(f"Run ID: {self.run_id}")
        logger.info(f"Shard: {self.config.shard_index + 1}/{self.config.total_shards}")
        logger.info(f"Concurrency: {self.config.concurrency}")
        
        results = []
        
        # Process PRs with concurrency
        with ThreadPoolExecutor(max_workers=self.config.concurrency) as executor:
            futures = {
                executor.submit(self.process_single_pr, pr_url): pr_url
                for pr_url in pr_urls
            }
            
            for future in as_completed(futures):
                pr_url = futures[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error processing {pr_url}: {e}", exc_info=True)
        
        # Generate summary
        summary = self._generate_summary(results)
        
        # Save summary
        summary_path = self.config.get_summary_path(self.run_id)
        save_json(summary, summary_path / "summary.json")
        
        logger.info(f"Pipeline complete. Summary saved to {summary_path}")
        
        return summary
    
    def _generate_summary(self, results: list[dict]) -> dict:
        """Generate summary statistics from results.
        
        Args:
            results: List of judge results
            
        Returns:
            Summary dictionary
        """
        if not results:
            return {
                'run_id': self.run_id,
                'total_samples': 0,
                'successful_samples': 0,
                'metrics': {}
            }
        
        # Compute aggregate metrics
        metrics = {
            'correctness': [],
            'completeness': [],
            'code_reuse': [],
            'best_practices': [],
            'unsolicited_docs': [],
            'aggregate': []
        }
        
        for result in results:
            scores = result['scores']
            metrics['correctness'].append(scores['correctness'])
            metrics['completeness'].append(scores['completeness'])
            metrics['code_reuse'].append(scores['code_reuse'])
            metrics['best_practices'].append(scores['best_practices'])
            metrics['unsolicited_docs'].append(scores['unsolicited_docs'])
            metrics['aggregate'].append(result['aggregate'])
        
        # Compute means
        summary_metrics = {}
        for metric, values in metrics.items():
            summary_metrics[metric] = {
                'mean': sum(values) / len(values) if values else 0.0,
                'min': min(values) if values else 0.0,
                'max': max(values) if values else 0.0
            }
        
        return {
            'run_id': self.run_id,
            'total_samples': len(results),
            'successful_samples': len(results),
            'metrics': summary_metrics
        }

