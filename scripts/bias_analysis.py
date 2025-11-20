#!/usr/bin/env python3
"""
Comprehensive bias analysis of v0 benchmark results.
Analyzes potential biases in agent performance, scoring, and evaluation.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich import box
import matplotlib.pyplot as plt
import seaborn as sns

console = Console()


def analyze_agent_bias(df):
    """Analyze potential biases between different agents."""
    console.print("\n[bold cyan]═══ AGENT BIAS ANALYSIS ═══[/bold cyan]\n")

    # Basic performance comparison
    agent_stats = (
        df.groupby("runner")
        .agg(
            {
                "aggregate": ["mean", "std", "min", "max"],
                "correctness": ["mean", "std"],
                "completeness": ["mean", "std"],
                "elapsed_ms": ["mean", "std"],
                "success": "mean",
            }
        )
        .round(3)
    )

    console.print("[bold]Agent Performance Statistics:[/bold]")
    print(agent_stats)

    # Success rate analysis
    success_rates = df.groupby("runner")["success"].mean()
    console.print(f"\n[bold]Success Rates:[/bold]")
    for agent, rate in success_rates.items():
        console.print(f"  {agent}: {rate:.3f}")

    # Score distribution analysis
    console.print(f"\n[bold]Score Distribution Analysis:[/bold]")
    for runner in df["runner"].unique():
        agent_data = df[df["runner"] == runner]["aggregate"]
        console.print(f"\n{runner.upper()}:")
        console.print(f"  Mean: {agent_data.mean():.3f}")
        console.print(f"  Std:  {agent_data.std():.3f}")
        console.print(f"  Min:  {agent_data.min():.3f}")
        console.print(f"  Max:  {agent_data.max():.3f}")
        console.print(f"  Skew: {agent_data.skew():.3f}")
        console.print(f"  Kurt: {agent_data.kurtosis():.3f}")


def analyze_task_difficulty_bias(df):
    """Analyze if certain tasks are systematically harder/easier for specific agents."""
    console.print("\n[bold cyan]═══ TASK DIFFICULTY BIAS ANALYSIS ═══[/bold cyan]\n")

    # Calculate task difficulty as average performance across agents
    task_difficulty = df.groupby("pr_id")["aggregate"].mean().sort_values()

    console.print("[bold]Task Difficulty Ranking (by average performance):[/bold]")
    for i, (pr_id, score) in enumerate(task_difficulty.head(10).items()):
        console.print(f"  {i + 1}. {pr_id}: {score:.3f}")

    console.print("\n[bold]Hardest Tasks (bottom 10):[/bold]")
    for i, (pr_id, score) in enumerate(task_difficulty.tail(10).items()):
        console.print(f"  {i + 1}. {pr_id}: {score:.3f}")

    # Check if any agent consistently performs better/worse on difficult tasks
    difficult_tasks = task_difficulty.tail(10).index.tolist()
    easy_tasks = task_difficulty.head(10).index.tolist()

    console.print(f"\n[bold]Performance on Difficult Tasks:[/bold]")
    difficult_df = df[df["pr_id"].isin(difficult_tasks)]
    for runner in df["runner"].unique():
        runner_difficult = difficult_df[difficult_df["runner"] == runner]["aggregate"].mean()
        runner_overall = df[df["runner"] == runner]["aggregate"].mean()
        console.print(
            f"  {runner}: difficult={runner_difficult:.3f}, overall={runner_overall:.3f}, diff={runner_difficult - runner_overall:.3f}"
        )

    console.print(f"\n[bold]Performance on Easy Tasks:[/bold]")
    easy_df = df[df["pr_id"].isin(easy_tasks)]
    for runner in df["runner"].unique():
        runner_easy = easy_df[easy_df["runner"] == runner]["aggregate"].mean()
        runner_overall = df[df["runner"] == runner]["aggregate"].mean()
        console.print(
            f"  {runner}: easy={runner_easy:.3f}, overall={runner_overall:.3f}, diff={runner_easy - runner_overall:.3f}"
        )


def analyze_scoring_bias(df):
    """Analyze potential biases in scoring dimensions."""
    console.print("\n[bold cyan]═══ SCORING BIAS ANALYSIS ═══[/bold cyan]\n")

    # Correlation between scoring dimensions
    score_cols = [
        "correctness",
        "completeness",
        "code_reuse",
        "best_practices",
        "unsolicited_docs",
        "aggregate",
    ]

    console.print("[bold]Scoring Dimension Correlations:[/bold]")
    corr_matrix = df[score_cols].corr()
    print(corr_matrix.round(3))

    # Check if any agent gets systematically higher/lower scores in specific dimensions
    for score_col in ["correctness", "completeness", "code_reuse", "best_practices"]:
        console.print(f"\n[bold]{score_col.upper()} Score Analysis:[/bold]")
        score_stats = df.groupby("runner")[score_col].agg(["mean", "std", "min", "max"])
        print(score_stats.round(3))


def analyze_time_bias(df):
    """Analyze potential time-based biases."""
    console.print("\n[bold cyan]═══ TIME BIAS ANALYSIS ═══[/bold cyan]\n")

    # Time vs performance correlation
    df["elapsed_sec"] = df["elapsed_ms"] / 1000

    console.print("[bold]Time vs Performance Correlation:[/bold]")
    time_corr = df[["elapsed_sec", "aggregate", "correctness", "completeness"]].corr()
    print(time_corr.round(3))

    # Performance by time quartiles
    df["time_quartile"] = pd.qcut(df["elapsed_sec"], q=4, labels=["Q1", "Q2", "Q3", "Q4"])

    console.print(f"\n[bold]Performance by Time Quartiles:[/bold]")
    time_perf = df.groupby("time_quartile")["aggregate"].agg(["mean", "std", "count"])
    print(time_perf.round(3))

    # Agent performance by time
    console.print(f"\n[bold]Agent Performance by Time Quartiles:[/bold]")
    agent_time_perf = df.groupby(["runner", "time_quartile"])["aggregate"].mean().unstack()
    print(agent_time_perf.round(3))


def analyze_consistency_bias(df):
    """Analyze consistency of performance across tasks."""
    console.print("\n[bold cyan]═══ CONSISTENCY BIAS ANALYSIS ═══[/bold cyan]\n")

    # Calculate coefficient of variation for each agent
    consistency = df.groupby("runner")["aggregate"].agg(["mean", "std"]).round(3)
    consistency["cv"] = consistency["std"] / consistency["mean"]

    console.print("[bold]Agent Consistency (Coefficient of Variation):[/bold]")
    print(consistency)

    # Best and worst performance ranges
    performance_range = df.groupby("runner")["aggregate"].agg(["min", "max"]).round(3)
    performance_range["range"] = performance_range["max"] - performance_range["min"]

    console.print(f"\n[bold]Performance Range:[/bold]")
    print(performance_range)


def detect_outliers(df):
    """Detect potential outliers that might indicate bias."""
    console.print("\n[bold cyan]═══ OUTLIER ANALYSIS ═══[/bold cyan]\n")

    # Find tasks with largest performance differences between agents
    pivot_df = df.pivot(index="pr_id", columns="runner", values="aggregate")

    # Calculate max difference between any two agents for each task
    pivot_df["max_diff"] = pivot_df.max(axis=1) - pivot_df.min(axis=1)

    console.print("[bold]Tasks with Largest Performance Differences:[/bold]")
    high_diff_tasks = pivot_df.nlargest(10, "max_diff")
    for pr_id, row in high_diff_tasks.iterrows():
        console.print(
            f"  {pr_id}: range={row['max_diff']:.3f}, auggie={row.get('auggie', 'N/A'):.3f}, claude-code={row.get('claude-code', 'N/A'):.3f}, factory={row.get('factory', 'N/A'):.3f}"
        )

    # Find agents with most outlier performances
    z_scores = np.abs((df["aggregate"] - df["aggregate"].mean()) / df["aggregate"].std())
    outliers = df[z_scores > 2]

    console.print(f"\n[bold]Outlier Performances (|z-score| > 2):[/bold]")
    console.print(f"Total outliers: {len(outliers)}")

    outlier_stats = outliers.groupby("runner").size()
    console.print("Outliers by agent:")
    for agent, count in outlier_stats.items():
        total_agent_tasks = len(df[df["runner"] == agent])
        console.print(f"  {agent}: {count}/{total_agent_tasks} ({count / total_agent_tasks:.1%})")


def analyze_model_bias(df):
    """Analyze bias related to different models used."""
    console.print("\n[bold cyan]═══ MODEL BIAS ANALYSIS ═══[/bold cyan]\n")

    # Different models used: sonnet4.5, claude-sonnet-4-5, claude-sonnet-4-5-20250929
    model_stats = (
        df.groupby("model")
        .agg(
            {
                "aggregate": ["mean", "std", "count"],
                "correctness": "mean",
                "completeness": "mean",
                "elapsed_ms": "mean",
            }
        )
        .round(3)
    )

    console.print("[bold]Performance by Model:[/bold]")
    print(model_stats)

    # Model vs runner analysis
    console.print(f"\n[bold]Model-Runner Performance:[/bold]")
    model_runner_stats = (
        df.groupby(["model", "runner"]).agg({"aggregate": ["mean", "count"]}).round(3)
    )
    print(model_runner_stats)


def main():
    # Load the detailed analysis data
    df = pd.read_csv("output/v0_detailed_analysis.csv")

    console.print("[bold cyan]COMPREHENSIVE BIAS ANALYSIS[/bold cyan]")
    console.print("=" * 60)

    # Run all bias analyses
    analyze_agent_bias(df)
    analyze_task_difficulty_bias(df)
    analyze_scoring_bias(df)
    analyze_time_bias(df)
    analyze_consistency_bias(df)
    detect_outliers(df)
    analyze_model_bias(df)

    console.print(f"\n[bold green]Bias analysis completed![/bold green]")


if __name__ == "__main__":
    main()
