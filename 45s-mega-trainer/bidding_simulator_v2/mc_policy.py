"""
mc_policy.py — flat determinized PIMC card-play policy + reusable
round-completion simulator + cheap rollout policies.

MCPolicy overrides ONLY choose_card (bidding/discard stay champion) so a
measured win-rate delta is attributable to card play alone. For each
candidate legal card it samples K consistent worlds (mc_sampler), plays
the round out with a cheap rollout policy, and picks the card with the
best mean decider-team round points. Anytime: hard cap on rollouts.

Instrumentation: per-decision rollout count + wall time (self.stats),
reported device-independently as node counts.
"""

import time, random
from typing import List, Tuple
from game_engine import (Card, Suit, GameState, get_trump_rank,
                         get_playable_cards, evaluate_trick)
from bidding_simulator_v2.policy import Policy
from bidding_simulator_v2.mc_sampler import sample_world, _cid
from bidding_simulator_v2.round_runner import _update_known_voids
from bidding_simulator_v2.improved_ai import ImprovedAI


# ── cheap rollout policies ───────────────────────────────────────────────────

def _off(c):
    """Within-suit offsuit strength index (higher = stronger). Matches the
    engine's offsuit ranking; shared by greedy + indep rollouts."""
    order = (['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
             if c.suit in (Suit.HEARTS, Suit.DIAMONDS)
             else ['10', '9', '8', '7', '6', '5', '4', '3', '2', 'A', 'J', 'Q', 'K'])
    return order.index(c.rank)


def _beats(c, b, trump, led):
    """True if card c currently beats card b given trump + led suit."""
    tc, tb = get_trump_rank(c, trump), get_trump_rank(b, trump)
    if tc >= 0 or tb >= 0:
        return tc > tb                       # trump > lower trump / non-trump
    cl = led is not None and c.suit == led.suit
    bl = led is not None and b.suit == led.suit
    if cl and not bl:
        return True
    if bl and not cl:
        return False
    if cl and bl:
        return _off(c) > _off(b)
    return False


def rollout_random(seat, hand, trump, trick, trick_leader, rng):
    led = trick[0][1] if trick else None
    legal = get_playable_cards(hand, trump, led)
    return rng.choice(legal) if legal else hand[0]


def rollout_greedy(seat, hand, trump, trick, trick_leader, rng):
    """~10-line greedy: lead lowest; following, win cheapest or dump lowest."""
    led = trick[0][1] if trick else None
    legal = get_playable_cards(hand, trump, led)
    if not legal:
        return hand[0]

    def lo(c):
        r = get_trump_rank(c, trump)
        return r + 200 if r >= 0 else _off(c)
    if led is None:
        return min(legal, key=lo)
    # cheapest card that currently beats the led card, else lowest
    beat = [c for c in legal if get_trump_rank(c, trump) >= 0
            or (c.suit == led.suit and _off(c) > _off(led)
                and get_trump_rank(led, trump) < 0)]
    return min(beat, key=lo) if beat else min(legal, key=lo)


def rollout_indep(seat, hand, trump, trick, trick_leader, rng):
    """Competent generic 45s player, deliberately DECORRELATED from the
    champion ImprovedAI: no bid inference, no void/known-OOT rules, no
    min-win / hold-up / endgame / 2nd-man-low / signalling logic. Just
    sound trick mechanics + partner awareness. This is the decorrelated
    steel-man rollout: if PIMC still wins with THIS as its world model,
    the gain is real (not a self-referential artifact of rolling out the
    champion against itself)."""
    led = trick[0][1] if trick else None
    legal = get_playable_cards(hand, trump, led)
    if not legal:
        return hand[0]
    if len(legal) == 1:
        return legal[0]

    def tr(c):
        return get_trump_rank(c, trump)

    def strength(c):                          # absolute lowest-first sort key
        r = tr(c)
        return 1000 + r if r >= 0 else _off(c)

    # LEADING: draw with a big trump if held, else conserve (lead low offsuit)
    if not trick:
        big = [c for c in legal if tr(c) >= 99]      # A-trump or higher
        if big:
            return min(big, key=strength)
        nont = [c for c in legal if tr(c) < 0]
        return min(nont or legal, key=strength)

    # FOLLOWING: find current best card + who played it
    best_seat, best_card = trick[0]
    for s, c in trick[1:]:
        if _beats(c, best_card, trump, led):
            best_seat, best_card = s, c
    partner_winning = (best_seat % 2 == seat % 2)

    if partner_winning:
        nont = [c for c in legal if tr(c) < 0]       # don't waste a winner
        return min(nont or legal, key=strength)
    winners = [c for c in legal if _beats(c, best_card, trump, led)]
    if winners:
        return min(winners, key=strength)            # win as cheaply as can
    nont = [c for c in legal if tr(c) < 0]            # can't win → dump low
    return min(nont or legal, key=strength)


# ── reusable round completion ────────────────────────────────────────────────

def simulate_round_completion(hands, trump, bidder, bid,
                              current_trick, trick_leader, trick_num,
                              tricks_won, htr, htp,
                              cards_played, play_history,
                              known_voids, known_oot,
                              rollout, rng,
                              cards_drawn=None, smart=False) -> Tuple[int, int]:
    """Play the round to its end from an arbitrary mid-trick state. Either a
    cheap `rollout(seat, hand, trump, led, rng)` chooses each remaining card,
    or (smart=True) the champion ImprovedAI does (the steel-man rollout).
    Returns (team0_round_points, team1_round_points)."""
    hands = [h[:] for h in hands]
    trick = list(current_trick)
    cards_played = list(cards_played)
    play_history = list(play_history)
    known_voids = [dict(v) for v in known_voids]
    known_oot = list(known_oot)
    tricks_won = list(tricks_won)
    cd = cards_drawn if cards_drawn is not None else [3, 3, 3, 3]

    while tricks_won[0] + tricks_won[1] < 5:
        cur = (trick_leader + len(trick)) % 4
        while len(trick) < 4:
            led = trick[0][1] if trick else None
            if smart:
                st = GameState(
                    hands=[h[:] for h in hands], trump_suit=trump,
                    bid_winner=bidder, high_bid=bid, dealer=0,
                    current_trick=list(trick), trick_leader=trick_leader,
                    tricks_won=list(tricks_won), trick_num=trick_num,
                    cards_drawn=list(cd), cards_played=list(cards_played),
                    known_out_of_trump=list(known_oot),
                    bidder_lost_trick=False,
                    high_trump_rank=htr, high_trump_winner=htp,
                    known_voids=[dict(v) for v in known_voids])
                card = ImprovedAI(cur).choose_card(st, list(play_history))
            else:
                card = rollout(cur, hands[cur], trump, list(trick),
                               trick_leader, rng)
            legal = get_playable_cards(hands[cur], trump, led)
            if card not in legal:
                card = legal[0]
            hands[cur].remove(card)
            trick.append((cur, card))
            play_history.append((cur, card))
            cards_played.append(card)
            tr = get_trump_rank(card, trump)
            if tr > htr:
                htr, htp = tr, cur
            cur = (cur + 1) % 4
        all_ids = {_cid(c) for c in cards_played}
        _update_known_voids(trick, trick_leader, trump, all_ids,
                            known_voids, known_oot)
        winner = evaluate_trick(trick, trump, trick_leader)
        tricks_won[winner % 2] += 1
        trick_leader = winner
        trick = []
        trick_num += 1

    pts = [tricks_won[0] * 5, tricks_won[1] * 5]
    if htp >= 0:
        pts[htp % 2] += 5
    bteam = bidder % 2
    out = [0, 0]
    out[bteam] = pts[bteam] if pts[bteam] >= bid else -bid
    out[1 - bteam] = pts[1 - bteam]
    return out[0], out[1]


# ── PIMC policy ──────────────────────────────────────────────────────────────

class MCPolicy(Policy):
    def __init__(self, k_worlds=40, rollout='random', max_rollouts=4000, seed=12345):
        self.name = f"mc_k{k_worlds}_{rollout}"
        self.k = k_worlds
        self.smart = (rollout == 'heuristic')
        self.rollout = {'greedy': rollout_greedy,
                        'indep': rollout_indep}.get(rollout, rollout_random)
        self.max_rollouts = max_rollouts
        self._rng = random.Random(seed)
        self.stats = {'decisions': 0, 'rollouts': 0, 'time': 0.0,
                      'by_trick': {}}

    def choose_card(self, seat: int, state: GameState,
                    play_history: List[Tuple[int, Card]]) -> Card:
        trump = state.trump_suit
        my_hand = state.hands[seat]
        ctrick = state.current_trick
        led = ctrick[0][1] if ctrick else None
        legal = get_playable_cards(my_hand, trump, led)
        if len(legal) <= 1:
            return legal[0] if legal else my_hand[0]

        t0 = time.perf_counter()
        kv = state.known_voids or [{}, {}, {}, {}]
        # budget: split rollouts across worlds, >=1 world
        per = max(1, self.max_rollouts // max(1, len(legal)))
        kw = min(self.k, per)
        totals = {i: 0.0 for i in range(len(legal))}
        counts = {i: 0 for i in range(len(legal))}
        n_roll = 0
        for _ in range(kw):
            world = sample_world(seat, my_hand, play_history, list(ctrick),
                                 kv, trump, self._rng)
            for idx, cand in enumerate(legal):
                h = [w[:] for w in world]
                h[seat] = [c for c in h[seat] if _cid(c) != _cid(cand)]
                ct = list(ctrick) + [(seat, cand)]
                tr = get_trump_rank(cand, trump)
                htr, htp = state.high_trump_rank, state.high_trump_winner
                if tr > htr:
                    htr, htp = tr, seat
                t0p, t1p = simulate_round_completion(
                    h, trump, state.bid_winner, state.high_bid,
                    ct, state.trick_leader, state.trick_num,
                    list(state.tricks_won),
                    htr, htp,
                    list(state.cards_played) + [cand],
                    list(play_history),
                    kv, state.known_out_of_trump,
                    self.rollout, self._rng,
                    cards_drawn=list(state.cards_drawn), smart=self.smart)
                myteam = seat % 2
                totals[idx] += (t0p if myteam == 0 else t1p) - \
                               (t1p if myteam == 0 else t0p)
                counts[idx] += 1
                n_roll += 1

        best = max(range(len(legal)),
                   key=lambda i: totals[i] / counts[i] if counts[i] else -1e9)
        dt = time.perf_counter() - t0
        self.stats['decisions'] += 1
        self.stats['rollouts'] += n_roll
        self.stats['time'] += dt
        bt = self.stats['by_trick'].setdefault(state.trick_num,
                                                {'n': 0, 'roll': 0, 't': 0.0})
        bt['n'] += 1; bt['roll'] += n_roll; bt['t'] += dt
        return legal[best]
