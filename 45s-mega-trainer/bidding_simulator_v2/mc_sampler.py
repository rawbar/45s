"""
mc_sampler.py — determinized opponent-hand sampler for Monte Carlo card play.

Given the deciding player's view of a mid-round state, deal the unseen cards
to the other 3 players so each sampled "world" is consistent with everything
public: cards played, current trick, per-opponent knownVoids (suit voids,
trump void, reneging-only + possibleTrump), and exact remaining hand sizes.

A biased sampler => confidently-wrong MC, so this is the crux of the MC work
and is covered by a constraint test suite (test_sampler.py).

PIMC convention: the candidate pool for opponents is everything the decider
hasn't seen (52 − my hand − cards played). Only sum(remaining hand sizes)
of them are actually dealt; the rest are implicitly kitty/discard/deck and
left out — we don't need to know which, just produce a consistent world.
"""

import random
from typing import List, Tuple, Dict
from game_engine import Card, Suit, RANKS, get_trump_rank, is_trump


def _full_deck() -> List[Card]:
    return [Card(r, s) for s in Suit for r in RANKS]


def _cid(c: Card) -> str:
    return f"{c.rank}{c.suit.value}"


def _forbidden_for(opp_voids: dict, trump: Suit):
    """Return a predicate card->bool: True if `opp` may NOT hold this card."""
    v = opp_voids or {}
    void_suits = {k for k, val in v.items()
                  if k not in ('trump', 'possibleTrump', 'noLowTrump') and val is True}
    trump_state = v.get('trump')          # True | 'reneging' | None
    possible = set(v.get('possibleTrump', []) or [])

    def forbidden(c: Card) -> bool:
        ct = get_trump_rank(c, trump) >= 0
        # suit void: no card of that suit (trump-suit handled via trump rules)
        if c.suit.value in void_suits and not ct:
            return True
        if ct:
            if trump_state is True:
                return True                      # fully void in trump
            if trump_state == 'reneging':
                # may only hold the specific renege-eligible top-3 trump
                return _cid(c) not in possible
        return False
    return forbidden


def remaining_counts(player: int,
                     my_hand: List[Card],
                     play_history: List[Tuple[int, Card]],
                     current_trick: List[Tuple[int, Card]]) -> List[int]:
    """Cards still in each seat's hand. NOTE: in this codebase play_history
    accumulates per-card, so it ALREADY includes the in-progress trick —
    current_trick is a subset (its tail), so it must NOT be added again
    (that was a double-count). Count play_history only; decider from my_hand."""
    played = [0, 0, 0, 0]
    for (pi, _) in play_history:
        played[pi] += 1
    counts = [5 - played[i] for i in range(4)]
    counts[player] = len(my_hand)
    return counts


def sample_world(player: int,
                 my_hand: List[Card],
                 play_history: List[Tuple[int, Card]],
                 current_trick: List[Tuple[int, Card]],
                 known_voids: List[dict],
                 trump: Suit,
                 rng: random.Random,
                 max_repair: int = 200) -> List[List[Card]]:
    """One consistent world: list of 4 hands; hands[player] == my_hand."""
    seen = {_cid(c) for c in my_hand}
    for (_, c) in play_history:
        seen.add(_cid(c))
    for (_, c) in current_trick:
        seen.add(_cid(c))
    pool = [c for c in _full_deck() if _cid(c) not in seen]
    rng.shuffle(pool)

    counts = remaining_counts(player, my_hand, play_history, current_trick)
    others = [i for i in range(4) if i != player]
    need = {i: counts[i] for i in others}
    forb = {i: _forbidden_for(known_voids[i] if known_voids else {}, trump)
            for i in others}

    hands: Dict[int, List[Card]] = {i: [] for i in others}
    leftover: List[Card] = []

    # Greedy pass: hardest-to-place cards first (allowed by fewest opponents).
    def allowed(card):
        return [i for i in others if not forb[i](card) and len(hands[i]) < need[i]]
    pool.sort(key=lambda c: len(allowed(c)))   # constrained cards placed first
    for card in pool:
        opts = allowed(card)
        if opts:
            tgt = rng.choice(opts)
            hands[tgt].append(card)
        else:
            leftover.append(card)

    # Repair: any under-filled opponent swaps a leftover card it can hold for
    # nothing, or steals a swappable card from another opponent.
    tries = 0
    while any(len(hands[i]) < need[i] for i in others) and tries < max_repair:
        tries += 1
        short = next(i for i in others if len(hands[i]) < need[i])
        # 1) take a legal leftover
        for j, card in enumerate(leftover):
            if not forb[short](card):
                hands[short].append(leftover.pop(j))
                break
        else:
            # 2) steal from an over/at-capacity opponent a card `short` can hold
            #    and `donor` can replace from leftover (or just give it up).
            moved = False
            for donor in others:
                if donor == short or not hands[donor]:
                    continue
                for k, card in enumerate(hands[donor]):
                    if not forb[short](card):
                        hands[short].append(hands[donor].pop(k))
                        moved = True
                        break
                if moved:
                    break
            if not moved:
                break   # constraint-infeasible deal — fall through to size fill

    # Size guarantee (rare infeasible worlds): exact hand sizes matter more
    # than a perfect constraint fit for an occasional degenerate sample —
    # an imperfect world beats a crash. Fill shortfalls ignoring `forb`.
    for i in others:
        while len(hands[i]) < need[i] and leftover:
            hands[i].append(leftover.pop())
        while len(hands[i]) < need[i]:
            donor = next((d for d in others
                          if d != i and len(hands[d]) > need[d]), None)
            if donor is None:
                donor = next((d for d in others if d != i and hands[d]), None)
            if donor is None:
                break
            hands[i].append(hands[donor].pop())

    out = [None, None, None, None]
    out[player] = list(my_hand)
    for i in others:
        out[i] = hands[i]
    return out


def sample_worlds(player, my_hand, play_history, current_trick,
                   known_voids, trump, k, rng) -> List[List[List[Card]]]:
    return [sample_world(player, my_hand, play_history, current_trick,
                         known_voids, trump, rng) for _ in range(k)]
