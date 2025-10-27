# Contributing to Long-Context-Bench

Thank you for your interest in contributing to Long-Context-Bench! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/Long-Context-Code-Bench.git`
3. Create a virtual environment: `python -m venv venv && source venv/bin/activate`
4. Install in development mode: `pip install -e ".[dev]"`
5. Create a branch: `git checkout -b feature/your-feature-name`

## Development Workflow

### Running Tests

```bash
pytest
```

### Code Formatting

We use `black` for code formatting and `ruff` for linting:

```bash
black src/ tests/
ruff check src/ tests/
```

### Type Checking

We use `mypy` for type checking:

```bash
mypy src/
```

## Adding a New Runner Adapter

To add support for a new CLI-based coding agent:

1. Create a new file in `src/long_context_bench/runners/` (e.g., `my_agent.py`)
2. Implement a subclass of `RunnerAdapter`:

```python
from long_context_bench.runners.base import RunnerAdapter, RunnerResult
from pathlib import Path

class MyAgentAdapter(RunnerAdapter):
    def get_default_binary_name(self) -> str:
        return "my-agent"
    
    def get_version(self) -> str:
        # Implement version detection
        pass
    
    def validate_environment(self) -> None:
        # Check for required environment variables
        pass
    
    def run(
        self,
        workspace_path: Path,
        task_instructions: str,
    ) -> RunnerResult:
        # Implement agent execution
        pass
```

3. Register your adapter in `src/long_context_bench/runners/__init__.py`:

```python
from long_context_bench.runners.my_agent import MyAgentAdapter

def get_runner_adapter(runner_name: str) -> type[RunnerAdapter]:
    runners = {
        "auggie": AuggieAdapter,
        "my-agent": MyAgentAdapter,  # Add your adapter
    }
    # ...
```

4. Add tests in `tests/test_runners.py`
5. Update documentation in `README.md`

### Runner Adapter Requirements

Your adapter must:

- Implement all abstract methods from `RunnerAdapter`
- Handle timeouts gracefully
- Return structured logs in JSONL format
- Exit with code 0 on success, non-zero on failure
- Support all required configuration options (model, timeout, etc.)
- Validate environment variables before execution

## Testing Your Changes

### Unit Tests

Add unit tests for new functionality:

```bash
pytest tests/test_your_module.py
```

### Integration Tests

Test your changes with a real PR:

```bash
long-context-bench pipeline \
  --runner your-runner \
  --model your-model \
  https://github.com/elastic/elasticsearch/pull/100001
```

## Submitting Changes

1. Ensure all tests pass: `pytest`
2. Format your code: `black src/ tests/`
3. Check linting: `ruff check src/ tests/`
4. Commit your changes with a descriptive message
5. Push to your fork: `git push origin feature/your-feature-name`
6. Open a pull request

### Pull Request Guidelines

- Provide a clear description of the changes
- Reference any related issues
- Include tests for new functionality
- Update documentation as needed
- Ensure CI passes

## Code Style

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Write docstrings for all public functions and classes
- Keep functions focused and concise
- Use meaningful variable names

## Documentation

When adding new features:

- Update the README.md with usage examples
- Add docstrings to all public APIs
- Update CHANGELOG.md with your changes
- Consider adding examples to the documentation

## Questions?

If you have questions or need help:

- Open an issue on GitHub
- Check existing issues and discussions
- Review the PRD (prd.md) for design decisions

## License

By contributing, you agree that your contributions will be licensed under the Apache-2.0 License.

