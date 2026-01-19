#!/usr/bin/env python3
"""
Quick start script for RL training
"""

import sys
import torch

def main():
    print("="*70)
    print("45s REINFORCEMENT LEARNING TRAINING")
    print("="*70)
    print()
    
    # Check GPU
    if not torch.cuda.is_available():
        print("⚠️  WARNING: CUDA not available!")
        print("   Training will use CPU (much slower)")
        print()
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting. Install CUDA-enabled PyTorch first.")
            sys.exit(0)
    else:
        print(f"✓ GPU detected: {torch.cuda.get_device_name(0)}")
        print(f"  Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        print()
    
    # Training options
    print("Training options:")
    print("  1. Quick test (1,000 episodes, ~5 minutes)")
    print("  2. Short training (10,000 episodes, ~1 hour)")
    print("  3. Full training (100,000 episodes, ~10 hours)")
    print("  4. Overnight training (500,000 episodes, ~2 days)")
    print()
    
    choice = input("Select option (1-4): ").strip()
    
    episodes_map = {
        '1': 1000,
        '2': 10000,
        '3': 100000,
        '4': 500000
    }
    
    num_episodes = episodes_map.get(choice, 10000)
    
    print()
    print(f"Starting training with {num_episodes:,} episodes...")
    print("Press Ctrl+C to stop early (model will be saved)")
    print()
    
    # Import and run
    from train_rl import SelfPlayTrainer, Policy45sNetwork, Card45sEncoder, Deck, GameState, Suit
    
    # Setup
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    encoder = Card45sEncoder()
    deck = Deck().shuffle()
    dummy_state = GameState(
        hands=[deck.deal(5) for _ in range(4)],
        trump_suit=Suit.HEARTS,
        bid_winner=0,
        high_bid=20,
        dealer=3,
        current_trick=[],
        trick_leader=0,
        tricks_won=[0, 0],
        trick_num=1,
        cards_drawn=[1, 2, 3, 4],
        cards_played=[],
        known_out_of_trump=[False, False, False, False],
        bidder_lost_trick=False
    )
    input_size = len(encoder.encode_game_state(dummy_state, 0))
    
    model = Policy45sNetwork(input_size=input_size, hidden_size=256)
    trainer = SelfPlayTrainer(model, device=device)
    
    try:
        trainer.train(
            num_episodes=num_episodes,
            batch_size=32,
            eval_interval=max(100, num_episodes // 20),
            save_interval=max(1000, num_episodes // 10)
        )
    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user")
        print("Saving model...")
        trainer.save_checkpoint('checkpoints', trainer.episode, is_final=True)
        trainer.save_stats('checkpoints')
        print("Model saved!")

if __name__ == "__main__":
    main()
