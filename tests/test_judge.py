"""Tests for judge stage."""

import pytest
from long_context_bench.stages.judge import compute_deterministic_scores, compute_llm_scores
from long_context_bench.models import Scores


def test_compute_deterministic_scores_exact_match():
    """Test deterministic scoring with exact match."""
    diff = """diff --git a/file.py b/file.py
index abc123..def456 100644
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
 def hello():
-    print("world")
+    print("universe")
"""
    
    scores = compute_deterministic_scores(diff, diff)
    
    assert scores.correctness == 1.0
    assert scores.completeness == 1.0
    assert scores.code_reuse == 1.0
    assert scores.best_practices == 1.0
    assert scores.unsolicited_docs == 1.0


def test_compute_deterministic_scores_empty_agent_diff():
    """Test deterministic scoring with empty agent diff."""
    ground_truth = """diff --git a/file.py b/file.py
index abc123..def456 100644
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
 def hello():
-    print("world")
+    print("universe")
"""
    
    scores = compute_deterministic_scores("", ground_truth)
    
    assert scores.correctness == -1.0
    assert scores.completeness == -1.0
    assert scores.code_reuse == 0.0
    assert scores.best_practices == 0.0
    assert scores.unsolicited_docs == 1.0


def test_compute_deterministic_scores_partial_match():
    """Test deterministic scoring with partial match."""
    ground_truth = """diff --git a/file.py b/file.py
index abc123..def456 100644
--- a/file.py
+++ b/file.py
@@ -1,5 +1,5 @@
 def hello():
-    print("world")
+    print("universe")
 def goodbye():
-    print("world")
+    print("universe")
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
    
    scores = compute_deterministic_scores(agent_diff, ground_truth)
    
    # Should have positive but not perfect scores
    assert -1.0 <= scores.correctness <= 1.0
    assert -1.0 <= scores.completeness <= 1.0
    assert scores.completeness < 1.0  # Not complete


def test_compute_deterministic_scores_unsolicited_docs():
    """Test deterministic scoring detects unsolicited documentation."""
    ground_truth = """diff --git a/file.py b/file.py
index abc123..def456 100644
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
 def hello():
-    print("world")
+    print("universe")
"""
    
    agent_diff = """diff --git a/file.py b/file.py
index abc123..def456 100644
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
 def hello():
-    print("world")
+    print("universe")
diff --git a/README.md b/README.md
new file mode 100644
--- /dev/null
+++ b/README.md
@@ -0,0 +1,3 @@
+# Documentation
+
+This is unsolicited documentation.
"""
    
    scores = compute_deterministic_scores(agent_diff, ground_truth)
    
    # Should penalize unsolicited docs
    assert scores.unsolicited_docs < 0.0


def test_compute_llm_scores_structure():
    """Test that LLM scores returns proper structure (may fall back to deterministic)."""
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
    
    # This will likely fall back to deterministic unless API keys are set
    scores, rationale = compute_llm_scores(
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

