"""
Test different Monte Carlo rollout counts
Find optimal balance of speed vs accuracy
"""

from game_simulator import Game45s, compare_strategies
from ai_players import HeuristicAI, MonteCarloAI
import time

def test_mc_rollouts(rollout_counts=[10, 20, 30, 50, 100], games_per_test=50):
    """
    Test MC with different rollout counts vs Heuristic AI.
    """
    print("="*70)
    print("MONTE CARLO ROLLOUT OPTIMIZATION")
    print("="*70)
    print()
    
    results = []
    
    for rollouts in rollout_counts:
        print(f"\nTesting {rollouts} rollouts...")
        print("-"*70)
        
        # Create players
        players = [
            HeuristicAI(0),                    # Team 0
            MonteCarloAI(1, rollouts),         # Team 1
            HeuristicAI(2),                    # Team 0
            MonteCarloAI(3, rollouts)          # Team 1
        ]
        
        mc_wins = 0
        mc_total_score = 0
        heuristic_total_score = 0
        
        start_time = time.time()
        
        for game_num in range(games_per_test):
            if (game_num + 1) % 10 == 0:
                print(f"  Game {game_num + 1}/{games_per_test}...", end='\r')
            
            game = Game45s(players, verbose=False)
            winner, history = game.play_game()
            
            if winner == 1:  # MC team
                mc_wins += 1
            
            mc_total_score += game.scores[1]
            heuristic_total_score += game.scores[0]
        
        elapsed = time.time() - start_time
        games_per_sec = games_per_test / elapsed
        
        win_rate = mc_wins / games_per_test * 100
        avg_mc_score = mc_total_score / games_per_test
        avg_h_score = heuristic_total_score / games_per_test
        
        result = {
            'rollouts': rollouts,
            'win_rate': win_rate,
            'wins': mc_wins,
            'avg_score': avg_mc_score,
            'games_per_sec': games_per_sec,
            'time': elapsed
        }
        results.append(result)
        
        print(f"\n  ✓ {rollouts} rollouts: {win_rate:.1f}% win rate | "
              f"{games_per_sec:.2f} g/s | {elapsed:.1f}s total")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"{'Rollouts':<10} {'Win Rate':<12} {'Speed':<15} {'Quality'}")
    print("-"*70)
    
    for r in results:
        speed_str = f"{r['games_per_sec']:.2f} g/s"
        quality = "⭐⭐⭐" if r['win_rate'] >= 60 else "⭐⭐" if r['win_rate'] >= 50 else "⭐"
        print(f"{r['rollouts']:<10} {r['win_rate']:>5.1f}% ({r['wins']}/50) {speed_str:<15} {quality}")
    
    # Recommendation
    print("\n" + "="*70)
    print("RECOMMENDATION")
    print("="*70)
    
    # Find sweet spot (best win rate among fast enough options)
    fast_enough = [r for r in results if r['games_per_sec'] >= 1.0]  # At least 1 game/sec
    if fast_enough:
        best = max(fast_enough, key=lambda x: x['win_rate'])
        print(f"\n✓ Use {best['rollouts']} rollouts")
        print(f"  Win rate: {best['win_rate']:.1f}%")
        print(f"  Speed: {best['games_per_sec']:.2f} games/sec")
        print(f"  Time per game: {1/best['games_per_sec']:.2f} seconds")
        print(f"\nThis provides good performance while keeping gameplay responsive.")
    else:
        # All are slow, pick best win rate
        best = max(results, key=lambda x: x['win_rate'])
        print(f"\n⚠ All options are slow (<1 game/sec)")
        print(f"  Best accuracy: {best['rollouts']} rollouts ({best['win_rate']:.1f}% win rate)")
        print(f"  But only {best['games_per_sec']:.2f} games/sec")
        print(f"\nConsider reducing to 10-20 rollouts for playability.")
    
    return results

if __name__ == "__main__":
    # Test common rollout counts
    results = test_mc_rollouts(
        rollout_counts=[10, 20, 30, 50, 100],
        games_per_test=50
    )
    
    print("\n" + "="*70)
    print("\nNext steps:")
    print("1. Use recommended rollout count in your web game")
    print("2. Test selective simulation (only use MC for tricks 3-5)")
    print("3. Implement hybrid: MC for close games, Heuristic otherwise")
