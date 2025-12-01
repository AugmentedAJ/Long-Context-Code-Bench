"""Tests for cross-agent analysis."""

import json
import pytest
from pathlib import Path
from long_context_bench.models import (
    AgentResult, ComparativeAnalysis, CrossAgentJudge, Scores
)


def test_agent_result():
    """Test AgentResult model."""
    scores = Scores(
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
    )
    
    result = AgentResult(
        runner="auggie",
        model="sonnet4.5",
        edit_run_id="abc123",
        status="success",
        elapsed_ms=45000,
        patch_unified="diff --git a/file.py...",
        scores=scores,
        aggregate=0.85,
        rationale="Good implementation",
        errors=[],
    )
    
    assert result.runner == "auggie"
    assert result.model == "sonnet4.5"
    assert result.aggregate == 0.85
    assert result.scores.correctness == 0.8


def test_comparative_analysis():
    """Test ComparativeAnalysis model."""
    analysis = ComparativeAnalysis(
        summary="Agent A performed better overall",
        best_agent="auggie:sonnet4.5",
        best_agent_reasoning="More complete implementation",
        approach_differences="Agent A used existing utilities, Agent B reimplemented",
        ranking=["auggie:sonnet4.5", "claude-code:claude-sonnet-4-5"],
    )
    
    assert analysis.best_agent == "auggie:sonnet4.5"
    assert len(analysis.ranking) == 2


def test_cross_agent_judge():
    """Test CrossAgentJudge model."""
    scores1 = Scores(
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
    )
    
    scores2 = Scores(
        correctness=0.6,
        completeness=0.7,
        code_reuse=0.8,
        best_practices=0.75,
        unsolicited_docs=1.0,
    )
    
    result1 = AgentResult(
        runner="auggie",
        model="sonnet4.5",
        edit_run_id="abc123",
        status="success",
        elapsed_ms=45000,
        patch_unified="diff1",
        scores=scores1,
        aggregate=0.85,
    )
    
    result2 = AgentResult(
        runner="claude-code",
        model="claude-sonnet-4-5",
        edit_run_id="def456",
        status="success",
        elapsed_ms=50000,
        patch_unified="diff2",
        scores=scores2,
        aggregate=0.77,
    )
    
    analysis = ComparativeAnalysis(
        summary="Agent 1 performed better",
        best_agent="auggie:sonnet4.5",
        best_agent_reasoning="Higher scores across all metrics",
        approach_differences="Different implementation strategies",
        ranking=["auggie:sonnet4.5", "claude-code:claude-sonnet-4-5"],
    )
    
    judge = CrossAgentJudge(
        repo_url="https://github.com/elastic/elasticsearch.git",
        pr_number=114869,
        base_commit="abc123",
        head_commit="def456",
        task_instructions="Fix the bug",
        ground_truth_diff="diff --git...",
        judge_mode="llm",
        judge_model="claude-sonnet-4-5",
        test_label="v0",
        agent_results=[result1, result2],
        comparative_analysis=analysis,
        timestamp="2025-11-06T00:00:00",
        analysis_run_id="xyz789",
    )

    assert judge.pr_number == 114869
    assert len(judge.agent_results) == 2
    assert judge.comparative_analysis.best_agent == "auggie:sonnet4.5"
    assert judge.judge_mode == "llm"


def test_cross_agent_judge_serialization():
    """Test that CrossAgentJudge can be serialized to JSON."""
    scores = Scores(
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
    )
    
    result = AgentResult(
        runner="auggie",
        model="sonnet4.5",
        edit_run_id="abc123",
        status="success",
        elapsed_ms=45000,
        patch_unified="diff",
        scores=scores,
        aggregate=0.85,
    )
    
    judge = CrossAgentJudge(
        repo_url="https://github.com/elastic/elasticsearch.git",
        pr_number=114869,
        base_commit="abc123",
        head_commit="def456",
        task_instructions="Fix the bug",
        ground_truth_diff="diff",
        judge_mode="llm",
        judge_model="gpt-4",
        agent_results=[result],
        timestamp="2025-11-06T00:00:00",
        analysis_run_id="xyz789",
    )
    
    # Serialize to JSON
    json_str = judge.model_dump_json(indent=2)
    
    # Deserialize back
    data = json.loads(json_str)
    judge_restored = CrossAgentJudge(**data)
    
    assert judge_restored.pr_number == 114869
    assert len(judge_restored.agent_results) == 1
    assert judge_restored.agent_results[0].runner == "auggie"

