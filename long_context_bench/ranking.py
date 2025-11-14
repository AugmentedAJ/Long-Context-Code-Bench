"""Ranking utilities for head-to-head comparisons.

Implements win/loss matrices and Elo-style ratings over PairwiseJudgeDecision
artifacts, as described in plan.md.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from long_context_bench.models import PairwiseJudgeDecision


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

