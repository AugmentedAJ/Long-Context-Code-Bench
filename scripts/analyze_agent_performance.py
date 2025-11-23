#!/usr/bin/env python3
"""Analyze agent performance patterns across all v1 judged PRs."""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

def load_cross_agent_data(output_dir: Path) -> List[Dict[str, Any]]:
    """Load all cross-agent analysis files."""
    ca_dir = output_dir / "cross_agent_analysis"
    results = []
    
    for file in sorted(ca_dir.glob("pr*.json")):
        try:
            with open(file) as f:
                data = json.load(f)
                results.append(data)
        except Exception as e:
            print(f"Error loading {file}: {e}", file=sys.stderr)
    
    return results

def analyze_agent_patterns(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze patterns in agent performance."""
    
    # Track metrics by agent
    agent_stats = defaultdict(lambda: {
        'total_tasks': 0,
        'wins': 0,
        'scores': [],
        'correctness': [],
        'completeness': [],
        'code_reuse': [],
        'best_practices': [],
        'unsolicited_docs': [],
        'llm_ratings': [],
        'tasks': []
    })
    
    # Track prompt characteristics
    prompt_analysis = []
    
    for pr_data in data:
        pr_number = pr_data['pr_number']
        task_instructions = pr_data.get('task_instructions', '')
        ground_truth = pr_data.get('ground_truth_diff', '')
        
        # Calculate task characteristics
        task_chars = {
            'pr_number': pr_number,
            'instruction_length': len(task_instructions),
            'instruction_words': len(task_instructions.split()),
            'ground_truth_lines': len(ground_truth.split('\n')) if ground_truth else 0,
            'ground_truth_files': ground_truth.count('diff --git') if ground_truth else 0,
        }
        
        best_agent = pr_data.get('comparative_analysis', {}).get('best_agent', '')
        
        for agent_result in pr_data.get('agent_results', []):
            agent_key = f"{agent_result['runner']}:{agent_result['model']}"
            stats = agent_stats[agent_key]
            
            stats['total_tasks'] += 1
            stats['scores'].append(agent_result['aggregate'])
            stats['correctness'].append(agent_result['scores']['correctness'])
            stats['completeness'].append(agent_result['scores']['completeness'])
            stats['code_reuse'].append(agent_result['scores']['code_reuse'])
            stats['best_practices'].append(agent_result['scores']['best_practices'])
            stats['unsolicited_docs'].append(agent_result['scores']['unsolicited_docs'])
            
            if agent_result.get('llm_rating'):
                stats['llm_ratings'].append(agent_result['llm_rating'])
            
            is_winner = (agent_key == best_agent)
            if is_winner:
                stats['wins'] += 1
            
            # Store task details
            task_detail = {
                **task_chars,
                'agent': agent_key,
                'aggregate': agent_result['aggregate'],
                'is_winner': is_winner,
                'rationale': agent_result.get('rationale', ''),
                'llm_summary': agent_result.get('llm_summary', ''),
                'status': agent_result['status'],
                'elapsed_ms': agent_result['elapsed_ms'],
            }
            stats['tasks'].append(task_detail)
            prompt_analysis.append(task_detail)
    
    return {
        'agent_stats': agent_stats,
        'prompt_analysis': prompt_analysis,
        'total_prs': len(data)
    }

def print_analysis(analysis: Dict[str, Any]):
    """Print detailed analysis."""
    
    print("=" * 80)
    print("AGENT PERFORMANCE ANALYSIS - V1 RESULTS")
    print("=" * 80)
    print()
    
    print(f"Total PRs analyzed: {analysis['total_prs']}")
    print()
    
    # Overall agent statistics
    print("=" * 80)
    print("OVERALL AGENT STATISTICS")
    print("=" * 80)
    print()
    
    for agent, stats in sorted(analysis['agent_stats'].items()):
        print(f"\n{agent}")
        print("-" * 80)
        print(f"  Total tasks: {stats['total_tasks']}")
        print(f"  Wins: {stats['wins']} ({stats['wins']/stats['total_tasks']*100:.1f}%)")
        print(f"  Avg aggregate score: {sum(stats['scores'])/len(stats['scores']):.3f}")
        print(f"  Avg correctness: {sum(stats['correctness'])/len(stats['correctness']):.3f}")
        print(f"  Avg completeness: {sum(stats['completeness'])/len(stats['completeness']):.3f}")
        print(f"  Avg code_reuse: {sum(stats['code_reuse'])/len(stats['code_reuse']):.3f}")
        print(f"  Avg best_practices: {sum(stats['best_practices'])/len(stats['best_practices']):.3f}")
        print(f"  Avg unsolicited_docs: {sum(stats['unsolicited_docs'])/len(stats['unsolicited_docs']):.3f}")
        if stats['llm_ratings']:
            print(f"  Avg LLM rating: {sum(stats['llm_ratings'])/len(stats['llm_ratings']):.3f}")
    
    print()
    print("=" * 80)
    print("WINS BY TASK CHARACTERISTICS")
    print("=" * 80)
    print()
    
    # Analyze wins by task characteristics
    for agent in sorted(analysis['agent_stats'].keys()):
        wins = [t for t in analysis['agent_stats'][agent]['tasks'] if t['is_winner']]
        losses = [t for t in analysis['agent_stats'][agent]['tasks'] if not t['is_winner']]
        
        if wins:
            print(f"\n{agent} - WINS ({len(wins)} tasks)")
            print("-" * 80)
            print(f"  Avg instruction length: {sum(t['instruction_length'] for t in wins)/len(wins):.0f} chars")
            print(f"  Avg instruction words: {sum(t['instruction_words'] for t in wins)/len(wins):.0f} words")
            print(f"  Avg ground truth lines: {sum(t['ground_truth_lines'] for t in wins)/len(wins):.0f}")
            print(f"  Avg ground truth files: {sum(t['ground_truth_files'] for t in wins)/len(wins):.1f}")
            print(f"  Avg score: {sum(t['aggregate'] for t in wins)/len(wins):.3f}")

        if losses:
            print(f"\n{agent} - LOSSES ({len(losses)} tasks)")
            print("-" * 80)
            print(f"  Avg instruction length: {sum(t['instruction_length'] for t in losses)/len(losses):.0f} chars")
            print(f"  Avg instruction words: {sum(t['instruction_words'] for t in losses)/len(losses):.0f} words")
            print(f"  Avg ground truth lines: {sum(t['ground_truth_lines'] for t in losses)/len(losses):.0f}")
            print(f"  Avg ground truth files: {sum(t['ground_truth_files'] for t in losses)/len(losses):.1f}")
            print(f"  Avg score: {sum(t['aggregate'] for t in losses)/len(losses):.3f}")

def main():
    """Main entry point."""
    output_dir = Path("output")

    print("Loading cross-agent analysis data...")
    data = load_cross_agent_data(output_dir)
    print(f"Loaded {len(data)} PR analyses")

    print("\nAnalyzing patterns...")
    analysis = analyze_agent_patterns(data)

    print_analysis(analysis)

    # Save detailed results
    output_file = Path("output/agent_performance_analysis.json")
    with open(output_file, 'w') as f:
        # Convert to serializable format
        serializable = {
            'total_prs': analysis['total_prs'],
            'agent_stats': {
                agent: {
                    'total_tasks': stats['total_tasks'],
                    'wins': stats['wins'],
                    'win_rate': stats['wins'] / stats['total_tasks'] if stats['total_tasks'] > 0 else 0,
                    'avg_aggregate': sum(stats['scores']) / len(stats['scores']) if stats['scores'] else 0,
                    'avg_correctness': sum(stats['correctness']) / len(stats['correctness']) if stats['correctness'] else 0,
                    'avg_completeness': sum(stats['completeness']) / len(stats['completeness']) if stats['completeness'] else 0,
                    'avg_code_reuse': sum(stats['code_reuse']) / len(stats['code_reuse']) if stats['code_reuse'] else 0,
                    'avg_best_practices': sum(stats['best_practices']) / len(stats['best_practices']) if stats['best_practices'] else 0,
                    'avg_unsolicited_docs': sum(stats['unsolicited_docs']) / len(stats['unsolicited_docs']) if stats['unsolicited_docs'] else 0,
                    'avg_llm_rating': sum(stats['llm_ratings']) / len(stats['llm_ratings']) if stats['llm_ratings'] else None,
                }
                for agent, stats in analysis['agent_stats'].items()
            },
            'prompt_analysis': analysis['prompt_analysis']
        }
        json.dump(serializable, f, indent=2)

    print(f"\n\nDetailed analysis saved to: {output_file}")

if __name__ == '__main__':
    main()

