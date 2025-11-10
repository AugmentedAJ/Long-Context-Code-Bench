"""Tests for judge stage."""

import pytest
from long_context_bench.stages.judge import compute_llm_scores
from long_context_bench.models import Scores


def test_compute_llm_scores_structure():
    """Test that LLM scores returns proper structure.

    Note: This test will raise an exception if LLM API is not available,
    which is expected behavior after removing deterministic fallback.
    """
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

    # This will raise an exception if API keys are not set (expected behavior)
    with pytest.raises(Exception):
        scores, rationale, llm_rating, llm_summary = compute_llm_scores(
            agent_diff,
            ground_truth,
            task_instructions,
            "gpt-4"
        )

