"""Auggie runner adapter."""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from .base import BaseRunner, RunnerResult

logger = logging.getLogger(__name__)


class AuggieRunner(BaseRunner):
    """Runner adapter for Auggie CLI agent."""
    
    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
        logs_path: Path
    ) -> RunnerResult:
        """Run Auggie on a task.
        
        Args:
            workspace_path: Path to prepared workspace
            task_instructions: Task instructions for the agent
            logs_path: Path to write logs
            
        Returns:
            RunnerResult with status and outputs
        """
        logs = []
        errors = []
        
        try:
            # Create a temporary file for the task instructions
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.txt', 
                delete=False
            ) as f:
                f.write(task_instructions)
                instructions_file = f.name
            
            # Build command
            cmd = self._build_command(instructions_file)
            
            # Set up environment
            env = os.environ.copy()
            if self.config.augment_api_token:
                env['AUGMENT_API_TOKEN'] = self.config.augment_api_token
            
            # Log command
            logs.append({
                'timestamp': self._get_timestamp(),
                'event': 'command_start',
                'command': ' '.join(cmd)
            })
            
            # Execute with timeout
            return_code, stdout, stderr, elapsed_ms = self.execute_with_timeout(
                cmd,
                workspace_path,
                self.config.timeout,
                env
            )
            
            # Clean up instructions file
            os.unlink(instructions_file)
            
            # Log completion
            logs.append({
                'timestamp': self._get_timestamp(),
                'event': 'command_complete',
                'return_code': return_code,
                'elapsed_ms': elapsed_ms
            })
            
            # Determine status
            if return_code == -1:
                status = 'timeout'
                errors.append('Agent execution timed out')
            elif return_code != 0:
                status = 'error'
                errors.append(f'Agent exited with code {return_code}')
                if stderr:
                    errors.append(f'stderr: {stderr}')
            else:
                status = 'success'
            
            # Extract diff
            patch_unified = self.extract_diff(workspace_path)
            
            # Write logs
            self.write_logs(logs, logs_path)
            
            return RunnerResult(
                status=status,
                elapsed_ms=elapsed_ms,
                patch_unified=patch_unified,
                logs_path=str(logs_path.relative_to(self.config.output_root)),
                errors=errors if errors else None
            )
            
        except Exception as e:
            logger.error(f"Error running Auggie: {e}", exc_info=True)
            errors.append(f"Exception: {str(e)}")
            
            # Write error logs
            logs.append({
                'timestamp': self._get_timestamp(),
                'event': 'error',
                'error': str(e)
            })
            self.write_logs(logs, logs_path)
            
            return RunnerResult(
                status='error',
                elapsed_ms=0,
                patch_unified='',
                logs_path=str(logs_path.relative_to(self.config.output_root)),
                errors=errors
            )
    
    def _build_command(self, instructions_file: str) -> list[str]:
        """Build Auggie command.
        
        Args:
            instructions_file: Path to file containing task instructions
            
        Returns:
            Command as list of strings
        """
        # Use agent binary if specified, otherwise use 'auggie'
        binary = self.config.agent_binary or 'auggie'
        
        cmd = [
            binary,
            '--model', self.config.model,
            '--input-file', instructions_file,
        ]
        
        # Add optional flags
        if self.config.disable_retrieval:
            cmd.append('--disable-retrieval')
        if self.config.disable_shell:
            cmd.append('--disable-shell')
        if self.config.enable_mcp_codebase_qa:
            cmd.append('--enable-mcp-codebase-qa')
        
        return cmd
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format.
        
        Returns:
            ISO formatted timestamp
        """
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'

