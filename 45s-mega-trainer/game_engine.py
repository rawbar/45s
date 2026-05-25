"""
45s Card Game Engine
Core game logic for the card game 45s
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum
import random

class Suit(Enum):
    SPADES = '♠'
    HEARTS = '♥'
    DIAMONDS = '♦'
    CLUBS = '♣'

RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

@dataclass
class Card:
    rank: str
    suit: Suit
    
    def __str__(self):
        return f"{self.rank}{self.suit.value}"
    
    def __repr__(self):
        return str(self)
    
    def __eq__(self, other):
        return self.rank == other.rank and self.suit == other.suit
    
    def __hash__(self):
        return hash((self.rank, self.suit))

class Deck:
    """Standard 52-card deck"""
    
    def __init__(self):
        self.cards = [Card(rank, suit) for suit in Suit for rank in RANKS]
    
    def shuffle(self):
        random.shuffle(self.cards)
        return self
    
    def deal(self, num_cards: int) -> List[Card]:
        """Deal num_cards from the deck"""
        dealt = self.cards[:num_cards]
        self.cards = self.cards[num_cards:]
        return dealt

def get_trump_rank(card: Card, trump_suit: Suit) -> int:
    """
    Get trump ranking value for a card.
    Returns -1 if not trump.
    Higher values beat lower values.
    """
    if card.rank == 'A' and card.suit == Suit.HEARTS:
        return 100  # A♥ is always 3rd best trump
    
    if card.suit != trump_suit:
        return -1
    
    # Trump suit rankings
    if card.rank == '5':
        return 102  # 5 of trump is best
    if card.rank == 'J':
        return 101  # J of trump is 2nd best
    if card.rank == 'A':
        return 99   # A of trump is 4th best (after A♥)
    if card.rank == 'K':
        return 98
    if card.rank == 'Q':
        return 97
    
    # Remaining trump (spot) cards - order MUST match index.html getTrumpRank exactly.
    # JS: red ♥/♦  -> 80 + ['2','3','4','6','7','8','9','10'].indexOf(rank)  (2 low, 10 high)
    #     black ♠/♣ -> 80 + ['10','9','8','7','6','4','3','2'].indexOf(rank) (10 low, 2 high)
    if trump_suit in [Suit.HEARTS, Suit.DIAMONDS]:
        order = ['2', '3', '4', '6', '7', '8', '9', '10']
    else:
        order = ['10', '9', '8', '7', '6', '4', '3', '2']

    try:
        return 80 + order.index(card.rank)
    except ValueError:
        return -1

def get_offsuit_rank(card: Card) -> int:
    """
    Get ranking for non-trump cards.
    Higher values beat lower values.
    """
    if card.suit in [Suit.HEARTS, Suit.DIAMONDS]:
        # Red suits: K high, A low
        order = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    else:
        # Black suits: K high, A second-high
        order = ['10', '9', '8', '7', '6', '5', '4', '3', '2', 'A', 'J', 'Q', 'K']
    
    try:
        return order.index(card.rank)
    except ValueError:
        return -1

def is_trump(card: Card, trump_suit: Suit) -> bool:
    """Check if a card is trump"""
    return (card.rank == 'A' and card.suit == Suit.HEARTS) or card.suit == trump_suit

def card_beats(card1: Card, card2: Card, trump_suit: Suit, led_suit: Suit) -> bool:
    """
    Returns True if card1 beats card2.
    Trump always beats non-trump.
    Led suit beats off-suit.
    """
    t1 = get_trump_rank(card1, trump_suit)
    t2 = get_trump_rank(card2, trump_suit)
    
    # Both trump - higher rank wins
    if t1 >= 0 and t2 >= 0:
        return t1 > t2
    
    # One trump - trump wins
    if t1 >= 0:
        return True
    if t2 >= 0:
        return False
    
    # Neither trump - must follow led suit
    if card1.suit != led_suit:
        return False
    if card2.suit != led_suit:
        return True
    
    # Both same suit - higher rank wins
    return get_offsuit_rank(card1) > get_offsuit_rank(card2)

def is_top_three_trump(card: Card, trump_suit: Suit) -> bool:
    """5 of trump, J of trump, or A♥ — the three reneging-eligible trump."""
    return ((card.rank == '5' and card.suit == trump_suit) or
            (card.rank == 'J' and card.suit == trump_suit) or
            (card.rank == 'A' and card.suit == Suit.HEARTS))


def get_playable_cards(hand: List[Card], trump_suit: Suit, led_card: Optional[Card]) -> List[Card]:
    """
    Faithful port of index.html getPlayableCards (reneging rules included).

    Trump led:
      - no trump in hand -> whole hand
      - else split trump into `must` (non-top-3, OR top-3 not higher than led)
        and `can_renege` (top-3 trump strictly higher than led rank).
        must non-empty -> must + can_renege ; must empty -> whole hand (renege).
    Offsuit led:
      - follow = same led suit AND not trump
      - follow empty -> whole hand ; else follow + all trump
    """
    if not hand:
        return []
    if not led_card:
        return hand.copy()

    led_suit = led_card.suit

    if is_trump(led_card, trump_suit):
        trump_cards = [c for c in hand if is_trump(c, trump_suit)]
        if not trump_cards:
            return hand.copy()
        led_rank = get_trump_rank(led_card, trump_suit)
        must, can_renege = [], []
        for c in trump_cards:
            if is_top_three_trump(c, trump_suit) and get_trump_rank(c, trump_suit) > led_rank:
                can_renege.append(c)
            else:
                must.append(c)
        return (must + can_renege) if must else hand.copy()

    follow = [c for c in hand if c.suit == led_suit and not is_trump(c, trump_suit)]
    trumps = [c for c in hand if is_trump(c, trump_suit)]
    return hand.copy() if not follow else (follow + trumps)

@dataclass
class GameState:
    """Represents the current state of a 45s game"""
    hands: List[List[Card]]  # 4 players
    trump_suit: Suit
    bid_winner: int  # Player index 0-3
    high_bid: int
    dealer: int
    
    # Trick state
    current_trick: List[Tuple[int, Card]]  # [(player_idx, card), ...]
    trick_leader: int
    tricks_won: List[int]  # [team0_tricks, team1_tricks]
    
    # Round state
    trick_num: int  # 1-5
    cards_drawn: List[int]  # How many cards each player drew
    cards_played: List[Card]  # All cards played this round
    known_out_of_trump: List[bool]  # Which players are known to be out of trump
    bidder_lost_trick: bool
    
    # High trick tracking
    high_trump_rank: int = -1  # Rank of highest trump played so far
    high_trump_winner: int = -1  # Player who played highest trump

    # Rich void/renege tracking (mirrors index.html knownVoids).
    # One dict per player: {'trump': True|'reneging', 'possibleTrump': [ids],
    #                       'noLowTrump': bool, '<suit char>': True}
    known_voids: Optional[List[dict]] = None

    # Game-context (set by game_runner for score-conditioned endgame rules;
    # None in round-context harnesses → score rules become no-ops).
    team_scores: Optional[List[int]] = None   # [team0, team1] PRE-round
    winning_total: int = 120

    # Cutthroat per-seat trick tracking (set by _play_round; partner mode
    # leaves these defaulted — partner AI has no need for per-player counts).
    # Used by improved_ai cutthroat coalition rules (C1/C2) to detect
    # set-locked / made-locked mid-round.
    player_tricks: Optional[List[int]] = None      # [p0, p1, p2, p3] tricks won SO FAR
    high_trump_player: int = -1                    # seat that owns the high-trump trick so far

    def get_team(self, player: int) -> int:
        """Get team number (0 or 1) for a player"""
        return player % 2
    
    def get_partner(self, player: int) -> int:
        """Get partner's player index"""
        return (player + 2) % 4
    
    def copy(self):
        """Create a deep copy of the game state"""
        import copy
        return copy.deepcopy(self)

def evaluate_trick(trick: List[Tuple[int, Card]], trump_suit: Suit, leader: int) -> int:
    """
    Evaluate a completed trick and return the winner's player index.
    """
    if not trick:
        return leader
    
    _, led_card = trick[0]
    led_suit = led_card.suit
    
    winner_idx = 0
    winner_card = led_card
    
    for i in range(1, len(trick)):
        _, card = trick[i]
        if card_beats(card, winner_card, trump_suit, led_suit):
            winner_idx = i
            winner_card = card
    
    # Convert trick position to player index
    return (leader + winner_idx) % 4

def calculate_points(tricks_won: List[int], bid_winner_team: int, high_bid: int, high_trick_winner: int) -> Tuple[int, int]:
    """
    Calculate points for both teams.
    Returns (team0_score, team1_score)
    
    high_trick_winner: player index who won the trick with highest trump
    """
    bidder_tricks = tricks_won[bid_winner_team]
    defender_tricks = tricks_won[1 - bid_winner_team]
    
    bidder_points = bidder_tricks * 5
    defender_points = defender_tricks * 5
    
    # Add 5 points for high trick
    high_trick_team = high_trick_winner % 2
    if high_trick_team == bid_winner_team:
        bidder_points += 5
    else:
        defender_points += 5
    
    # Check if bidder made their bid
    made_it = bidder_points >= high_bid
    
    if made_it:
        bidder_score = bidder_points
    else:
        bidder_score = -high_bid  # Set - lose bid amount
    
    scores = [0, 0]
    scores[bid_winner_team] = bidder_score
    scores[1 - bid_winner_team] = defender_points
    
    return tuple(scores)

if __name__ == "__main__":
    # Quick test
    deck = Deck().shuffle()
    hand = deck.deal(5)
    print("Sample hand:", hand)
    
    trump = Suit.HEARTS
    print(f"\nTrump: {trump.value}")
    
    for card in hand:
        trump_rank = get_trump_rank(card, trump)
        if trump_rank >= 0:
            print(f"{card} is trump (rank: {trump_rank})")
        else:
            print(f"{card} is not trump (offsuit rank: {get_offsuit_rank(card)})")
