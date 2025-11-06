#!/usr/bin/env python3
"""
Comprehensive analysis of v0 benchmark results.
Analyzes performance differences between agents (Auggie, Claude Code, Factory).
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

def find_judge_dir_for_edit_run(output_dir: Path, edit_run_id: str):
    """Find the judge directory that contains results for a given edit_run_id."""
    judge_base = output_dir / 'judges' / 'deterministic' / 'default'

    # Search all judge run directories
    for judge_run_dir in judge_base.iterdir():
        if not judge_run_dir.is_dir():
            continue

        # Check if any judge.json in this directory has the matching edit_run_id
        for judge_file in judge_run_dir.glob("*/judge.json"):
            try:
                with open(judge_file) as f:
                    data = json.load(f)
                if data.get('edit_run_id') == edit_run_id:
                    return judge_run_dir
            except:
                continue

    return None


def load_all_results(output_dir: Path):
    """Load all judge and edit results for v0 test label."""

    agents = [
        ('auggie', 'sonnet4.5', 'a9463435'),
        ('claude-code', 'claude-sonnet-4-5', 'c7a3f90a'),
        ('factory', 'claude-sonnet-4-5-20250929', '074538b9')
    ]

    all_results = []

    for runner, model, edit_run_id in agents:
        console.print(f"\n[bold]Loading results for {runner}/{model}...[/bold]")

        # Load all edits for this agent
        edit_dir = output_dir / 'edits' / runner / model / edit_run_id
        if not edit_dir.exists():
            console.print(f"[yellow]Warning: Edit directory not found: {edit_dir}[/yellow]")
            continue

        pr_dirs = [d for d in edit_dir.iterdir() if d.is_dir()]
        console.print(f"  Found {len(pr_dirs)} PR results")

        # Find judge directory for this edit run
        judge_dir = find_judge_dir_for_edit_run(output_dir, edit_run_id)
        if not judge_dir:
            console.print(f"[yellow]  Warning: No judge directory found for edit_run_id {edit_run_id}[/yellow]")
            continue

        console.print(f"  Using judge directory: {judge_dir.name}")

        pr_count = 0
        for pr_dir in pr_dirs:
            pr_id = pr_dir.name

            # Load edit data
            edit_file = pr_dir / 'edit.json'
            if not edit_file.exists():
                continue

            with open(edit_file) as f:
                edit_data = json.load(f)

            # Find corresponding judge result
            judge_file = judge_dir / pr_id / 'judge.json'

            if not judge_file.exists():
                continue

            with open(judge_file) as f:
                judge_data = json.load(f)

            # Extract scores from judge data
            scores = judge_data.get('scores', {})

            result = {
                'runner': runner,
                'model': model,
                'run_id': edit_run_id,
                'pr_id': pr_id,
                'pr_number': judge_data.get('pr_number'),
                'correctness': scores.get('correctness', 0),
                'completeness': scores.get('completeness', 0),
                'code_reuse': scores.get('code_reuse', 0),
                'best_practices': scores.get('best_practices', 0),
                'unsolicited_docs': scores.get('unsolicited_docs', 0),
                'aggregate': judge_data.get('aggregate', 0),
                'elapsed_ms': edit_data.get('elapsed_ms', 0),
                'success': edit_data.get('success', False),
                'error': edit_data.get('error'),
            }
            all_results.append(result)
            pr_count += 1

        console.print(f"  Loaded {pr_count} judged results")

    return pd.DataFrame(all_results)


def print_summary_comparison(df):
    """Print high-level summary comparison."""
    console.print("\n[bold cyan]═══ SUMMARY COMPARISON ═══[/bold cyan]\n")
    
    table = Table(box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Auggie", style="green")
    table.add_column("Claude Code", style="blue")
    table.add_column("Factory", style="magenta")
    
    for runner in ['auggie', 'claude-code', 'factory']:
        agent_df = df[df['runner'] == runner]
        if len(agent_df) == 0:
            continue
    
    # Success rate
    auggie_success = df[df['runner'] == 'auggie']['success'].mean() * 100
    claude_success = df[df['runner'] == 'claude-code']['success'].mean() * 100
    factory_success = df[df['runner'] == 'factory']['success'].mean() * 100
    table.add_row("Success Rate", f"{auggie_success:.1f}%", f"{claude_success:.1f}%", f"{factory_success:.1f}%")
    
    # Aggregate score
    auggie_agg = df[df['runner'] == 'auggie']['aggregate'].mean()
    claude_agg = df[df['runner'] == 'claude-code']['aggregate'].mean()
    factory_agg = df[df['runner'] == 'factory']['aggregate'].mean()
    table.add_row("Mean Aggregate", f"{auggie_agg:.3f}", f"{claude_agg:.3f}", f"{factory_agg:.3f}")
    
    # Correctness
    auggie_corr = df[df['runner'] == 'auggie']['correctness'].mean()
    claude_corr = df[df['runner'] == 'claude-code']['correctness'].mean()
    factory_corr = df[df['runner'] == 'factory']['correctness'].mean()
    table.add_row("Mean Correctness", f"{auggie_corr:.3f}", f"{claude_corr:.3f}", f"{factory_corr:.3f}")
    
    # Completeness
    auggie_comp = df[df['runner'] == 'auggie']['completeness'].mean()
    claude_comp = df[df['runner'] == 'claude-code']['completeness'].mean()
    factory_comp = df[df['runner'] == 'factory']['completeness'].mean()
    table.add_row("Mean Completeness", f"{auggie_comp:.3f}", f"{claude_comp:.3f}", f"{factory_comp:.3f}")
    
    # Code reuse
    auggie_reuse = df[df['runner'] == 'auggie']['code_reuse'].mean()
    claude_reuse = df[df['runner'] == 'claude-code']['code_reuse'].mean()
    factory_reuse = df[df['runner'] == 'factory']['code_reuse'].mean()
    table.add_row("Mean Code Reuse", f"{auggie_reuse:.3f}", f"{claude_reuse:.3f}", f"{factory_reuse:.3f}")
    
    # Unsolicited docs
    auggie_docs = df[df['runner'] == 'auggie']['unsolicited_docs'].mean()
    claude_docs = df[df['runner'] == 'claude-code']['unsolicited_docs'].mean()
    factory_docs = df[df['runner'] == 'factory']['unsolicited_docs'].mean()
    table.add_row("Mean Unsolicited Docs", f"{auggie_docs:.3f}", f"{claude_docs:.3f}", f"{factory_docs:.3f}")
    
    # Speed
    auggie_speed = df[df['runner'] == 'auggie']['elapsed_ms'].mean() / 1000
    claude_speed = df[df['runner'] == 'claude-code']['elapsed_ms'].mean() / 1000
    factory_speed = df[df['runner'] == 'factory']['elapsed_ms'].mean() / 1000
    table.add_row("Mean Time (sec)", f"{auggie_speed:.1f}", f"{claude_speed:.1f}", f"{factory_speed:.1f}")
    
    console.print(table)


def analyze_score_distribution(df):
    """Analyze distribution of scores."""
    console.print("\n[bold cyan]═══ SCORE DISTRIBUTION ANALYSIS ═══[/bold cyan]\n")
    
    for runner in ['auggie', 'claude-code', 'factory']:
        agent_df = df[df['runner'] == runner]
        if len(agent_df) == 0:
            continue
        
        console.print(f"\n[bold]{runner.upper()}:[/bold]")
        
        table = Table(box=box.SIMPLE)
        table.add_column("Percentile", style="cyan")
        table.add_column("Aggregate", justify="right")
        table.add_column("Correctness", justify="right")
        table.add_column("Completeness", justify="right")
        
        for p in [0, 25, 50, 75, 100]:
            agg = np.percentile(agent_df['aggregate'], p)
            corr = np.percentile(agent_df['correctness'], p)
            comp = np.percentile(agent_df['completeness'], p)
            table.add_row(f"p{p}", f"{agg:.3f}", f"{corr:.3f}", f"{comp:.3f}")
        
        console.print(table)


def analyze_best_worst_tasks(df):
    """Identify tasks where each agent performs best/worst."""
    console.print("\n[bold cyan]═══ BEST & WORST PERFORMING TASKS ═══[/bold cyan]\n")
    
    for runner in ['auggie', 'claude-code', 'factory']:
        agent_df = df[df['runner'] == runner].copy()
        if len(agent_df) == 0:
            continue
        
        console.print(f"\n[bold]{runner.upper()}:[/bold]")
        
        # Top 5 tasks
        top5 = agent_df.nlargest(5, 'aggregate')[['pr_id', 'aggregate', 'correctness', 'completeness']]
        console.print("\n[green]Top 5 Tasks:[/green]")
        for _, row in top5.iterrows():
            console.print(f"  {row['pr_id']}: agg={row['aggregate']:.3f}, corr={row['correctness']:.3f}, comp={row['completeness']:.3f}")
        
        # Bottom 5 tasks
        bottom5 = agent_df.nsmallest(5, 'aggregate')[['pr_id', 'aggregate', 'correctness', 'completeness']]
        console.print("\n[red]Bottom 5 Tasks:[/red]")
        for _, row in bottom5.iterrows():
            console.print(f"  {row['pr_id']}: agg={row['aggregate']:.3f}, corr={row['correctness']:.3f}, comp={row['completeness']:.3f}")


def analyze_head_to_head(df):
    """Compare agents on same tasks."""
    console.print("\n[bold cyan]═══ HEAD-TO-HEAD COMPARISON ═══[/bold cyan]\n")
    
    # Get common PRs across all agents
    auggie_prs = set(df[df['runner'] == 'auggie']['pr_id'])
    claude_prs = set(df[df['runner'] == 'claude-code']['pr_id'])
    factory_prs = set(df[df['runner'] == 'factory']['pr_id'])
    
    common_prs = auggie_prs & claude_prs & factory_prs
    console.print(f"Common PRs across all agents: {len(common_prs)}\n")
    
    # For each common PR, compare scores
    comparisons = []
    for pr_id in common_prs:
        auggie_score = df[(df['runner'] == 'auggie') & (df['pr_id'] == pr_id)]['aggregate'].values[0]
        claude_score = df[(df['runner'] == 'claude-code') & (df['pr_id'] == pr_id)]['aggregate'].values[0]
        factory_score = df[(df['runner'] == 'factory') & (df['pr_id'] == pr_id)]['aggregate'].values[0]
        
        comparisons.append({
            'pr_id': pr_id,
            'auggie': auggie_score,
            'claude-code': claude_score,
            'factory': factory_score,
            'auggie_vs_claude': auggie_score - claude_score,
            'auggie_vs_factory': auggie_score - factory_score,
            'factory_vs_claude': factory_score - claude_score,
        })
    
    comp_df = pd.DataFrame(comparisons)
    
    # Win rates
    auggie_wins_claude = (comp_df['auggie_vs_claude'] > 0).sum()
    auggie_wins_factory = (comp_df['auggie_vs_factory'] > 0).sum()
    factory_wins_claude = (comp_df['factory_vs_claude'] > 0).sum()
    
    console.print(f"[green]Auggie wins vs Claude Code:[/green] {auggie_wins_claude}/{len(common_prs)} ({auggie_wins_claude/len(common_prs)*100:.1f}%)")
    console.print(f"[green]Auggie wins vs Factory:[/green] {auggie_wins_factory}/{len(common_prs)} ({auggie_wins_factory/len(common_prs)*100:.1f}%)")
    console.print(f"[magenta]Factory wins vs Claude Code:[/magenta] {factory_wins_claude}/{len(common_prs)} ({factory_wins_claude/len(common_prs)*100:.1f}%)")
    
    # Tasks where Auggie significantly outperforms
    console.print("\n[bold]Tasks where Auggie significantly outperforms Claude Code (>0.3 diff):[/bold]")
    auggie_strong = comp_df[comp_df['auggie_vs_claude'] > 0.3].nlargest(10, 'auggie_vs_claude')
    for _, row in auggie_strong.iterrows():
        console.print(f"  {row['pr_id']}: Auggie={row['auggie']:.3f}, Claude={row['claude-code']:.3f}, Diff={row['auggie_vs_claude']:.3f}")
    
    # Tasks where Claude Code significantly outperforms
    console.print("\n[bold]Tasks where Claude Code significantly outperforms Auggie (>0.3 diff):[/bold]")
    claude_strong = comp_df[comp_df['auggie_vs_claude'] < -0.3].nsmallest(10, 'auggie_vs_claude')
    for _, row in claude_strong.iterrows():
        console.print(f"  {row['pr_id']}: Auggie={row['auggie']:.3f}, Claude={row['claude-code']:.3f}, Diff={row['auggie_vs_claude']:.3f}")


def main():
    output_dir = Path('output')
    
    console.print("[bold cyan]Loading v0 benchmark results...[/bold cyan]")
    df = load_all_results(output_dir)
    
    if len(df) == 0:
        console.print("[red]No results found![/red]")
        return
    
    console.print(f"\n[green]✓ Loaded {len(df)} results[/green]")
    console.print(f"  Auggie: {len(df[df['runner'] == 'auggie'])} tasks")
    console.print(f"  Claude Code: {len(df[df['runner'] == 'claude-code'])} tasks")
    console.print(f"  Factory: {len(df[df['runner'] == 'factory'])} tasks")
    
    # Run analyses
    print_summary_comparison(df)
    analyze_score_distribution(df)
    analyze_best_worst_tasks(df)
    analyze_head_to_head(df)
    
    # Save detailed results
    output_file = Path('output/v0_detailed_analysis.csv')
    df.to_csv(output_file, index=False)
    console.print(f"\n[green]✓ Detailed results saved to {output_file}[/green]")


if __name__ == '__main__':
    main()

