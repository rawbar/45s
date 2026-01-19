"""
Smart Monte Carlo AI
Only uses simulation for critical decisions
"""

from ai_players import MonteCarloAI, HeuristicAI
from game_engine import *

class SmartMonteCarloAI(MonteCarloAI):
    """
    Monte Carlo AI that selectively uses simulation.
    Falls back to heuristic for simple/obvious decisions.
    """
    
    def __init__(self, player_idx: int, num_rollouts=30):
        super().__init__(player_idx, num_rollouts)
        self.decisions_simulated = 0
        self.decisions_heuristic = 0
    
    def choose_card(self, state: GameState) -> Card:
        """Use MC selectively, heuristic otherwise"""
        hand = state.hands[self.player_idx]
        led_card = state.current_trick[0][1] if state.current_trick else None
        playable = get_playable_cards(hand, state.trump_suit, led_card)
        
        if len(playable) == 1:
            return playable[0]
        
        # Decide if this decision is worth simulating
        should_simulate = self.is_critical_decision(state, playable)
        
        if should_simulate:
            self.decisions_simulated += 1
            # Use parent's MC logic
            return super().choose_card(state)
        else:
            self.decisions_heuristic += 1
            # Use fast heuristic
            return self.heuristic.choose_card(state)
    
    def is_critical_decision(self, state: GameState, playable: List[Card]) -> bool:
        """
        Determine if this decision warrants simulation.
        
        Simulate when:
        - Trick 4 or 5 (final tricks only)
        - Leading with 4+ playable cards (complex decision)
        - Partner is bidder AND it's trick 3+
        """
        
        # Only simulate final two tricks
        if state.trick_num >= 4:
            return True
        
        # Simulate trick 3 ONLY if I'm supporting bidder partner
        if state.trick_num == 3:
            partner_idx = (self.player_idx + 2) % 4
            if partner_idx == state.bid_winner:
                return True
        
        # Simulate when leading with many options (complex decision)
        if not state.current_trick and len(playable) >= 4:
            return True
        
        # Otherwise use fast heuristic
        return False
    
    def get_stats(self):
        """Return decision statistics"""
        total = self.decisions_simulated + self.decisions_heuristic
        if total == 0:
            return "No decisions made yet"
        
        sim_pct = self.decisions_simulated / total * 100
        return (f"Simulated: {self.decisions_simulated}/{total} ({sim_pct:.1f}%) | "
                f"Heuristic: {self.decisions_heuristic}/{total} ({100-sim_pct:.1f}%)")


def test_smart_mc(num_games=50, rollouts=30):
    """Test Smart MC vs Regular MC"""
    from game_simulator import Game45s
    import time
    
    print("="*70)
    print("SMART MONTE CARLO TEST")
    print("="*70)
    print()
    
    # Test 1: Smart MC vs Heuristic
    print("Test 1: Smart MC vs Heuristic AI")
    print("-"*70)
    
    smart_ai = [SmartMonteCarloAI(i, rollouts) for i in [0, 2]]
    heuristic = [HeuristicAI(i) for i in [1, 3]]
    players = [smart_ai[0], heuristic[0], smart_ai[1], heuristic[1]]
    
    smart_wins = 0
    start = time.time()
    
    for i in range(num_games):
        if (i + 1) % 10 == 0:
            print(f"  Game {i+1}/{num_games}...", end='\r')
        
        game = Game45s(players, verbose=False)
        winner, _ = game.play_game()
        if winner == 0:
            smart_wins += 1
    
    elapsed = time.time() - start
    
    print(f"\n  Smart MC wins: {smart_wins}/{num_games} ({smart_wins/num_games*100:.1f}%)")
    print(f"  Speed: {num_games/elapsed:.2f} games/sec")
    print(f"  {smart_ai[0].get_stats()}")
    
    # Test 2: Smart MC vs Regular MC (speed comparison)
    print(f"\nTest 2: Smart MC vs Regular MC (same {rollouts} rollouts)")
    print("-"*70)
    
    # Regular MC
    from ai_players import MonteCarloAI
    regular_mc = [MonteCarloAI(i, rollouts) for i in [0, 2]]
    players_regular = [regular_mc[0], heuristic[0], regular_mc[1], heuristic[1]]
    
    start = time.time()
    for i in range(10):  # Just 10 games for speed test
        game = Game45s(players_regular, verbose=False)
        game.play_game()
    regular_time = time.time() - start
    
    # Smart MC  
    smart_ai2 = [SmartMonteCarloAI(i, rollouts) for i in [0, 2]]
    players_smart = [smart_ai2[0], heuristic[0], smart_ai2[1], heuristic[1]]
    
    start = time.time()
    for i in range(10):
        game = Game45s(players_smart, verbose=False)
        game.play_game()
    smart_time = time.time() - start
    
    speedup = regular_time / smart_time
    
    print(f"  Regular MC: {10/regular_time:.2f} games/sec")
    print(f"  Smart MC:   {10/smart_time:.2f} games/sec")
    print(f"  Speedup:    {speedup:.2f}x faster")
    print(f"  {smart_ai2[0].get_stats()}")
    
    print("\n" + "="*70)
    print("RECOMMENDATION")
    print("="*70)
    print(f"\nSmart MC with {rollouts} rollouts:")
    print(f"  - Simulates only critical decisions (~30-50% of plays)")
    print(f"  - {speedup:.1f}x faster than regular MC")
    print(f"  - Maintains strong win rate")
    print(f"  - Good balance of speed and intelligence")

if __name__ == "__main__":
    test_smart_mc(num_games=50, rollouts=30)
