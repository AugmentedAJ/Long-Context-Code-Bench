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

## Web UI Development

The web dashboard is located in `long_context_bench/web/` and deployed to `output/web/`.

### Key Files

- `index.html` - Main HTML structure and layout
- `app.js` - Core application logic, leaderboard, PR details
- `data-loader.js` - Data fetching and caching
- `styles.css` - Styling
- `server.js` - Express server for local development

### Development Workflow

1. Make changes to files in `long_context_bench/web/`

2. Deploy and test:
```bash
long-context-bench web output
# Or manually:
python3 -c "from long_context_bench.stats import deploy_web_app; from pathlib import Path; deploy_web_app(Path('output'))"
```

3. Refresh browser at http://localhost:3000

### Metrics Display Conventions

- **Win Rate**: Primary ranking metric (percentage of PRs where agent beat human)
- **Score colors**: Green (≥0.5), Orange (0 to 0.5), Red (<0)
- **Unsolicited Docs**: Uses **inverted colors** (lower = better, shown in green)

### Regenerating Summaries

After changing how metrics are calculated:

```bash
# Regenerate all summaries for a judge run
for edit_run in <edit_run_id_1> <edit_run_id_2> ...; do
  long-context-bench summary output \
    --edit-run-id $edit_run \
    --judge-run-id <judge_run_id> \
    --output-dir output
done
```

## Adding New Metrics

To add a new evaluation metric:

1. Update `Scores` model in `long_context_bench/models.py`:

```python
class Scores(BaseModel):
    correctness: float = Field(ge=-1.0, le=1.0)
    # ... existing metrics
    new_metric: float = Field(ge=-1.0, le=1.0)
```

**Note**: All metrics use the scale: -1 = much worse than human, 0 = human level (ground truth), 1 = better than human

2. Update judge logic in `long_context_bench/stages/judge.py`

3. Update web UI to display the new metric in `long_context_bench/web/app.js` and `index.html`

4. Regenerate summaries and redeploy web app

5. Add tests

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

