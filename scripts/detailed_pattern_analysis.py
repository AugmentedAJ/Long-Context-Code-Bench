#!/usr/bin/env python3
"""Detailed pattern analysis of agent wins and losses."""

import json
import sys
from pathlib import Path
from collections import defaultdict, Counter
import re

def load_data():
    """Load the analysis data."""
    with open("output/agent_performance_analysis.json") as f:
        return json.load(f)

def extract_keywords(text: str) -> list:
    """Extract meaningful keywords from text."""
    # Common technical keywords
    keywords = []
    
    # Look for specific patterns
    patterns = {
        'deprecation': r'\b(deprecat\w*)\b',
        'test': r'\b(test\w*)\b',
        'refactor': r'\b(refactor\w*)\b',
        'fix': r'\b(fix\w*|bug\w*)\b',
        'add': r'\b(add\w*|creat\w*)\b',
        'remove': r'\b(remov\w*|delet\w*)\b',
        'update': r'\b(updat\w*|modif\w*)\b',
        'config': r'\b(config\w*|setting\w*)\b',
        'api': r'\b(api|endpoint\w*)\b',
        'database': r'\b(database|db|sql)\b',
        'async': r'\b(async\w*|await)\b',
        'error': r'\b(error\w*|exception\w*)\b',
        'validation': r'\b(validat\w*)\b',
        'migration': r'\b(migrat\w*)\b',
        'security': r'\b(security|auth\w*|permission\w*)\b',
    }
    
    text_lower = text.lower()
    for category, pattern in patterns.items():
        if re.search(pattern, text_lower):
            keywords.append(category)
    
    return keywords

def analyze_win_loss_patterns(data):
    """Analyze patterns in wins vs losses."""
    
    print("=" * 80)
    print("DETAILED WIN/LOSS PATTERN ANALYSIS")
    print("=" * 80)
    print()
    
    for agent_key in sorted(data['agent_stats'].keys()):
        print(f"\n{'=' * 80}")
        print(f"{agent_key}")
        print(f"{'=' * 80}\n")
        
        # Get tasks for this agent
        tasks = [t for t in data['prompt_analysis'] if t['agent'] == agent_key]
        wins = [t for t in tasks if t['is_winner']]
        losses = [t for t in tasks if not t['is_winner']]
        
        # Analyze task types
        print(f"Task Type Analysis:")
        print(f"-" * 80)
        
        win_keywords = Counter()
        loss_keywords = Counter()
        
        for task in wins:
            keywords = extract_keywords(task.get('llm_summary', '') + ' ' + task.get('rationale', ''))
            win_keywords.update(keywords)
        
        for task in losses:
            keywords = extract_keywords(task.get('llm_summary', '') + ' ' + task.get('rationale', ''))
            loss_keywords.update(keywords)
        
        print(f"\nMost common in WINS:")
        for keyword, count in win_keywords.most_common(10):
            print(f"  {keyword}: {count} ({count/len(wins)*100:.1f}%)")
        
        print(f"\nMost common in LOSSES:")
        for keyword, count in loss_keywords.most_common(10):
            print(f"  {keyword}: {count} ({count/len(losses)*100:.1f}%)")
        
        # Analyze complexity
        print(f"\n\nComplexity Analysis:")
        print(f"-" * 80)
        
        if wins:
            print(f"\nWINS (n={len(wins)}):")
            print(f"  Avg files changed: {sum(t['ground_truth_files'] for t in wins)/len(wins):.1f}")
            print(f"  Avg lines changed: {sum(t['ground_truth_lines'] for t in wins)/len(wins):.0f}")
            print(f"  Avg execution time: {sum(t['elapsed_ms'] for t in wins)/len(wins)/1000:.1f}s")
            print(f"  Avg score: {sum(t['aggregate'] for t in wins)/len(wins):.3f}")
        
        if losses:
            print(f"\nLOSSES (n={len(losses)}):")
            print(f"  Avg files changed: {sum(t['ground_truth_files'] for t in losses)/len(losses):.1f}")
            print(f"  Avg lines changed: {sum(t['ground_truth_lines'] for t in losses)/len(losses):.0f}")
            print(f"  Avg execution time: {sum(t['elapsed_ms'] for t in losses)/len(losses)/1000:.1f}s")
            print(f"  Avg score: {sum(t['aggregate'] for t in losses)/len(losses):.3f}")
        
        # Show specific examples
        print(f"\n\nTop 3 WINS (by score):")
        print(f"-" * 80)
        for task in sorted(wins, key=lambda t: t['aggregate'], reverse=True)[:3]:
            print(f"\nPR {task['pr_number']} (score: {task['aggregate']:.3f}):")
            print(f"  Files: {task['ground_truth_files']}, Lines: {task['ground_truth_lines']}")
            summary = task.get('llm_summary', 'No summary')
            if len(summary) > 200:
                summary = summary[:200] + "..."
            print(f"  Summary: {summary}")
        
        print(f"\n\nTop 3 LOSSES (by score difference from winner):")
        print(f"-" * 80)
        # For losses, we want to see the worst performances
        for task in sorted(losses, key=lambda t: t['aggregate'])[:3]:
            print(f"\nPR {task['pr_number']} (score: {task['aggregate']:.3f}):")
            print(f"  Files: {task['ground_truth_files']}, Lines: {task['ground_truth_lines']}")
            summary = task.get('llm_summary', 'No summary')
            if len(summary) > 200:
                summary = summary[:200] + "..."
            print(f"  Summary: {summary}")
            rationale = task.get('rationale', 'No rationale')
            if len(rationale) > 300:
                rationale = rationale[:300] + "..."
            print(f"  Why it lost: {rationale}")

def main():
    """Main entry point."""
    print("Loading analysis data...")
    data = load_data()
    
    analyze_win_loss_patterns(data)

if __name__ == '__main__':
    main()

