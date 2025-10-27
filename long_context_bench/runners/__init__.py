"""Runner adapters for CLI-based coding agents."""

from long_context_bench.runners.base import RunnerAdapter, RunnerResult
from long_context_bench.runners.auggie import AuggieAdapter
from long_context_bench.runners.generic import GenericAdapter

__all__ = ["RunnerAdapter", "RunnerResult", "AuggieAdapter", "GenericAdapter"]


def get_runner_adapter(runner_name: str, **kwargs) -> RunnerAdapter:
    """Get runner adapter by name.
    
    Args:
        runner_name: Name of the runner (e.g., "auggie", "claude-code")
        **kwargs: Additional arguments for the adapter
        
    Returns:
        RunnerAdapter instance
    """
    adapters = {
        "auggie": AuggieAdapter,
        "generic": GenericAdapter,
    }
    
    adapter_class = adapters.get(runner_name, GenericAdapter)
    return adapter_class(**kwargs)

