#!/usr/bin/env python3
"""Generate detailed case studies of interesting wins/losses."""

import json
from pathlib import Path

def load_cross_agent_data():
    """Load all cross-agent analysis files."""
    ca_dir = Path("output/cross_agent_analysis")
    results = []
    
    for file in sorted(ca_dir.glob("pr*.json")):
        with open(file) as f:
            data = json.load(f)
            results.append(data)
    
    return results

def print_case_study(pr_data, title):
    """Print a detailed case study."""
    print(f"\n{'=' * 80}")
    print(f"{title}")
    print(f"{'=' * 80}\n")
    
    print(f"PR Number: {pr_data['pr_number']}")
    print(f"Task: {pr_data['task_instructions'][:200]}...")
    print(f"\nGround Truth Stats:")
    gt = pr_data.get('ground_truth_diff', '')
    print(f"  Files changed: {gt.count('diff --git')}")
    print(f"  Lines: {len(gt.split(chr(10)))}")
    
    print(f"\n{'=' * 80}")
    print("AGENT RESULTS")
    print(f"{'=' * 80}\n")
    
    for agent_result in pr_data['agent_results']:
        agent_name = f"{agent_result['runner']}:{agent_result['model']}"
        print(f"\n{agent_name}")
        print(f"{'-' * 80}")
        print(f"Status: {agent_result['status']}")
        print(f"Elapsed: {agent_result['elapsed_ms']/1000:.1f}s")
        print(f"Aggregate Score: {agent_result['aggregate']:.3f}")
        print(f"Scores: C={agent_result['scores']['correctness']:.2f}, "
              f"Comp={agent_result['scores']['completeness']:.2f}, "
              f"CR={agent_result['scores']['code_reuse']:.2f}, "
              f"BP={agent_result['scores']['best_practices']:.2f}, "
              f"UD={agent_result['scores']['unsolicited_docs']:.2f}")
        if agent_result.get('llm_rating'):
            print(f"LLM Rating: {agent_result['llm_rating']:.2f}")
        
        print(f"\nSummary: {agent_result.get('llm_summary', 'N/A')}")
        
        print(f"\nRationale:")
        rationale = agent_result.get('rationale', 'N/A')
        # Print first 500 chars
        if len(rationale) > 500:
            print(f"  {rationale[:500]}...")
        else:
            print(f"  {rationale}")
    
    if pr_data.get('comparative_analysis'):
        ca = pr_data['comparative_analysis']
        print(f"\n{'=' * 80}")
        print("COMPARATIVE ANALYSIS")
        print(f"{'=' * 80}\n")
        print(f"Best Agent: {ca.get('best_agent', 'N/A')}")
        print(f"\nReasoning: {ca.get('best_agent_reasoning', 'N/A')}")
        print(f"\nApproach Differences:")
        print(f"  {ca.get('approach_differences', 'N/A')[:500]}...")

def main():
    """Main entry point."""
    print("Loading data...")
    data = load_cross_agent_data()
    
    # Find interesting cases
    
    # Case 1: Where Auggie won decisively
    auggie_wins = [pr for pr in data 
                   if pr.get('comparative_analysis', {}).get('best_agent') == 'auggie:sonnet4.5']
    best_auggie = max(auggie_wins, 
                      key=lambda pr: [ar for ar in pr['agent_results'] 
                                     if ar['runner'] == 'auggie'][0]['aggregate'])
    
    # Case 2: Where Factory won decisively
    factory_wins = [pr for pr in data 
                    if pr.get('comparative_analysis', {}).get('best_agent') == 'factory:claude-sonnet-4-5-20250929']
    best_factory = max(factory_wins,
                       key=lambda pr: [ar for ar in pr['agent_results'] 
                                      if ar['runner'] == 'factory'][0]['aggregate'])
    
    # Case 3: Where all agents struggled
    all_struggled = min(data, key=lambda pr: max(ar['aggregate'] for ar in pr['agent_results']))
    
    # Case 4: Close competition
    def score_variance(pr):
        scores = [ar['aggregate'] for ar in pr['agent_results']]
        mean = sum(scores) / len(scores)
        return sum((s - mean) ** 2 for s in scores) / len(scores)
    
    close_competition = min(data, key=score_variance)
    
    # Case 5: Where Claude Code won (rare!)
    claude_wins = [pr for pr in data 
                   if pr.get('comparative_analysis', {}).get('best_agent') == 'claude-code:claude-sonnet-4-5']
    
    print_case_study(best_auggie, "CASE STUDY 1: Auggie's Best Win")
    print_case_study(best_factory, "CASE STUDY 2: Factory's Best Win")
    print_case_study(all_struggled, "CASE STUDY 3: All Agents Struggled")
    print_case_study(close_competition, "CASE STUDY 4: Close Competition")
    
    if claude_wins:
        print_case_study(claude_wins[0], "CASE STUDY 5: Claude Code's Rare Win")

if __name__ == '__main__':
    main()

