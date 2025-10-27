"""Runner adapters for different CLI-based coding agents."""

from long_context_bench.runners.base import RunnerAdapter, RunnerConfig, RunnerResult
from long_context_bench.runners.auggie import AuggieAdapter

__all__ = [
    "RunnerAdapter",
    "RunnerConfig",
    "RunnerResult",
    "AuggieAdapter",
]


def get_runner_adapter(runner_name: str) -> type[RunnerAdapter]:
    """Get runner adapter class by name.
    
    Args:
        runner_name: Name of the runner (e.g., 'auggie')
        
    Returns:
        RunnerAdapter subclass
        
    Raises:
        ValueError: If runner is not supported
    """
    runners = {
        "auggie": AuggieAdapter,
    }
    
    if runner_name not in runners:
        raise ValueError(
            f"Unsupported runner: {runner_name}. "
            f"Supported runners: {', '.join(runners.keys())}"
        )
    
    return runners[runner_name]

