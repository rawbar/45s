"""
deck_generator.py — GPU-accelerated batch deck generation

Uses torch.randperm on CUDA to generate N shuffled decks in a single GPU call,
keeping CPU workers fed without deck-generation idle time.

Falls back to numpy if CUDA is unavailable.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
from typing import List, Tuple
from game_engine import Card, Suit, Deck

# ─────────────────────────────────────────────────────────────────────────────
# Build the canonical ordered card list (stable index → Card mapping)
# ─────────────────────────────────────────────────────────────────────────────

def _build_all_cards() -> List[Card]:
    """Return all 52 cards in a fixed, repeatable order."""
    d = Deck()
    return list(d.cards)          # Deck() is unshuffled

ALL_CARDS = _build_all_cards()
N_CARDS   = len(ALL_CARDS)        # 52


# ─────────────────────────────────────────────────────────────────────────────
# GPU / CPU detection
# ─────────────────────────────────────────────────────────────────────────────

def _detect_gpu() -> Tuple[bool, str]:
    """Returns (gpu_available, device_name_or_note)."""
    try:
        import torch
        if torch.cuda.is_available():
            return True, torch.cuda.get_device_name(0)
        return False, "CUDA not available"
    except ImportError:
        return False, "PyTorch not installed"


GPU_AVAILABLE, GPU_NAME = _detect_gpu()


# ─────────────────────────────────────────────────────────────────────────────
# DeckGenerator
# ─────────────────────────────────────────────────────────────────────────────

class DeckGenerator:
    """
    Generates batches of shuffled decks efficiently.

    GPU path:  torch.rand(N, 52) on CUDA → argsort → 52 permutations in one call
    CPU path:  np.random.permutation repeated N times

    Each generated deck is a List[Card] of all 52 cards in shuffled order.
    Callers slice the deck into hands: deck[:5], deck[5:10], etc.
    """

    def __init__(self, use_gpu: bool = True):
        self.use_gpu = use_gpu and GPU_AVAILABLE
        self._torch  = None
        if self.use_gpu:
            import torch as _t
            self._torch = _t

    @property
    def device_name(self) -> str:
        return GPU_NAME if self.use_gpu else "CPU (numpy)"

    def generate_batch(self, n: int) -> List[List[Card]]:
        """
        Return n shuffled decks.
        Each deck is a list of all 52 Card objects.
        """
        if self.use_gpu:
            return self._gpu_batch(n)
        return self._cpu_batch(n)

    def _gpu_batch(self, n: int) -> List[List[Card]]:
        """Generate n permutations with a single GPU call, transfer to CPU."""
        torch = self._torch
        # torch.rand(N, 52) then argsort gives N independent permutations
        rand_vals = torch.rand(n, N_CARDS, device='cuda')
        indices   = torch.argsort(rand_vals, dim=1).cpu().numpy()  # (N, 52) int64
        return [[ALL_CARDS[i] for i in row] for row in indices]

    def _cpu_batch(self, n: int) -> List[List[Card]]:
        """CPU fallback using numpy."""
        return [
            [ALL_CARDS[i] for i in np.random.permutation(N_CARDS)]
            for _ in range(n)
        ]

    def deal_from_deck(self, deck: List[Card]):
        """
        Slice a shuffled deck into the standard game deal:
        Returns (hands, kitty, remaining)
          hands     — List of 4 × 5-card hands
          kitty     — 3 cards
          remaining — remaining 29 cards for drawing
        """
        hands     = [deck[i*5:(i+1)*5] for i in range(4)]
        kitty     = deck[20:23]
        remaining = deck[23:]
        return hands, kitty, remaining


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: single deck
# ─────────────────────────────────────────────────────────────────────────────

_default_gen = None  # type: Optional[DeckGenerator]

def get_generator(use_gpu: bool = True) -> DeckGenerator:
    global _default_gen
    if _default_gen is None:
        _default_gen = DeckGenerator(use_gpu=use_gpu)
    return _default_gen
