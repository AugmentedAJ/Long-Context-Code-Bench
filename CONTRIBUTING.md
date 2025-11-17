# Contributing to Long-Context-Bench

Thank you for your interest in contributing to Long-Context-Bench! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python ≥ 3.11
- Git
- GitHub account

### Installation

1. Fork the repository on GitHub

2. Clone your fork:
```bash
git clone https://github.com/YOUR_USERNAME/Long-Context-Code-Bench.git
cd Long-Context-Code-Bench
```

3. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

4. Install in development mode:
```bash
pip install -e ".[dev]"
```

## Development Workflow

### Running Tests

```bash
pytest tests/
```

### Code Formatting

We use `black` for code formatting:

```bash
black long_context_bench/ tests/
```

### Linting

We use `ruff` for linting:

```bash
ruff check long_context_bench/ tests/
```

### Type Checking

We use `mypy` for type checking:

```bash
mypy long_context_bench/
```

## Making Changes

### Branch Naming

- Feature branches: `feature/description`
- Bug fixes: `fix/description`
- Documentation: `docs/description`

### Commit Messages

Follow conventional commits format:

- `feat: Add new feature`
- `fix: Fix bug in X`
- `docs: Update documentation`
- `test: Add tests for Y`
- `refactor: Refactor Z`

### Pull Request Process

1. Create a new branch from `main`
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass
5. Update documentation as needed
6. Submit a pull request

## Adding New Runners

To add support for a new CLI agent:

1. Create a new adapter in `long_context_bench/runners/`:

```python
from long_context_bench.runners.base import RunnerAdapter, RunnerResult

class MyAgentAdapter(RunnerAdapter):
    def run(self, workspace_path, task_instructions, logs_path, env):
        # Implement agent execution
        pass
```

2. Register the adapter in `long_context_bench/runners/__init__.py`:

```python
def get_runner_adapter(runner_name: str, **kwargs) -> RunnerAdapter:
    adapters = {
        "auggie": AuggieAdapter,
        "my-agent": MyAgentAdapter,  # Add here
        "generic": GenericAdapter,
    }
    # ...
```

3. Add tests under `tests/` (for example, in a new `tests/test_runners_<name>.py`)

4. Update documentation in `README.md`

## Adding New Metrics

To add a new evaluation metric:

1. Update `Scores` model in `long_context_bench/models.py`:

```python
class Scores(BaseModel):
    correctness: float = Field(ge=-1.0, le=1.0)
    # ... existing metrics
    new_metric: float = Field(ge=-1.0, le=1.0)
```

2. Update judge logic in `long_context_bench/stages/judge.py`

3. Update aggregate calculation to include new metric

4. Add tests

## Dataset Versioning

When proposing changes to the dataset:

1. Create a new version (e.g., v1)
2. Document changes in `CHANGELOG.md`
3. Update `data/` directory with new dataset file
4. Ensure backward compatibility or provide migration guide

## Documentation

- Update `README.md` for user-facing changes
- Update design and requirements docs under `docs/` as needed
- Add docstrings to all public functions and classes
- Update `CHANGELOG.md` with your changes

## Code Style

- Follow PEP 8
- Use type hints for all function signatures
- Write descriptive docstrings (Google style)
- Keep functions focused and small
- Add comments for complex logic

## Testing Guidelines

- Write tests for all new functionality
- Aim for high test coverage
- Use descriptive test names
- Test edge cases and error conditions
- Mock external dependencies (GitHub API, git operations)

## Questions?

If you have questions or need help:

- Open an issue on GitHub
- Tag maintainers in your PR
- Check existing issues and PRs for similar discussions

## License

By contributing, you agree that your contributions will be licensed under the Apache-2.0 License.

