"""Ranking utilities for head-to-head comparisons.

Implements win/loss matrices and Elo-style ratings over AgentVsHumanDecision
and PairwiseJudgeDecision artifacts, as described in plan.md.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Union

from long_context_bench.models import AgentVsHumanDecision, PairwiseJudgeDecision


def compute_win_loss_matrix_from_scores(
    decisions: List[AgentVsHumanDecision],
) -> Dict[str, Dict[str, Dict[str, int]]]:
    """Compute head-to-head win/loss/tie counts by comparing agent scores.

    Each agent is compared against every other agent based on their aggregate scores.

    Returns a nested mapping of the form:
        matrix[agent_id][opponent_id] -> {"wins", "losses", "ties"}
    where the counts are from the perspective of ``agent_id``.
    """

    matrix: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0})
    )

    # Create a mapping of agent_id to aggregate score
    score_map: Dict[str, float] = {
        decision.agent_id: decision.aggregate for decision in decisions
    }

    # Compare each agent against every other agent
    for decision_i in decisions:
        agent_i = decision_i.agent_id
        score_i = score_map[agent_i]

        for decision_j in decisions:
            agent_j = decision_j.agent_id
            if agent_i == agent_j:
                continue  # Don't compare agent to itself

            score_j = score_map[agent_j]

            # Ensure entry exists
            _ = matrix[agent_i][agent_j]

            # Determine win/loss/tie based on score comparison
            if abs(score_i - score_j) < 1e-3:
                matrix[agent_i][agent_j]["ties"] += 1
            elif score_i > score_j:
                matrix[agent_i][agent_j]["wins"] += 1
            else:
                matrix[agent_i][agent_j]["losses"] += 1

    # Convert nested defaultdicts back to plain dicts for serialization
    return {
        agent_id: {opponent_id: stats for opponent_id, stats in opponents.items()}
        for agent_id, opponents in matrix.items()
    }


def compute_elo_ratings_from_scores(
    decisions: List[AgentVsHumanDecision],
    initial_rating: float = 1500.0,
    k_factor: float = 32.0,
) -> Dict[str, float]:
    """Compute Elo ratings by treating score comparisons as pairwise matches.

    Each pair of agents is treated as a match where the agent with the higher
    aggregate score wins. Ties occur when scores are within epsilon.
    """

    ratings: Dict[str, float] = {}

    def _get_rating(agent_id: str) -> float:
        if agent_id not in ratings:
            ratings[agent_id] = initial_rating
        return ratings[agent_id]

    # Create a mapping of agent_id to aggregate score
    score_map: Dict[str, float] = {
        decision.agent_id: decision.aggregate for decision in decisions
    }

    # Process all pairwise comparisons
    for i, decision_i in enumerate(decisions):
        for j, decision_j in enumerate(decisions):
            if i >= j:
                continue  # Only process each pair once

            agent_i = decision_i.agent_id
            agent_j = decision_j.agent_id
            score_i = score_map[agent_i]
            score_j = score_map[agent_j]

            ra = _get_rating(agent_i)
            rj = _get_rating(agent_j)

            # Expected scores
            expected_i = 1.0 / (1.0 + 10 ** ((rj - ra) / 400.0))
            expected_j = 1.0 - expected_i

            # Actual scores based on aggregate comparison
            if abs(score_i - score_j) < 1e-3:
                actual_i = actual_j = 0.5  # Tie
            elif score_i > score_j:
                actual_i, actual_j = 1.0, 0.0  # i wins
            else:
                actual_i, actual_j = 0.0, 1.0  # j wins

            # Update ratings
            ratings[agent_i] = ra + k_factor * (actual_i - expected_i)
            ratings[agent_j] = rj + k_factor * (actual_j - expected_j)

    return ratings


def compute_win_loss_matrix(
    comparisons: List[PairwiseJudgeDecision],
) -> Dict[str, Dict[str, Dict[str, int]]]:
    """Compute head-to-head win/loss/tie counts for each agent pair.

    Returns a nested mapping of the form:
        matrix[agent_id][opponent_id] -> {"wins", "losses", "ties"}
    where the counts are from the perspective of ``agent_id``.
    """

    matrix: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0})
    )

    for decision in comparisons:
        a = decision.submission_a_id
        b = decision.submission_b_id

        # Ensure entries exist
        _ = matrix[a][b]
        _ = matrix[b][a]

        winner = decision.winner.lower()
        if winner == "a":
            matrix[a][b]["wins"] += 1
            matrix[b][a]["losses"] += 1
        elif winner == "b":
            matrix[a][b]["losses"] += 1
            matrix[b][a]["wins"] += 1
        else:
            matrix[a][b]["ties"] += 1
            matrix[b][a]["ties"] += 1

    # Convert nested defaultdicts back to plain dicts for serialization
    return {
        agent_id: {opponent_id: stats for opponent_id, stats in opponents.items()}
        for agent_id, opponents in matrix.items()
    }


def compute_elo_ratings(
    comparisons: List[PairwiseJudgeDecision],
    initial_rating: float = 1500.0,
    k_factor: float = 32.0,
) -> Dict[str, float]:
    """Compute Elo ratings from a list of pairwise decisions.

    Each PairwiseJudgeDecision is treated as a single game between
    submission_a_id and submission_b_id. Ties count as 0.5 for both sides.
    """

    ratings: Dict[str, float] = {}

    def _get_rating(agent_id: str) -> float:
        if agent_id not in ratings:
            ratings[agent_id] = initial_rating
        return ratings[agent_id]

    for decision in comparisons:
        a = decision.submission_a_id
        b = decision.submission_b_id

        ra = _get_rating(a)
        rb = _get_rating(b)

        # Expected scores
        expected_a = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
        expected_b = 1.0 - expected_a

        winner = decision.winner.lower()
        if winner == "a":
            score_a, score_b = 1.0, 0.0
        elif winner == "b":
            score_a, score_b = 0.0, 1.0
        else:
            score_a = score_b = 0.5

        ratings[a] = ra + k_factor * (score_a - expected_a)
        ratings[b] = rb + k_factor * (score_b - expected_b)

    return ratings


def rank_agents(
    comparisons: List[PairwiseJudgeDecision],
    method: str = "elo",
) -> List[str]:
    """Rank agents based on pairwise decisions.

    Args:
        comparisons: List of PairwiseJudgeDecision objects.
        method: "elo" (default) or "win_loss".

    Returns:
        Ordered list of agent IDs from best to worst.
    """

    if not comparisons:
        return []

    if method == "win_loss":
        matrix = compute_win_loss_matrix(comparisons)
        scores: Dict[str, tuple[float, int, int]] = {}
        for agent_id, opponents in matrix.items():
            wins = sum(v["wins"] for v in opponents.values())
            losses = sum(v["losses"] for v in opponents.values())
            ties = sum(v["ties"] for v in opponents.values())
            matches = wins + losses + ties
            if matches == 0:
                score = 0.0
            else:
                score = (wins + 0.5 * ties) / matches
            # Store tuple for stable sorting: (score, wins, -losses)
            scores[agent_id] = (score, wins, -losses)

        # Sort by composite score tuple
        return [
            agent_id
            for agent_id, _ in sorted(
                scores.items(), key=lambda item: item[1], reverse=True
            )
        ]

    # Default: Elo-based ranking
    ratings = compute_elo_ratings(comparisons)
    return [
        agent_id
        for agent_id, _ in sorted(ratings.items(), key=lambda item: item[1], reverse=True)
    ]

