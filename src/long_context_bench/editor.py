"""Edit stage: Run agents to produce edits."""

import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import git

from long_context_bench.models import EditResult, Sample
from long_context_bench.runners import RunnerConfig, get_runner_adapter
from long_context_bench.utils import (
    clone_repo,
    get_pr_id,
    get_unified_diff,
    save_json,
)

logger = logging.getLogger(__name__)


class Editor:
    """Editor for running agents on samples."""

    def __init__(self, runner_config: RunnerConfig, run_id: Optional[str] = None):
        """Initialize editor.
        
        Args:
            runner_config: Runner configuration
            run_id: Run identifier (generated if not provided)
        """
        self.runner_config = runner_config
        self.run_id = run_id or datetime.now().strftime("run_%Y%m%d_%H%M%S")
        
        # Get runner adapter
        adapter_class = get_runner_adapter(runner_config.runner)
        self.adapter = adapter_class(runner_config)

    def edit_sample(
        self,
        sample: Sample,
        output_dir: Path,
    ) -> Optional[EditResult]:
        """Run agent on a sample to produce edits.
        
        Args:
            sample: Sample to edit
            output_dir: Output directory for artifacts
            
        Returns:
            EditResult or None if editing failed
        """
        pr_id = get_pr_id(sample.repo_url, sample.pr_number)
        logger.info(f"Editing sample: {pr_id}")
        
        try:
            # Create temporary workspace
            with tempfile.TemporaryDirectory() as tmpdir:
                workspace_path = Path(tmpdir) / "workspace"
                
                # Clone repo and checkout base commit
                logger.info(f"Cloning repository to {workspace_path}")
                repo = clone_repo(sample.repo_url, workspace_path)
                
                logger.info(f"Checking out base commit: {sample.base_commit}")
                repo.git.checkout(sample.base_commit, detach=True)
                
                # Run agent
                logger.info("Running agent")
                result = self.adapter.run(
                    workspace_path=workspace_path,
                    task_instructions=sample.task_instructions,
                )
                
                # Extract unified diff
                patch_unified = ""
                if result.status == "success":
                    try:
                        # Get diff against base commit
                        patch_unified = repo.git.diff(sample.base_commit, unified=3)
                        logger.info(f"Generated patch: {len(patch_unified)} bytes")
                    except Exception as e:
                        logger.error(f"Failed to generate diff: {e}")
                        result.status = "error"
                        if result.errors:
                            result.errors.append(f"Failed to generate diff: {e}")
                        else:
                            result.errors = [f"Failed to generate diff: {e}"]
            
            # Create edit result
            edit_result = EditResult(
                repo_url=sample.repo_url,
                pr_number=sample.pr_number,
                base_commit=sample.base_commit,
                runner=self.runner_config.runner,
                model=self.runner_config.model,
                timeout_s=self.runner_config.timeout_s,
                status=result.status,
                elapsed_ms=result.elapsed_ms,
                patch_unified=patch_unified,
                logs_path=f"logs.jsonl",
                errors=result.errors,
            )
            
            # Save edit result and logs
            edit_dir = (
                output_dir
                / "edits"
                / self.runner_config.runner
                / self.runner_config.model
                / self.run_id
                / pr_id
            )
            edit_dir.mkdir(parents=True, exist_ok=True)
            
            edit_path = edit_dir / "edit.json"
            save_json(edit_result.model_dump(), edit_path)
            
            # Save logs
            logs_path = edit_dir / "logs.jsonl"
            with open(logs_path, "w") as f:
                for log_line in result.logs:
                    f.write(log_line + "\n")
            
            logger.info(f"Edit result saved to {edit_path}")
            
            return edit_result
            
        except Exception as e:
            logger.error(f"Failed to edit sample {pr_id}: {e}", exc_info=True)
            return None

    def edit_samples(
        self,
        samples: list[Sample],
        output_dir: Path,
    ) -> list[EditResult]:
        """Run agent on multiple samples.
        
        Args:
            samples: List of samples to edit
            output_dir: Output directory for artifacts
            
        Returns:
            List of successfully generated EditResults
        """
        results = []
        
        for sample in samples:
            result = self.edit_sample(sample, output_dir)
            if result:
                results.append(result)
        
        return results

