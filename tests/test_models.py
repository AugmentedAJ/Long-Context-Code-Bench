"""Tests for data models."""

import pytest
from long_context_bench.models import (
    Sample, SampleStats, Edit, Judge, Scores,
    EditRunManifest, JudgeRunManifest, AggregateSummary,
    AgentResult, AgentVsHumanDecision, PairwiseJudgeDecision, HeadToHeadAgentStats,
    HeadToHeadPRResult, HeadToHeadAgentSummary, HeadToHeadGlobalSummary,
)


def test_sample_stats():
    """Test SampleStats model."""
    stats = SampleStats(
        files_changed=5,
        lines_added=100,
        lines_deleted=50,
        total_diff_hunks=10,
        context_size_bytes=10000,
        truncated=False,
    )
    assert stats.files_changed == 5
    assert stats.lines_added == 100
    assert stats.truncated is False


def test_sample():
    """Test Sample model."""
    stats = SampleStats(
        files_changed=5,
        lines_added=100,
        lines_deleted=50,
        total_diff_hunks=10,
        context_size_bytes=10000,
        truncated=False,
    )

    sample = Sample(
        dataset_version="v0",
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=115001,
        base_commit="abc123",
        head_commit="def456",
        task_instructions="Fix bug in search",
        stats=stats,
    )

    assert sample.dataset_version == "v0"
    assert sample.pr_number == 115001
    assert sample.stats.files_changed == 5


def test_edit():
    """Test Edit model."""
    edit = Edit(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=115001,
        base_commit="abc123",
        runner="auggie",
        model="claude-sonnet-4",
        timeout_s=1800,
        status="success",
        elapsed_ms=30000,
        patch_unified="diff --git a/file.py b/file.py\n...",
        logs_path="logs.jsonl",
        errors=[],
        edit_run_id="test123",
    )

    assert edit.status == "success"
    assert edit.elapsed_ms == 30000
    assert edit.errors == []


def test_scores():
    """Test Scores model."""
    scores = Scores(
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
    )

    assert scores.correctness == 0.8
    assert scores.completeness == 0.9

    # Test bounds
    with pytest.raises(ValueError):
        Scores(
            correctness=1.5,  # Out of bounds
            completeness=0.9,
            code_reuse=0.7,
            best_practices=0.85,
            unsolicited_docs=1.0,
        )


def test_judge():
    """Test Judge model."""
    scores = Scores(
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
    )

    judge = Judge(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=115001,
        base_commit="abc123",
        head_commit="def456",
        judge_mode="deterministic",
        judge_model=None,
        scores=scores,
        aggregate=0.85,
        rationale=None,
    )

    assert judge.judge_mode == "deterministic"
    assert judge.aggregate == 0.85
    assert judge.scores.correctness == 0.8

def test_edit_run_manifest_with_test_label():
    """Test EditRunManifest with test_label."""
    manifest = EditRunManifest(
        dataset_version="v0",
        harness_version="0.1.0",
        runner="auggie",
        model="claude-sonnet-4.5",
        os="Linux",
        python_version="3.11.0",
        timeout_s=1800,
        concurrency=1,
        total_shards=1,
        shard_index=0,
        flags={},
        timestamp="2025-01-01T00:00:00",
        edit_run_id="abc123",
        test_label="sonnet-4.5-comparison",
    )

    assert manifest.test_label == "sonnet-4.5-comparison"
    assert manifest.runner == "auggie"
    assert manifest.model == "claude-sonnet-4.5"


def test_judge_run_manifest_with_test_label():
    """Test JudgeRunManifest with test_label."""
    manifest = JudgeRunManifest(
        harness_version="0.1.0",
        judge_mode="deterministic",
        edit_run_ids=["abc123"],
        os="Linux",
        python_version="3.11.0",
        timestamp="2025-01-01T00:00:00",
        judge_run_id="def456",
        test_label="sonnet-4.5-comparison",
    )

    assert manifest.test_label == "sonnet-4.5-comparison"
    assert manifest.judge_mode == "deterministic"


def test_aggregate_summary_with_test_label():
    """Test AggregateSummary with test_label and runner/model."""
    summary = AggregateSummary(
        run_id="abc123",
        total_samples=10,
        successful_samples=8,
        failed_samples=2,
        skipped_samples=0,
        success_rate=0.8,
        mean_correctness=0.75,
        mean_completeness=0.80,
        mean_code_reuse=0.70,
        mean_best_practices=0.85,
        mean_unsolicited_docs=1.0,
        mean_aggregate=0.78,
        std_aggregate=0.05,
        mean_elapsed_ms=30000,
        tasks_per_hour=120.0,
        test_label="sonnet-4.5-comparison",
        runner="auggie",
        model="claude-sonnet-4.5",
    )

    assert summary.test_label == "sonnet-4.5-comparison"
    assert summary.runner == "auggie"
    assert summary.model == "claude-sonnet-4.5"
    assert summary.mean_aggregate == 0.78



def test_agent_vs_human_decision_model():
    """Test AgentVsHumanDecision model construction."""
    decision = AgentVsHumanDecision(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=115001,
        agent_id="runner1:model1:run1",
        judge_model="anthropic/claude-3-5-sonnet-20241022",
        judge_runner="claude-code",
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
        matches_human=0.75,
        aggregate=0.85,
        rationale="Good implementation overall.",
        notes="Minor issues with edge cases",
        timestamp="2025-01-01T00:00:00",
        codebase_context_files=["src/main.py"],
    )

    assert decision.agent_id == "runner1:model1:run1"
    assert decision.correctness == 0.8
    assert decision.aggregate == 0.85
    assert decision.matches_human == 0.75


def test_pairwise_judge_decision_model():
    """Test PairwiseJudgeDecision model construction (deprecated)."""
    decision = PairwiseJudgeDecision(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=115001,
        submission_a_id="runner1:model1:run1",
        submission_b_id="runner2:model2:run2",
        judge_model="anthropic/claude-3-5-sonnet-20241022",
        judge_runner=None,
        order_seed=123,
        winner="A",
        correctness_preference="A",
        completeness_preference="A",
        code_quality_preference="B",
        integration_preference="tie",
        raw_scores={"A": {"correctness": 0.9}, "B": {"correctness": 0.7}},
        rationale="A is more correct overall.",
        timestamp="2025-01-01T00:00:00",
        codebase_context_files=["src/main.py"],
    )

    assert decision.winner == "A"
    assert decision.submission_a_id.endswith("run1")
    assert "A" in decision.raw_scores


def test_head_to_head_pr_result_model():
    """Test HeadToHeadPRResult model wiring."""
    scores = Scores(
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
    )

    agent_result = AgentResult(
        runner="runner1",
        model="model1",
        edit_run_id="run1",
        status="success",
        elapsed_ms=1234,
        patch_unified="diff --git a/file.py b/file.py\n...",
        scores=scores,
        aggregate=0.85,
        rationale="Looks good",
        llm_rating=0.9,
        llm_summary="Solid patch",
        errors=[],
        logs_path="logs.jsonl",
    )

    stats = HeadToHeadAgentStats(
        agent_id="runner1:model1:run1",
        wins=1,
        losses=0,
        ties=0,
    )

    agent_decision = AgentVsHumanDecision(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=115001,
        agent_id="runner1:model1:run1",
        judge_model="anthropic/claude-3-5-sonnet-20241022",
        judge_runner="claude-code",
        correctness=0.8,
        completeness=0.9,
        code_reuse=0.7,
        best_practices=0.85,
        unsolicited_docs=1.0,
        matches_human=0.75,
        aggregate=0.85,
        rationale="Good implementation.",
        timestamp="2025-01-01T00:00:00",
        codebase_context_files=None,
    )

    h2h = HeadToHeadPRResult(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=115001,
        base_commit="abc123",
        head_commit="def456",
        task_instructions="Fix bug in search",
        test_label="head-to-head-test",
        agent_results=[agent_result],
        agent_decisions=[agent_decision],
        agent_stats=[stats],
        head_to_head_run_id="h2h123",
        timestamp="2025-01-01T00:00:00",
    )

    dumped = h2h.model_dump()
    assert dumped["pr_number"] == 115001
    assert dumped["agent_stats"][0]["wins"] == 1
    assert dumped["agent_decisions"][0]["agent_id"] == "runner1:model1:run1"
    assert dumped["agent_decisions"][0]["aggregate"] == 0.85


def test_head_to_head_global_summary_model():
    """Test HeadToHeadGlobalSummary and HeadToHeadAgentSummary models."""
    agent_summary = HeadToHeadAgentSummary(
        agent_id="runner1:model1:run1",
        runner="runner1",
        model="model1",
        test_label="head-to-head-test",
        wins=3,
        losses=1,
        ties=0,
        matches=4,
        win_rate=0.75,
        elo_rating=1550.0,
        elo_uncertainty=None,
    )

    matrix = {
        "runner1:model1:run1": {
            "runner2:model2:run2": {"wins": 2, "losses": 1, "ties": 0}
        }
    }

    summary = HeadToHeadGlobalSummary(
        test_label="head-to-head-test",
        agents=[agent_summary],
        head_to_head_matrix=matrix,
    )

    assert summary.agents[0].win_rate == 0.75
    assert "runner2:model2:run2" in summary.head_to_head_matrix["runner1:model1:run1"]


