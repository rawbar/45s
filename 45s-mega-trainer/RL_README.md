# 45s Reinforcement Learning Training

Train a neural network to play 45s through self-play using your RTX 3070 GPU.

## Quick Start

### 1. Install Dependencies

```bash
# Install PyTorch with CUDA support (for your RTX 3070)
pip install torch --index-url https://download.pytorch.org/whl/cu118

# Or use requirements.txt
pip install -r requirements.txt
```

### 2. Run Training

```bash
python train.py
```

This will:
- Detect your GPU automatically
- Let you choose training duration
- Train the neural network
- Save checkpoints periodically
- Evaluate progress against Heuristic AI

### 3. Training Options

**Quick test** (1,000 episodes, ~5 min)
- Tests if everything works
- Won't produce good AI yet

**Short training** (10,000 episodes, ~1 hour)
- Should start showing improvement
- Good for testing

**Full training** (100,000 episodes, ~10 hours)
- Recommended minimum for decent performance
- Run overnight

**Overnight** (500,000 episodes, ~2 days)
- Best results
- GPU will run hot but is designed for this

## What Happens During Training

### Self-Play
- 4 RL agents play complete games against each other
- Neural network learns from wins and losses
- Gradually discovers optimal strategies

### Progress Output
```
[████████████░░░░░░░░] 60.0% | 60000/100000 | 15.2 eps/s | ETA: 73m
Eval @ 60000: RL wins 42/50 (84.0%) | Avg score: 105.3
```

Shows:
- Progress bar with ETA
- Episodes per second
- Evaluation vs Heuristic AI
- Win rate and average score

### Checkpoints
Saved to `checkpoints/` folder:
- `checkpoint_10000.pt` - Every 10k episodes
- `final_model.pt` - When training completes
- `training_stats.json` - Performance metrics

## What the AI Learns

Through millions of games, it discovers:
- **When to renege** (save high trump for later)
- **Sacrifice plays** (force out opponent's trump)
- **Trump preservation** (lead offsuit when appropriate)
- **3rd man high / 2nd man low** (partnership support)
- **Endgame tactics** (optimal trick 4-5 play)
- **Card counting** (infer opponent hands)

All without being explicitly programmed!

## Expected Results

After 100,000 episodes of training:
- **vs Heuristic AI**: 70-80% win rate
- **vs Monte Carlo (100 rollouts)**: 55-65% win rate
- **Discovers strategies** not in heuristic code

The neural network effectively "compresses" Monte Carlo's simulation ability into fast pattern recognition.

## GPU Usage

Your RTX 3070 specs:
- 8GB VRAM
- 5888 CUDA cores
- Perfect for this task!

Expected performance:
- ~10-20 episodes/second
- ~100% GPU utilization
- ~60-70°C temperature (normal)
- ~150W power draw

## Troubleshooting

**"CUDA not available"**
```bash
# Verify PyTorch sees your GPU
python -c "import torch; print(torch.cuda.is_available())"
python -c "import torch; print(torch.cuda.get_device_name(0))"
```

If False, reinstall PyTorch with CUDA:
```bash
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

**Out of memory**
Reduce batch size in `train.py`:
```python
trainer.train(batch_size=16)  # Instead of 32
```

**Training too slow**
- Close other GPU programs
- Reduce hidden_size in model (256 → 128)
- Use fewer rollouts for evaluation

## After Training

Once trained, you can:

1. **Evaluate the model**
```python
from train_rl import *
# Load trained model
checkpoint = torch.load('checkpoints/final_model.pt')
model.load_state_dict(checkpoint['model_state_dict'])
# Test vs different opponents
```

2. **Export to JavaScript** (for web game)
   - Convert model weights to JSON
   - Implement inference in JavaScript
   - Embed in your web game

3. **Continue training**
   - Load checkpoint
   - Train for more episodes
   - Fine-tune performance

## Next Steps

After successful training:
1. Share results (win rate vs Heuristic/MC)
2. Analyze what strategies it learned
3. Export model for web game integration
4. Or train even longer for better performance!

## Files

- `train.py` - Simple training launcher
- `train_rl.py` - Full training system
- `rl_model.py` - Neural network architecture
- `checkpoints/` - Saved models (created automatically)

Enjoy training your AI! 🎮🤖
