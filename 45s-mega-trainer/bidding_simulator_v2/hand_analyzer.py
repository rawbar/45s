"""
hand_analyzer.py — Hand feature extraction and categorization

Extracts all features from a 5-card hand for a given trump suit,
computes the hand category label used in reporting, and determines
which bid levels are worth testing.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dataclasses import dataclass
from typing import List, Tuple, Optional
from game_engine import Card, Suit, get_trump_rank, is_trump


# ─────────────────────────────────────────────────────────────────────────────
# HandProfile
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class HandProfile:
    # Trump features
    trump_suit:       Suit
    trump_count:      int   # total trump cards (0-5)
    has_5:            bool  # 5 of trump
    has_j:            bool  # J of trump
    has_ah:           bool  # A♥ (always trump)
    has_at:           bool  # A of trump (non-hearts)
    has_k:            bool  # K of trump
    has_q:            bool  # Q of trump
    high_trump_count: int   # count of {5, J, A♥, A, K, Q} held
    top_sequence:     int   # unbroken run from top: 0=no5, 1=5, 2=5+J, 3=5+J+A♥, 4=5+J+A♥+A

    # Off-suit features
    offsuit_aces:  int  # aces in non-trump suits (0-3)
    offsuit_kings: int  # kings in non-trump suits (0-3)
    void_count:    int  # non-trump suits with 0 cards (0-3)

    def as_row(self) -> dict:
        """Return dict matching the SQLite hands table columns."""
        return {
            'trump_suit':       self.trump_suit.value,
            'trump_count':      self.trump_count,
            'has_5':            int(self.has_5),
            'has_j':            int(self.has_j),
            'has_ah':           int(self.has_ah),
            'has_at':           int(self.has_at),
            'has_k':            int(self.has_k),
            'has_q':            int(self.has_q),
            'high_trump_count': self.high_trump_count,
            'top_sequence':     self.top_sequence,
            'offsuit_aces':     self.offsuit_aces,
            'offsuit_kings':    self.offsuit_kings,
            'void_count':       self.void_count,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────────────────────

def analyze_hand(hand: List[Card], trump_suit: Suit) -> HandProfile:
    """Extract all features from a 5-card hand for the given trump suit."""
    has_5  = any(c.rank == '5' and c.suit == trump_suit for c in hand)
    has_j  = any(c.rank == 'J' and c.suit == trump_suit for c in hand)
    has_ah = any(c.rank == 'A' and c.suit == Suit.HEARTS for c in hand)
    has_at = (trump_suit != Suit.HEARTS and
              any(c.rank == 'A' and c.suit == trump_suit for c in hand))
    has_k  = any(c.rank == 'K' and c.suit == trump_suit for c in hand)
    has_q  = any(c.rank == 'Q' and c.suit == trump_suit for c in hand)

    trump_count = sum(1 for c in hand if is_trump(c, trump_suit))

    high_trump_count = sum(1 for c in hand
                           if is_trump(c, trump_suit)
                           and c.rank in ('5', 'J', 'K', 'Q', 'A'))

    # top_sequence: how many of the very top trump you hold in unbroken order
    if not has_5:
        top_seq = 0
    elif not has_j:
        top_seq = 1
    elif not has_ah:
        top_seq = 2
    elif not has_at:
        top_seq = 3
    else:
        top_seq = 4

    # Off-suit features
    non_trump_suits = [s for s in Suit if s != trump_suit]
    # Cards by non-trump suit
    offsuit_cards = [c for c in hand if not is_trump(c, trump_suit)]

    offsuit_aces  = sum(1 for c in offsuit_cards if c.rank == 'A')
    offsuit_kings = sum(1 for c in offsuit_cards if c.rank == 'K')

    # Voids: non-trump suits with 0 cards
    void_count = 0
    for s in non_trump_suits:
        if not any(c.suit == s and not is_trump(c, trump_suit) for c in hand):
            void_count += 1

    return HandProfile(
        trump_suit=trump_suit,
        trump_count=trump_count,
        has_5=has_5,
        has_j=has_j,
        has_ah=has_ah,
        has_at=has_at,
        has_k=has_k,
        has_q=has_q,
        high_trump_count=high_trump_count,
        top_sequence=top_seq,
        offsuit_aces=offsuit_aces,
        offsuit_kings=offsuit_kings,
        void_count=void_count,
    )


def find_best_trump_suit(hand: List[Card]) -> Suit:
    """
    Find the trump suit that gives this hand the strongest position.
    Priority: has_5 (weight 10) > has_j (weight 5) > trump_count.
    """
    best_suit  = Suit.SPADES
    best_score = -1

    for suit in Suit:
        count  = sum(1 for c in hand if is_trump(c, suit))
        has_5  = any(c.rank == '5' and c.suit == suit for c in hand)
        has_j  = any(c.rank == 'J' and c.suit == suit for c in hand)
        score  = count + (10 if has_5 else 0) + (5 if has_j else 0)

        if score > best_score:
            best_score = score
            best_suit  = suit

    return best_suit


# ─────────────────────────────────────────────────────────────────────────────
# Viable bid filter
# ─────────────────────────────────────────────────────────────────────────────

def is_viable_bid(profile: HandProfile, bid: int) -> bool:
    """
    Returns True if this bid level is worth testing for this hand.
    Skips clearly unrealistic bids to save compute and keep data clean.
    """
    if bid == 15:
        return True   # Always test 15 — even weak hands face forced bids
    if bid == 20:
        return profile.trump_count >= 2 or profile.has_5 or profile.has_j
    if bid == 25:
        return profile.has_5 or profile.has_j or profile.trump_count >= 4
    if bid == 30:
        return (profile.has_5 or profile.has_j) and profile.trump_count >= 3
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Category label
# ─────────────────────────────────────────────────────────────────────────────

def get_category(profile: HandProfile) -> str:
    """
    Generate a human-readable category string for reporting.
    Examples: 'GUARANTEED_30', '5_J_T4', 'NO_HIGH_T3_A1'
    """
    # Guaranteed hands
    if profile.top_sequence >= 4:
        return 'GUARANTEED_30'
    if profile.top_sequence == 3 and profile.trump_count >= 4:
        return 'NEAR_GUARANTEED_30'

    # Build base from high trump held
    parts = []
    if profile.has_5:  parts.append('5')
    if profile.has_j:  parts.append('J')
    if profile.has_ah: parts.append('AH')
    if profile.has_at: parts.append('AT')
    if not parts:      parts.append('NO_HIGH')

    parts.append(f"T{profile.trump_count}")

    base = '_'.join(parts)

    # Off-suit modifiers
    mods = []
    if profile.offsuit_aces  >= 2: mods.append(f"A{profile.offsuit_aces}")
    elif profile.offsuit_aces == 1: mods.append('A1')
    if profile.void_count    >= 2: mods.append(f"V{profile.void_count}")
    elif profile.void_count  == 1: mods.append('V1')

    if mods:
        return base + '_' + '_'.join(mods)
    return base
