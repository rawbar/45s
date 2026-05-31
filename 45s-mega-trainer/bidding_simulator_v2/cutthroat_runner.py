"""
cutthroat_runner.py — Full-game driver for the 4-player CUTTHROAT variant
(every-man-for-himself; no partner concept).

Mirrors `game_runner.play_game` but with per-player scoring:
  - Each seat banks its OWN round points (tricks*5 + high-trump bonus).
  - Bidder: if bidder's own round pts >= bid → bank own pts; else bank -bid
    (or -2*bid for a 30-for-60 bid). Defenders ALWAYS bank their own pts
    regardless of whether the bidder makes — the only thing at stake for the
    bidder is the contract; the other three players score independently.
  - Game over: first seat to >= 120 wins. On a tie (multiple seats >= 120 in
    the same round), the bidder wins the tiebreak.

Reuses `game_runner._play_round` with `return_per_player=True` for the trick
loop (single source of truth — no duplicated card-play machinery). Bidding
uses the same `Policy.decide_bid` (which forwards `cutthroat=True` when the
policy is constructed with that flag).

NOTE: at chunk A time, `improved_ai.py` is NOT yet cutthroat-gated. Card
play still treats seat+2 as "partner". The flag is threaded through
`ai_flags['cutthroat']` so chunk B can branch on it without re-plumbing.
"""

import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import List, Dict
from game_engine import Deck
from bidding_simulator_v2.bidding import find_best_trump_suit
from bidding_simulator_v2.game_runner import _play_round, MAX_ROUNDS
from bidding_simulator_v2.policy import Policy


def play_game_cutthroat(seat_policy: List[Policy], seed: int,
                        start_dealer: int = 0) -> Dict:
    """
    Play a full deterministic cutthroat game. seat_policy[seat] drives that
    seat. Each seat is independent — no team aggregation.

    `seed` fully determines every round's deal (same shuffle scheme as
    `play_game`) so a paired-seat-rotation run with the SAME seed isolates
    seat policy from deal luck.

    Returns dict:
      winner          : seat index 0..3 (bidder wins simultaneous ties)
      final_scores    : [s0, s1, s2, s3]
      rounds          : total rounds played
      bids_made       : how many bids were made by any seat
      bids_set        : how many bids were set
    """
    rng = random.Random(seed)
    scores = [0, 0, 0, 0]
    dealer = start_dealer
    rounds = 0
    made = 0
    set_ = 0
    last_bidder = -1

    while max(scores) < 120 and rounds < MAX_ROUNDS:
        rounds += 1
        d = Deck()
        rng.shuffle(d.cards)
        hands = [d.deal(5) for _ in range(4)]
        kitty = d.deal(3)
        rest = d.cards[:]

        # ── Bid phase ────────────────────────────────────────────────────────
        # Same order as partner: left of dealer first, dealer last. There is
        # NO partner in cutthroat, so partner_bid is forced to 0 on every
        # call (Policy with cutthroat=True also forces this internally in
        # bidding.decide_bid; we still pass 0 here to be explicit). The
        # opp_score we pass is the MAX of the other three seats' scores —
        # that's the most useful "how close is the threat to 120" signal in
        # a 4-player FFA. team_score is just this seat's own score.
        bids: List = [None, None, None, None]
        suits: List = [None, None, None, None]
        high_bid = 0
        order = [(dealer + 1) % 4, (dealer + 2) % 4, (dealer + 3) % 4, dealer]
        for p in order:
            ts = scores[p]
            os_ = max(scores[(p + 1) % 4], scores[(p + 2) % 4],
                      scores[(p + 3) % 4])
            b, s = seat_policy[p].decide_bid(hands[p], high_bid, p, dealer,
                                             ts, os_, 0,
                                             dealer_score=scores[dealer])
            bids[p] = b
            suits[p] = s
            if b > high_bid:
                high_bid = b

        # Resolve bid winner: first max scanning seats 0..3 (matches JS / partner)
        max_b = 0
        winner = dealer
        for i in range(4):
            if (bids[i] or 0) > max_b:
                max_b = bids[i]
                winner = i
        if max_b == 0:                                   # safety: dealer bagged 15
            winner = dealer
            max_b = 15
            suits[winner] = find_best_trump_suit(hands[winner])['suit']

        trump = suits[winner] or find_best_trump_suit(hands[winner])['suit']
        last_bidder = winner

        # ── Play the round (reuse partner-mode trick loop) ───────────────────
        # return_per_player=True gives us raw per-seat pts; we then apply the
        # cutthroat bidder-make/set rule (different from partner-team rule).
        # pre_round_scores = real per-seat GAME totals at round start
        # (NOT per-round pts). cutthroat L1/L2/L3 read this to detect
        # bidder-winning-game (L3), leader self-nickel-grab (L1), and
        # don't-help-the-leader (L2). pre_scores stays = scores[:] for
        # the legacy team_scores=[t0,t1] partner-style API (cutthroat
        # passes 4-vec here too, but team_scores is downstream of an
        # is-partner-mode flag → no effect in cutthroat AI path).
        _t0, _t1, per_player = _play_round(
            winner, max_b, trump, hands, kitty, rest, seat_policy,
            pre_scores=scores[:], return_per_player=True,
            pre_round_scores=scores[:],
        )

        bidder_pts = per_player[winner]
        bidder_made = bidder_pts >= max_b

        round_delta = [0, 0, 0, 0]
        for p in range(4):
            if p == winner:
                if bidder_made:
                    round_delta[p] = bidder_pts
                else:
                    # 30-for-60: a bid of 30 doubles the set penalty.
                    round_delta[p] = -2 * max_b if max_b == 30 else -max_b
            else:
                # Defenders always bank their own pts — defender pts are
                # independent in cutthroat (5*own_tricks + maybe high-trump
                # bonus), not the negation of the bidder's set.
                round_delta[p] = per_player[p]

        for p in range(4):
            scores[p] += round_delta[p]

        if bidder_made:
            made += 1
        else:
            set_ += 1

        if max(scores) >= 120:
            break
        dealer = (dealer + 1) % 4

    # Decide winner: first seat to 120; on tie, bidder wins.
    at_120 = [i for i in range(4) if scores[i] >= 120]
    if len(at_120) == 1:
        winner_seat = at_120[0]
    elif len(at_120) >= 2:
        # Simultaneous tie → bidder of the deciding round wins.
        if last_bidder in at_120:
            winner_seat = last_bidder
        else:
            # bidder didn't reach 120 but multiple defenders did — pick
            # highest score, ties broken by seat order (rare edge case).
            winner_seat = max(at_120, key=lambda s: (scores[s], -s))
    else:
        # MAX_ROUNDS hit without anyone reaching 120 — pick top score.
        winner_seat = max(range(4), key=lambda s: (scores[s], -s))

    return {
        'winner': winner_seat,
        'final_scores': scores,
        'rounds': rounds,
        'bids_made': made,
        'bids_set': set_,
    }
