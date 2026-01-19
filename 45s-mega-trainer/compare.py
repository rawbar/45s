#!/usr/bin/env python3
"""
45s AI Comparison Script
Run this to compare Heuristic vs Monte Carlo AI
"""

from game_simulator import run_tournament, compare_strategies

def main():
    print("="*70)
    print("45s AI COMPARISON")
    print("="*70)
    print()
    
    # First, run baseline with heuristic only
    print("STEP 1: Baseline - Heuristic AI only")
    print("-"*70)
    baseline = run_tournament(num_games=1000, verbose=False)
    
    print("\n\n")
    
    # Now compare heuristic vs Monte Carlo
    print("STEP 2: Comparison - Heuristic vs Monte Carlo")
    print("-"*70)
    comparison = compare_strategies(num_games=100, mc_rollouts=100, verbose=False)
    
    print("\n\n")
    print("="*70)
    print("ANALYSIS")
    print("="*70)
    
    # Calculate win rate improvement
    baseline_balanced = abs(baseline['team0_wins'] - baseline['team1_wins']) / 1000 * 100
    
    if comparison['montecarlo_wins'] > comparison['heuristic_wins']:
        advantage = comparison['montecarlo_wins'] - comparison['heuristic_wins']
        print(f"✓ Monte Carlo AI has {advantage}-game advantage ({advantage/100*100:.1f}% win rate improvement)")
        print(f"  This suggests MC makes better decisions on average.")
    elif comparison['heuristic_wins'] > comparison['montecarlo_wins']:
        advantage = comparison['heuristic_wins'] - comparison['montecarlo_wins']
        print(f"✗ Heuristic AI has {advantage}-game advantage")
        print(f"  MC may need more rollouts or better opponent modeling.")
    else:
        print(f"= Tied - both strategies perform equally")
    
    print()
    print(f"Baseline balance: {baseline_balanced:.1f}% deviation from 50/50")
    print(f"(Lower is better - shows fair/balanced gameplay)")
    
    print()
    print("RECOMMENDATIONS:")
    if comparison['montecarlo_wins'] > comparison['heuristic_wins'] + 10:
        print("  → MC is significantly better! Consider:")
        print("     • Use MC for complex decisions in web game")
        print("     • Extract MC insights to improve heuristics")
        print("     • Proceed to RL training for even better results")
    elif comparison['montecarlo_wins'] > comparison['heuristic_wins']:
        print("  → MC shows promise. Next steps:")
        print("     • Run more games for statistical confidence")
        print("     • Try different rollout counts (50, 150, 200)")
        print("     • Analyze where MC wins (which tricks/situations)")
    else:
        print("  → Heuristic is competitive. Options:")
        print("     • Increase MC rollouts (currently 100)")
        print("     • Improve opponent hand sampling")
        print("     • Skip to RL training instead")

if __name__ == "__main__":
    main()
