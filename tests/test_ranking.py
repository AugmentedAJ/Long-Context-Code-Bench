"""Tests for head-to-head ranking utilities."""

from long_context_bench.models import AgentVsHumanDecision, PairwiseJudgeDecision
from long_context_bench.ranking import (
    compute_win_loss_matrix,
    compute_elo_ratings,
    compute_win_loss_matrix_from_scores,
    compute_elo_ratings_from_scores,
    rank_agents,
)


def _make_decision(agent_a: str, agent_b: str, winner: str) -> PairwiseJudgeDecision:
    """Helper to construct a minimal PairwiseJudgeDecision."""

    return PairwiseJudgeDecision(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=115001,
        submission_a_id=agent_a,
        submission_b_id=agent_b,
        winner=winner,
        timestamp="2025-01-01T00:00:00",
    )


def _make_agent_decision(agent_id: str, aggregate: float) -> AgentVsHumanDecision:
    """Helper to construct a minimal AgentVsHumanDecision."""

    return AgentVsHumanDecision(
        repo_url="https://github.com/elastic/elasticsearch",
        pr_number=115001,
        agent_id=agent_id,
        correctness=aggregate,
        completeness=aggregate,
        code_reuse=aggregate,
        best_practices=aggregate,
        unsolicited_docs=1.0,
        matches_human=aggregate,
        aggregate=aggregate,
        timestamp="2025-01-01T00:00:00",
    )


def test_compute_win_loss_matrix_simple():
    """Basic sanity check for win/loss matrix construction."""

    decisions = [
        _make_decision("agentA", "agentB", "A"),  # A beats B
        _make_decision("agentA", "agentC", "B"),  # C beats A
        _make_decision("agentB", "agentC", "tie"),  # B ties C
    ]

    matrix = compute_win_loss_matrix(decisions)

    assert matrix["agentA"]["agentB"]["wins"] == 1
    assert matrix["agentB"]["agentA"]["losses"] == 1

    assert matrix["agentC"]["agentA"]["wins"] == 1
    assert matrix["agentA"]["agentC"]["losses"] == 1

    assert matrix["agentB"]["agentC"]["ties"] == 1
    assert matrix["agentC"]["agentB"]["ties"] == 1


def test_compute_elo_ratings_and_rank_agents():
    """Elo ratings and ranking should agree that agentA is best."""

    decisions = [
        _make_decision("agentA", "agentB", "A"),
        _make_decision("agentA", "agentC", "A"),
        _make_decision("agentB", "agentC", "B"),
    ]

    elo = compute_elo_ratings(decisions)
    assert set(elo.keys()) == {"agentA", "agentB", "agentC"}

    ranks_elo = rank_agents(decisions, method="elo")
    ranks_win_loss = rank_agents(decisions, method="win_loss")

    assert ranks_elo[0] == "agentA"
    assert ranks_win_loss[0] == "agentA"


def test_compute_win_loss_matrix_from_scores():
    """Test score-based win/loss matrix construction."""

    decisions = [
        _make_agent_decision("agentA", 0.9),  # Best
        _make_agent_decision("agentB", 0.7),  # Middle
        _make_agent_decision("agentC", 0.5),  # Worst
    ]

    matrix = compute_win_loss_matrix_from_scores(decisions)

    # agentA should beat both B and C
    assert matrix["agentA"]["agentB"]["wins"] == 1
    assert matrix["agentA"]["agentC"]["wins"] == 1
    assert matrix["agentA"]["agentB"]["losses"] == 0
    assert matrix["agentA"]["agentC"]["losses"] == 0

    # agentB should lose to A but beat C
    assert matrix["agentB"]["agentA"]["losses"] == 1
    assert matrix["agentB"]["agentC"]["wins"] == 1

    # agentC should lose to both A and B
    assert matrix["agentC"]["agentA"]["losses"] == 1
    assert matrix["agentC"]["agentB"]["losses"] == 1


def test_compute_win_loss_matrix_from_scores_with_ties():
    """Test score-based win/loss matrix with ties."""

    decisions = [
        _make_agent_decision("agentA", 0.8),
        _make_agent_decision("agentB", 0.8),  # Tie with A
        _make_agent_decision("agentC", 0.5),
    ]

    matrix = compute_win_loss_matrix_from_scores(decisions)

    # agentA and agentB should tie
    assert matrix["agentA"]["agentB"]["ties"] == 1
    assert matrix["agentB"]["agentA"]["ties"] == 1

    # Both should beat C
    assert matrix["agentA"]["agentC"]["wins"] == 1
    assert matrix["agentB"]["agentC"]["wins"] == 1


def test_compute_elo_ratings_from_scores():
    """Test Elo ratings from score-based comparisons."""

    decisions = [
        _make_agent_decision("agentA", 0.9),
        _make_agent_decision("agentB", 0.7),
        _make_agent_decision("agentC", 0.5),
    ]

    elo = compute_elo_ratings_from_scores(decisions)

    assert set(elo.keys()) == {"agentA", "agentB", "agentC"}

    # agentA should have highest rating
    assert elo["agentA"] > elo["agentB"]
    assert elo["agentB"] > elo["agentC"]

