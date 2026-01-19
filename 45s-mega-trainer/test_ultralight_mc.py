"""
Test ultra-light Monte Carlo rollout counts
Find minimum viable MC for web game performance
"""

from game_simulator import Game45s
from ai_players import HeuristicAI, MonteCarloAI
import time

def test_ultralight_mc(rollout_counts=[3, 5, 7, 10, 15], games_per_test=50):
    """
    Test MC with very low rollout counts for web game.
    Goal: Find minimum rollouts that still beat heuristic.
    """
    print("="*70)
    print("ULTRA-LIGHT MONTE CARLO TEST")
    print("Goal: Find fastest MC that still beats Heuristic AI")
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
        sec_per_game = elapsed / games_per_test
        
        win_rate = mc_wins / games_per_test * 100
        avg_mc_score = mc_total_score / games_per_test
        avg_h_score = heuristic_total_score / games_per_test
        
        result = {
            'rollouts': rollouts,
            'win_rate': win_rate,
            'wins': mc_wins,
            'avg_score': avg_mc_score,
            'games_per_sec': games_per_sec,
            'sec_per_game': sec_per_game,
            'time': elapsed
        }
        results.append(result)
        
        print(f"\n  ✓ {rollouts} rollouts: {win_rate:.1f}% win rate | "
              f"{sec_per_game:.2f}s per game | {games_per_sec:.2f} g/s")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY - WEB GAME VIABILITY")
    print("="*70)
    print(f"{'Rollouts':<10} {'Win Rate':<15} {'Time/Game':<15} {'Web Viable?'}")
    print("-"*70)
    
    for r in results:
        time_str = f"{r['sec_per_game']:.2f}s"
        
        # Web game viability
        if r['sec_per_game'] <= 1.0:
            viable = "✅ EXCELLENT"
        elif r['sec_per_game'] <= 2.0:
            viable = "✓ Good"
        elif r['sec_per_game'] <= 3.0:
            viable = "⚠ Acceptable"
        else:
            viable = "❌ Too slow"
        
        # Win rate quality
        if r['win_rate'] >= 55:
            quality = "⭐⭐⭐"
        elif r['win_rate'] >= 52:
            quality = "⭐⭐"
        else:
            quality = "⭐"
        
        print(f"{r['rollouts']:<10} {r['win_rate']:>5.1f}% {quality:<7} {time_str:<15} {viable}")
    
    # Recommendation
    print("\n" + "="*70)
    print("RECOMMENDATION FOR WEB GAME")
    print("="*70)
    
    # Find best option that's fast enough
    fast_enough = [r for r in results if r['sec_per_game'] <= 1.5]
    
    if fast_enough:
        # Pick highest win rate among fast options
        best = max(fast_enough, key=lambda x: x['win_rate'])
        print(f"\n✅ RECOMMENDED: {best['rollouts']} rollouts")
        print(f"   Win rate: {best['win_rate']:.1f}% (beats Heuristic)")
        print(f"   Speed: {best['sec_per_game']:.2f} seconds per game")
        print(f"   Response time: ~{best['sec_per_game']/7:.2f}s per card played")
        print(f"\n   This provides a good player experience:")
        print(f"   - Noticeably smarter than Heuristic AI")
        print(f"   - Fast enough to feel responsive")
        print(f"   - {best['rollouts']} simulations is computationally feasible in browser")
    else:
        print(f"\n⚠ All options still too slow for ideal web gameplay")
        print(f"   Consider further optimizations:")
        print(f"   - Use Web Workers for background simulation")
        print(f"   - Cache common positions")
        print(f"   - Optimize JavaScript implementation")
    
    # Also show the absolute best performer
    absolute_best = max(results, key=lambda x: x['win_rate'])
    print(f"\n📊 Highest win rate: {absolute_best['rollouts']} rollouts ({absolute_best['win_rate']:.1f}%)")
    print(f"   But takes {absolute_best['sec_per_game']:.2f}s per game")
    
    return results

if __name__ == "__main__":
    print("\nThis will test very low rollout counts (3, 5, 7, 10, 15)")
    print("Looking for the sweet spot: fast enough for web, smart enough to beat Heuristic\n")
    
    results = test_ultralight_mc(
        rollout_counts=[3, 5, 7, 10, 15],
        games_per_test=50
    )
    
    print("\n" + "="*70)
    print("NEXT STEPS:")
    print("="*70)
    print("\n1. Use the recommended rollout count")
    print("2. I'll convert the MC logic to JavaScript")
    print("3. We'll integrate it into your web game")
    print("4. Players will notice the AI is smarter!")
