# 45s Card Game - Python Simulator

Python-based simulator and AI trainer for the card game 45s.

## Files

- `game_engine.py` - Core game logic (cards, rules, scoring)
- `ai_players.py` - AI player implementations (Heuristic, MC, RL)
- `game_simulator.py` - Game runner and tournament system
- `requirements.txt` - Python dependencies

## Quick Start

### Run a Single Game (Verbose)
```bash
python game_simulator.py
```

### Run Tournament (1000 games)
```python
from game_simulator import run_tournament
results = run_tournament(num_games=1000, verbose=False)
```

## AI Players

### HeuristicAI
- Uses hand-coded strategies based on bidding simulations
- Implements: bidding thresholds, discard strategy, basic play heuristics
- Fast, deterministic, interpretable

### MonteCarloAI (Coming Soon)
- Uses simulation to evaluate moves
- Samples opponent hands, simulates N rollouts
- Slower but handles complex situations

### RLAI (Coming Soon)
- Reinforcement learning trained agent
- Learns optimal strategies through self-play
- GPU-accelerated training

## Game Rules Implemented

✅ Standard 52-card deck
✅ Trump ranking: 5, J, A♥, A, K, Q, then low-high (red) or high-low (black)
✅ Reneging allowed (can play trump when off-suit is led)
✅ Bidding: 15, 20, 25, 30
✅ Scoring: 5 points per trick, must make bid
✅ Team play (players 0&2 vs 1&3)

## Testing

Run quick test:
```bash
python -c "from game_simulator import *; run_tournament(100)"
```

## Next Steps

1. ✅ Core game engine
2. ✅ Heuristic AI
3. ⏳ Monte Carlo AI
4. ⏳ Tournament comparison (Heuristic vs MC)
5. ⏳ Reinforcement Learning training
6. ⏳ Strategy analysis tools
7. ⏳ Export best strategy to JavaScript for web game

## Performance

On typical hardware:
- Heuristic AI: ~1000 games/second
- Monte Carlo AI (100 rollouts): ~10-50 games/second
- RL Training: GPU recommended, 10K+ games/hour

## Usage Example

```python
from game_simulator import Game45s
from ai_players import HeuristicAI

# Create 4 AI players
players = [HeuristicAI(i) for i in range(4)]

# Play a game
game = Game45s(players, verbose=True)
winner, history = game.play_game()

print(f"Winner: Team {winner}")
print(f"Rounds played: {len(history)}")
```
