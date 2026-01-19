"""
Reinforcement Learning Training for 45s
Self-play training using PPO (Proximal Policy Optimization)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
from collections import deque
import time
import os
import json

from game_engine import *
from ai_players import AIPlayer, HeuristicAI
from game_simulator import Game45s
from rl_model import Policy45sNetwork, Card45sEncoder

class RLAgent(AIPlayer):
    """AI player using trained neural network"""
    
    def __init__(self, player_idx: int, model: Policy45sNetwork, encoder: Card45sEncoder, 
                 temperature=1.0, device='cpu'):
        super().__init__(player_idx)
        self.model = model
        self.encoder = encoder
        self.temperature = temperature
        self.device = device
        self.heuristic = HeuristicAI(player_idx)  # Fallback for bidding/discarding
        
        # Training data collection
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
    
    def decide_bid(self, hand: List[Card], current_high: int, dealer: int,
                   team_score: int, opp_score: int) -> Tuple[int, Optional[Suit]]:
        """Use heuristic for bidding (for now)"""
        return self.heuristic.decide_bid(hand, current_high, dealer, team_score, opp_score)
    
    def choose_discards(self, hand: List[Card], trump_suit: Suit,
                       is_bidder: bool, bid_amount: int) -> List[Card]:
        """Use heuristic for discarding (for now)"""
        return self.heuristic.choose_discards(hand, trump_suit, is_bidder, bid_amount)
    
    def choose_card(self, state: GameState) -> Card:
        """Use neural network to choose card"""
        hand = state.hands[self.player_idx]
        led_card = state.current_trick[0][1] if state.current_trick else None
        playable = get_playable_cards(hand, state.trump_suit, led_card)
        
        if len(playable) == 1:
            return playable[0]
        
        # Encode state
        encoded_state = self.encoder.encode_game_state(state, self.player_idx)
        
        # Get action from model
        card, value = self.model.select_action(encoded_state, playable, self.temperature, self.device)
        
        # Store for training (if collecting data)
        if hasattr(self, 'collecting_data') and self.collecting_data:
            self.states.append(encoded_state)
            self.actions.append(self.encoder.encode_card(card))
            self.values.append(value)
        
        return card
    
    def reset_episode(self):
        """Clear episode data"""
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
    
    def store_reward(self, reward: float):
        """Store reward for this episode"""
        # Assign reward to all actions in episode
        self.rewards = [reward] * len(self.states)


class SelfPlayTrainer:
    """
    Trains 45s AI through self-play using PPO.
    """
    
    def __init__(self, model: Policy45sNetwork, device='cuda', 
                 learning_rate=3e-4, gamma=0.99):
        self.model = model.to(device)
        self.device = device
        self.encoder = Card45sEncoder()
        self.optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        self.gamma = gamma  # Discount factor
        
        # Training stats
        self.episode = 0
        self.stats = {
            'episodes': [],
            'rl_wins': [],
            'avg_score': [],
            'policy_loss': [],
            'value_loss': [],
            'total_loss': []
        }
    
    def play_self_play_game(self, temperature=1.0, collect_data=True):
        """
        Play one game with RL agents and collect training data.
        
        Returns: (rl_team_won, training_batch)
        """
        # Create 4 RL agents
        agents = [RLAgent(i, self.model, self.encoder, temperature, self.device) 
                  for i in range(4)]
        
        # Enable data collection
        if collect_data:
            for agent in agents:
                agent.collecting_data = True
                agent.reset_episode()
        
        # Play game
        game = Game45s(agents, verbose=False)
        winner, history = game.play_game()
        
        # Calculate rewards
        final_scores = game.scores
        
        # Team 0 reward (normalized to -1 to +1)
        team0_reward = (final_scores[0] - final_scores[1]) / 120.0
        team1_reward = -team0_reward
        
        # Assign rewards to agents
        for i, agent in enumerate(agents):
            reward = team0_reward if i % 2 == 0 else team1_reward
            agent.store_reward(reward)
        
        # Collect training data
        batch = {
            'states': [],
            'actions': [],
            'rewards': [],
            'values': []
        }
        
        if collect_data:
            for agent in agents:
                batch['states'].extend(agent.states)
                batch['actions'].extend(agent.actions)
                batch['rewards'].extend(agent.rewards)
                batch['values'].extend(agent.values)
        
        return winner, batch, final_scores
    
    def train_batch(self, batch, clip_epsilon=0.2):
        """
        Train on a batch of experience using PPO.
        """
        if not batch['states']:
            return 0.0, 0.0, 0.0
        
        # Convert to tensors
        states = torch.FloatTensor(np.array(batch['states'])).to(self.device)
        actions = torch.LongTensor(batch['actions']).to(self.device)
        rewards = torch.FloatTensor(batch['rewards']).to(self.device)
        old_values = torch.FloatTensor(batch['values']).to(self.device)
        
        # Forward pass
        policy_logits, values = self.model(states)
        values = values.squeeze()
        
        # Policy loss (simplified PPO - just supervised learning on rewards)
        log_probs = F.log_softmax(policy_logits, dim=1)
        action_log_probs = log_probs.gather(1, actions.unsqueeze(1)).squeeze()
        
        # Advantage = reward - value estimate
        advantages = rewards - old_values.detach()
        
        # Policy loss: maximize log prob weighted by advantage
        policy_loss = -(action_log_probs * advantages).mean()
        
        # Value loss: MSE between predicted and actual returns
        value_loss = F.mse_loss(values, rewards)
        
        # Total loss
        total_loss = policy_loss + 0.5 * value_loss
        
        # Optimize
        self.optimizer.zero_grad()
        total_loss.backward()
        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 0.5)
        self.optimizer.step()
        
        return policy_loss.item(), value_loss.item(), total_loss.item()
    
    def train(self, num_episodes=10000, batch_size=32, eval_interval=100, 
              save_interval=1000, save_dir='checkpoints'):
        """
        Main training loop.
        """
        print("="*70)
        print("REINFORCEMENT LEARNING TRAINING - 45s")
        print("="*70)
        print(f"Device: {self.device}")
        print(f"Episodes: {num_episodes}")
        print(f"Batch size: {batch_size}")
        print()
        
        os.makedirs(save_dir, exist_ok=True)
        
        # Training buffer
        experience_buffer = []
        
        start_time = time.time()
        
        for episode in range(num_episodes):
            self.episode = episode
            
            # Decay temperature (more exploration early, more exploitation later)
            temperature = max(0.1, 1.0 - episode / (num_episodes * 0.8))
            
            # Play game and collect data
            winner, batch, scores = self.play_self_play_game(temperature=temperature)
            experience_buffer.append(batch)
            
            # Train when we have enough data
            if len(experience_buffer) >= batch_size:
                # Combine batches
                combined_batch = {
                    'states': [],
                    'actions': [],
                    'rewards': [],
                    'values': []
                }
                for b in experience_buffer:
                    for key in combined_batch:
                        combined_batch[key].extend(b[key])
                
                # Train
                policy_loss, value_loss, total_loss = self.train_batch(combined_batch)
                
                # Clear buffer
                experience_buffer = []
                
                # Store stats
                self.stats['policy_loss'].append(policy_loss)
                self.stats['value_loss'].append(value_loss)
                self.stats['total_loss'].append(total_loss)
            
            # Progress
            if (episode + 1) % max(1, num_episodes // 100) == 0:
                elapsed = time.time() - start_time
                eps_per_sec = (episode + 1) / elapsed
                eta_sec = (num_episodes - episode - 1) / eps_per_sec if eps_per_sec > 0 else 0
                eta_min = int(eta_sec // 60)
                
                # Progress bar
                percent = (episode + 1) / num_episodes * 100
                bar_len = 40
                filled = int(bar_len * (episode + 1) / num_episodes)
                bar = '█' * filled + '░' * (bar_len - filled)
                
                print(f"\r[{bar}] {percent:5.1f}% | {episode + 1}/{num_episodes} | "
                      f"{eps_per_sec:.1f} eps/s | ETA: {eta_min}m", end='', flush=True)
            
            # Evaluation
            if (episode + 1) % eval_interval == 0:
                print()  # New line
                eval_results = self.evaluate(num_games=50)
                print(f"Eval @ {episode + 1}: RL wins {eval_results['rl_wins']}/50 "
                      f"({eval_results['rl_win_rate']:.1f}%) | "
                      f"Avg score: {eval_results['rl_avg_score']:.1f}")
                
                self.stats['episodes'].append(episode + 1)
                self.stats['rl_wins'].append(eval_results['rl_wins'])
                self.stats['avg_score'].append(eval_results['rl_avg_score'])
            
            # Save checkpoint
            if (episode + 1) % save_interval == 0:
                self.save_checkpoint(save_dir, episode + 1)
        
        print()  # Final newline
        print("\nTraining complete!")
        
        # Final save
        self.save_checkpoint(save_dir, num_episodes, is_final=True)
        self.save_stats(save_dir)
    
    def evaluate(self, num_games=100):
        """
        Evaluate RL agent vs Heuristic AI.
        """
        # RL agents (greedy, no exploration)
        rl_agents = [RLAgent(i, self.model, self.encoder, temperature=0.0, device=self.device) 
                     for i in [0, 2]]  # Team 0
        heuristic_agents = [HeuristicAI(i) for i in [1, 3]]  # Team 1
        
        players = [rl_agents[0], heuristic_agents[0], rl_agents[1], heuristic_agents[1]]
        
        rl_wins = 0
        rl_total_score = 0
        
        for _ in range(num_games):
            game = Game45s(players, verbose=False)
            winner, history = game.play_game()
            
            if winner == 0:  # RL team
                rl_wins += 1
            
            rl_total_score += game.scores[0]
        
        return {
            'rl_wins': rl_wins,
            'rl_win_rate': rl_wins / num_games * 100,
            'rl_avg_score': rl_total_score / num_games
        }
    
    def save_checkpoint(self, save_dir, episode, is_final=False):
        """Save model checkpoint"""
        filename = 'final_model.pt' if is_final else f'checkpoint_{episode}.pt'
        path = os.path.join(save_dir, filename)
        
        torch.save({
            'episode': episode,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'stats': self.stats
        }, path)
        
        print(f"  → Saved checkpoint: {path}")
    
    def save_stats(self, save_dir):
        """Save training statistics"""
        with open(os.path.join(save_dir, 'training_stats.json'), 'w') as f:
            json.dump(self.stats, f, indent=2)


if __name__ == "__main__":
    # Check for GPU
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device}")
    
    if device == 'cuda':
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    
    # Create model
    encoder = Card45sEncoder()
    # Get input size from dummy state
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
    
    # Create trainer
    trainer = SelfPlayTrainer(model, device=device, learning_rate=3e-4)
    
    # Train
    trainer.train(
        num_episodes=10000,
        batch_size=32,
        eval_interval=500,
        save_interval=2000
    )
