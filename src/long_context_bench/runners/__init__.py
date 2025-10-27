"""Runner adapters for different CLI-based coding agents."""

from .base import BaseRunner, RunnerResult
from .auggie import AuggieRunner

__all__ = ['BaseRunner', 'RunnerResult', 'AuggieRunner']


def get_runner(runner_name: str, config) -> BaseRunner:
    """Get runner instance by name.
    
    Args:
        runner_name: Name of the runner
        config: Benchmark configuration
        
    Returns:
        Runner instance
        
    Raises:
        ValueError: If runner name is not supported
    """
    runners = {
        'auggie': AuggieRunner,
    }
    
    if runner_name not in runners:
        raise ValueError(
            f"Unknown runner: {runner_name}. "
            f"Supported runners: {', '.join(runners.keys())}"
        )
    
    return runners[runner_name](config)

