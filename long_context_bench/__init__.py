"""Long-Context-Bench: Benchmark for evaluating long-context code editing capabilities.

This module also exposes a few lightweight configuration constants that are safe to
import from anywhere in the codebase.
"""

__version__ = "0.1.0"

# Default agent-as-judge configuration for head-to-head evaluation.
#
# For v0 we standardize on a single canonical agent judge to keep the
# benchmark transparent and reproducible. Claude Code is used as the
# default judge because it is the most commonly deployed agent in our
# current setup, but any supported runner can be used instead.

# Runner name for the default head-to-head judge agent (Claude Code CLI).
DEFAULT_HEAD_TO_HEAD_JUDGE_RUNNER: str = "claude-code"

# Model name passed to the judge runner. This should match the model
# string used in the edit stage for Claude Code in the v0 benchmark.
DEFAULT_HEAD_TO_HEAD_JUDGE_MODEL: str = "claude-sonnet-4-5"

