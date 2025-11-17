"""Tests for head-to-head ranking utilities."""

from long_context_bench.models import PairwiseJudgeDecision
from long_context_bench.ranking import (
    compute_win_loss_matrix,
    compute_elo_ratings,
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

