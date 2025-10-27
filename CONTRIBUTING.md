# Contributing to Long-Context-Bench

Thank you for your interest in contributing to Long-Context-Bench! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/Long-Context-Code-Bench.git`
3. Create a new branch: `git checkout -b feature/your-feature-name`
4. Install development dependencies: `pip install -e ".[dev]"`

## Development Setup

### Prerequisites

- Python ≥ 3.11
- Git
- GitHub personal access token

### Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Set up environment variables
export GITHUB_GIT_TOKEN=your_token
export AUGMENT_API_TOKEN=your_token  # If testing with Auggie
```

## Code Style

We follow PEP 8 and use automated tools to enforce code style:

- **Black** for code formatting
- **Ruff** for linting
- **MyPy** for type checking

Before submitting a PR, run:

```bash
# Format code
black src/ tests/

# Check linting
ruff check src/ tests/

# Type checking
mypy src/
```

## Testing

We use pytest for testing. Please add tests for any new functionality.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=long_context_bench --cov-report=html

# Run specific test file
pytest tests/test_utils.py
```

## Adding a New Runner

To add support for a new CLI agent:

1. Create a new file in `src/long_context_bench/runners/` (e.g., `my_agent.py`)
2. Implement a class that inherits from `BaseRunner`
3. Implement the `run()` method
4. Register the runner in `src/long_context_bench/runners/__init__.py`
5. Add tests in `tests/test_runners.py`
6. Update documentation

Example:

```python
from .base import BaseRunner, RunnerResult

class MyAgentRunner(BaseRunner):
    def run(self, workspace_path, task_instructions, logs_path):
        # Implement agent execution
        pass
```

## Submitting Changes

1. Ensure all tests pass: `pytest`
2. Ensure code is formatted: `black src/ tests/`
3. Ensure linting passes: `ruff check src/ tests/`
4. Commit your changes with a descriptive message
5. Push to your fork
6. Create a Pull Request

### Commit Message Guidelines

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues and PRs when relevant

Example:
```
Add support for Claude Code runner

- Implement ClaudeCodeRunner class
- Add configuration options
- Update documentation
- Add tests

Fixes #123
```

## Pull Request Process

1. Update the README.md with details of changes if applicable
2. Update the CHANGELOG.md following the existing format
3. Ensure the PR description clearly describes the problem and solution
4. Link any relevant issues
5. Request review from maintainers

## Reporting Bugs

When reporting bugs, please include:

- Python version
- Operating system
- Steps to reproduce
- Expected behavior
- Actual behavior
- Error messages and stack traces
- Relevant configuration

## Feature Requests

We welcome feature requests! Please:

- Check if the feature has already been requested
- Clearly describe the use case
- Explain why this feature would be useful
- Provide examples if possible

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Assume good intentions

## Questions?

If you have questions, please:

- Check the documentation
- Search existing issues
- Open a new issue with the "question" label

## License

By contributing, you agree that your contributions will be licensed under:
- Apache-2.0 for code
- CC BY 4.0 for documentation

Thank you for contributing to Long-Context-Bench!

