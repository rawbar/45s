"""
Reinforcement Learning Model for 45s
Neural network that learns to play 45s through self-play
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from game_engine import *
from typing import List, Tuple, Dict

class Card45sEncoder:
    """
    Encodes game state into neural network input.
    """
    
    def __init__(self):
        # Card encoding: 52 cards total
        self.card_to_idx = {}
        idx = 0
        for suit in Suit:
            for rank in RANKS:
                self.card_to_idx[f"{rank}{suit.value}"] = idx
                idx += 1
    
    def encode_card(self, card: Card) -> int:
        """Get index for a card"""
        return self.card_to_idx[f"{card.rank}{card.suit.value}"]
    
    def encode_hand(self, hand: List[Card]) -> np.ndarray:
        """
        Encode hand as binary vector (52 dimensions).
        1 if card is in hand, 0 otherwise.
        """
        vec = np.zeros(52, dtype=np.float32)
        for card in hand:
            vec[self.encode_card(card)] = 1.0
        return vec
    
    def encode_cards_played(self, cards: List[Card]) -> np.ndarray:
        """Encode which cards have been played"""
        vec = np.zeros(52, dtype=np.float32)
        for card in cards:
            vec[self.encode_card(card)] = 1.0
        return vec
    
    def encode_game_state(self, state: GameState, player_idx: int) -> np.ndarray:
        """
        Encode full game state for neural network.
        
        Returns vector with:
        - My hand (52 dims)
        - Cards played (52 dims)
        - Current trick (52 dims for cards + 4 dims for who played)
        - Trump suit (4 dims, one-hot)
        - Game context (scalar values):
            - High bid
            - Tricks won by each team (2)
            - Cards drawn by each player (4)
            - My position (4, one-hot)
            - Bidder position (4, one-hot)
            - Trick number (1-5, one-hot)
            - Am I bidder? (1)
            - Is partner bidder? (1)
            - Known out of trump (4)
        """
        encoder = []
        
        # My hand (52)
        encoder.append(self.encode_hand(state.hands[player_idx]))
        
        # Cards played (52)
        encoder.append(self.encode_cards_played(state.cards_played))
        
        # Current trick - cards (52)
        trick_cards = [card for _, card in state.current_trick]
        encoder.append(self.encode_cards_played(trick_cards))
        
        # Current trick - who played (4)
        trick_players = np.zeros(4, dtype=np.float32)
        for player, _ in state.current_trick:
            trick_players[player] = 1.0
        encoder.append(trick_players)
        
        # Trump suit (4, one-hot)
        trump_vec = np.zeros(4, dtype=np.float32)
        trump_vec[list(Suit).index(state.trump_suit)] = 1.0
        encoder.append(trump_vec)
        
        # High bid (normalized)
        encoder.append(np.array([state.high_bid / 30.0], dtype=np.float32))
        
        # Tricks won (2, normalized)
        tricks_won = np.array(state.tricks_won, dtype=np.float32) / 5.0
        encoder.append(tricks_won)
        
        # Cards drawn (4, normalized)
        cards_drawn = np.array(state.cards_drawn, dtype=np.float32) / 4.0
        encoder.append(cards_drawn)
        
        # My position (4, one-hot)
        my_pos = np.zeros(4, dtype=np.float32)
        my_pos[player_idx] = 1.0
        encoder.append(my_pos)
        
        # Bidder position (4, one-hot)
        bidder_pos = np.zeros(4, dtype=np.float32)
        bidder_pos[state.bid_winner] = 1.0
        encoder.append(bidder_pos)
        
        # Trick number (5, one-hot)
        trick_num = np.zeros(5, dtype=np.float32)
        trick_num[state.trick_num - 1] = 1.0
        encoder.append(trick_num)
        
        # Am I bidder?
        encoder.append(np.array([1.0 if player_idx == state.bid_winner else 0.0], dtype=np.float32))
        
        # Is partner bidder?
        partner_idx = (player_idx + 2) % 4
        encoder.append(np.array([1.0 if partner_idx == state.bid_winner else 0.0], dtype=np.float32))
        
        # Known out of trump (4)
        encoder.append(np.array(state.known_out_of_trump, dtype=np.float32))
        
        # Concatenate all
        return np.concatenate(encoder)


class Policy45sNetwork(nn.Module):
    """
    Neural network that outputs:
    1. Policy: probability distribution over legal actions
    2. Value: expected score from this position
    """
    
    def __init__(self, input_size=178, hidden_size=256):
        super().__init__()
        
        # Shared trunk
        self.trunk = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
        )
        
        # Policy head (which card to play)
        self.policy_head = nn.Sequential(
            nn.Linear(hidden_size, 128),
            nn.ReLU(),
            nn.Linear(128, 52)  # Logits for each possible card
        )
        
        # Value head (expected score)
        self.value_head = nn.Sequential(
            nn.Linear(hidden_size, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
            nn.Tanh()  # Normalized score estimate
        )
    
    def forward(self, state):
        """
        state: (batch_size, input_size) tensor
        Returns: (policy_logits, value)
        """
        features = self.trunk(state)
        policy_logits = self.policy_head(features)
        value = self.value_head(features)
        return policy_logits, value
    
    def get_action_probs(self, state, legal_cards, device='cpu'):
        """
        Get probability distribution over legal cards.
        
        state: encoded state vector
        legal_cards: list of Card objects that are legal to play
        device: torch device to use
        
        Returns: (card, probability) for each legal card
        """
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(device)
            policy_logits, value = self.forward(state_tensor)
            
            # Mask illegal actions
            encoder = Card45sEncoder()
            legal_indices = [encoder.encode_card(card) for card in legal_cards]
            
            # Set illegal actions to very negative logit
            mask = torch.full((52,), float('-inf')).to(device)
            mask[legal_indices] = 0.0
            
            masked_logits = policy_logits[0] + mask
            
            # Softmax to get probabilities
            probs = F.softmax(masked_logits, dim=0)
            
            # Extract probabilities for legal cards
            card_probs = [(legal_cards[i], probs[legal_indices[i]].item()) 
                         for i in range(len(legal_cards))]
            
            return card_probs, value.item()
    
    def select_action(self, state, legal_cards, temperature=1.0, device='cpu'):
        """
        Select an action using the policy.
        
        temperature: 
            - 1.0 = sample from policy
            - 0.0 = greedy (pick best)
            - >1.0 = more exploration
        """
        card_probs, value = self.get_action_probs(state, legal_cards, device)
        
        if temperature == 0.0:
            # Greedy
            return max(card_probs, key=lambda x: x[1])[0], value
        
        # Sample from distribution
        cards = [c for c, _ in card_probs]
        probs = np.array([p for _, p in card_probs])
        
        # Apply temperature
        if temperature != 1.0:
            probs = probs ** (1.0 / temperature)
        
        # Normalize to ensure sum = 1.0
        probs = probs / probs.sum()
        
        chosen_card = np.random.choice(len(cards), p=probs)
        return cards[chosen_card], value


def count_parameters(model):
    """Count trainable parameters"""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == "__main__":
    # Test the model
    print("Testing RL Model...")
    
    # Create encoder
    encoder = Card45sEncoder()
    
    # Create dummy game state
    deck = Deck().shuffle()
    hands = [deck.deal(5) for _ in range(4)]
    
    state = GameState(
        hands=hands,
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
    
    # Encode state
    encoded = encoder.encode_game_state(state, player_idx=0)
    print(f"State vector size: {len(encoded)}")
    
    # Create model
    model = Policy45sNetwork(input_size=len(encoded))
    print(f"Model parameters: {count_parameters(model):,}")
    
    # Test forward pass
    legal_cards = hands[0][:3]  # Pretend only 3 cards are legal
    card, value = model.select_action(encoded, legal_cards, temperature=1.0)
    print(f"Selected card: {card}")
    print(f"Value estimate: {value:.3f}")
    
    print("\n✓ Model test passed!")
