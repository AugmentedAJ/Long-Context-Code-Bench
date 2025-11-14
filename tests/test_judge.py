"""Tests for judge stage."""

import pytest
from long_context_bench.stages.judge import compute_llm_scores
from long_context_bench.models import Scores


def test_compute_llm_scores_structure():
    """Test that LLM scores returns proper structure."""
    agent_diff = """diff --git a/file.py b/file.py
index abc123..def456 100644
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
 def hello():
-    print("world")
+    print("universe")
"""

    ground_truth = agent_diff
    task_instructions = "Change the greeting message"

    # This requires API keys to be set
    scores, rationale, llm_rating, llm_summary = compute_llm_scores(
        agent_diff,
        ground_truth,
        task_instructions,
        "gpt-4"
    )

    # Verify structure
    assert isinstance(scores, Scores)
    assert isinstance(rationale, str)
    assert -1.0 <= scores.correctness <= 1.0
    assert -1.0 <= scores.completeness <= 1.0
    assert -1.0 <= scores.code_reuse <= 1.0
    assert -1.0 <= scores.best_practices <= 1.0
    assert -1.0 <= scores.unsolicited_docs <= 1.0
    assert len(rationale) > 0

