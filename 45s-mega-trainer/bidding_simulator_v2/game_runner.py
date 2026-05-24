"""
game_runner.py — Simulate a full 45s game to 120, two policies (one per team).

Faithful to index.html game loop:
  - dealer rotation each round ((dealer+1)%4)
  - bid phase: left of dealer first, dealer last; decide_bid gets live team/opp
    scores + partner's bid-so-far; dealer bagged → forced 15 (decide_bid handles)
  - winner = highest bid (first max scanning seats 0..3, matching JS resolution)
  - trump = the suit decide_bid returned for the winning bidder (pre-kitty hand)
  - bidder takes 3-card kitty, all discard/draw (5-card-draw OFF), bidder leads T1
  - 5 tricks via the faithful card AI + JS knownVoids tracking
  - round scoring: 5/trick + 5 for the trick holding the highest trump; bidder
    team scores its points if >= bid else -bid; defenders always score theirs
  - first team to >=120 wins; both >=120 same round → bidding team wins
"""

import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import List, Tuple, Dict, Optional
from game_engine import (
    Card, Suit, Deck, GameState,
    get_trump_rank, get_playable_cards, evaluate_trick,
)
from bidding_simulator_v2.bidding import find_best_trump_suit
from bidding_simulator_v2.round_runner import _update_known_voids
from bidding_simulator_v2.improved_ai import cid
from bidding_simulator_v2.policy import Policy, CHAMPION

MAX_ROUNDS = 200  # safety cap; real games end far sooner

# "Losing state": opponent is one makeable minimum bid (15 → +15) from 120.
# A team that, at some round start, faces an opponent at >= this score is in
# the spot situational rules (desperation) are meant for. Conditional metrics
# bucket on this so a rare-but-real comeback effect isn't diluted to noise.
LOSING_THRESHOLD = 105


def _play_round(bidder: int, bid: int, trump: Suit,
                hands: List[List[Card]], kitty: List[Card],
                deck_for_draw: List[Card],
                seat_policy: List[Policy],
                pre_scores: Optional[List[int]] = None,
                return_per_player: bool = False):
    """Play one round; return (team0_round_points, team1_round_points).
    pre_scores = game-level [team0, team1] BEFORE this round (for score-
    conditioned endgame play rules); None in round-only callers.

    When `return_per_player=True` (cutthroat runner), also returns a third
    element: per_player_pts[4] = each seat's own raw round points before
    bidder-make/set adjustment (= 5*tricks_won_by_seat + 5 if that seat
    won the high-trump trick). The bidder-make/set rule is per-mode
    (partner sums team, cutthroat tests bidder's own pts) so applying it
    is left to the caller. partner_mode path (return_per_player=False)
    is BIT-IDENTICAL to the prior 2-tuple return."""
    hands = [h[:] for h in hands]
    hands[bidder].extend(kitty)
    deck = deck_for_draw[:]

    cards_drawn = [0, 0, 0, 0]
    for i in range(4):
        disc = seat_policy[i].choose_discards(hands[i], trump, i == bidder, bid)
        for c in disc:
            if c in hands[i]:
                hands[i].remove(c)
        nd = max(0, 5 - len(hands[i]))
        cards_drawn[i] = nd
        for _ in range(nd):
            if deck:
                hands[i].append(deck.pop())

    tricks_won = [0, 0]
    # Per-seat trick count for cutthroat scoring. Always tracked (cheap, 4
    # ints) so the only divergence between modes is the return shape — keeps
    # the trick loop bit-identical to before.
    player_tricks = [0, 0, 0, 0]
    trick_leader = bidder
    cards_played_all: List[Card] = []
    play_history: List[Tuple[int, Card]] = []
    high_trump_rank = -1
    high_trump_player = -1
    known_oot = [False, False, False, False]
    known_voids: List[dict] = [{}, {}, {}, {}]
    bidder_lost = False

    for trick_num in range(1, 6):
        trick: List[Tuple[int, Card]] = []
        current = trick_leader
        for _ in range(4):
            state = GameState(
                hands=[h[:] for h in hands], trump_suit=trump,
                bid_winner=bidder, high_bid=bid, dealer=0,
                current_trick=trick[:], trick_leader=trick_leader,
                tricks_won=tricks_won[:], trick_num=trick_num,
                cards_drawn=cards_drawn[:], cards_played=cards_played_all[:],
                known_out_of_trump=known_oot[:], bidder_lost_trick=bidder_lost,
                high_trump_rank=high_trump_rank, high_trump_winner=high_trump_player,
                known_voids=[dict(v) for v in known_voids],
                team_scores=(pre_scores[:] if pre_scores is not None else None),
            )
            card = seat_policy[current].choose_card(current, state, play_history[:])
            led = trick[0][1] if trick else None
            legal = get_playable_cards(hands[current], trump, led)
            if card not in legal:
                card = legal[0]
            hands[current].remove(card)
            trick.append((current, card))
            play_history.append((current, card))
            cards_played_all.append(card)
            tr = get_trump_rank(card, trump)
            if tr > high_trump_rank:
                high_trump_rank = tr
                high_trump_player = current
            current = (current + 1) % 4

        all_ids = {cid(c) for c in cards_played_all}
        _update_known_voids(trick, trick_leader, trump, all_ids,
                            known_voids, known_oot)
        winner = evaluate_trick(trick, trump, trick_leader)
        tricks_won[winner % 2] += 1
        player_tricks[winner] += 1
        if winner % 2 != bidder % 2:
            bidder_lost = True
        trick_leader = winner

    # Round scoring
    pts = [tricks_won[0] * 5, tricks_won[1] * 5]
    if high_trump_player >= 0:
        pts[high_trump_player % 2] += 5  # +5 for the highest-trump trick

    bteam = bidder % 2
    dteam = 1 - bteam
    out = [0, 0]
    if pts[bteam] >= bid:
        out[bteam] = pts[bteam]
    else:
        out[bteam] = -bid          # set
    out[dteam] = pts[dteam]

    if return_per_player:
        # Raw per-seat round pts: 5*tricks + 5 high-trump bonus to that seat.
        # Bidder-make/set is per-mode — cutthroat caller applies it (banks
        # -bid if bidder's OWN pts < bid; defenders always bank their pts).
        per_player = [player_tricks[p] * 5 for p in range(4)]
        if high_trump_player >= 0:
            per_player[high_trump_player] += 5
        return out[0], out[1], per_player
    return out[0], out[1]


def play_game(seat_policy: List[Policy], seed: int,
              start_dealer: int = 0) -> Dict:
    """
    Play a full deterministic game. seat_policy[seat] drives that seat
    (seats 0,2 share one team policy; 1,3 the other).

    `seed` fully determines every round's deal — so a paired run with the
    SAME seed + start_dealer but swapped team policies isolates the policy
    difference (deal luck cancels). This is the variance control the
    evaluator relies on; do NOT reshuffle from a global RNG here.

    Returns dict: winner_team, scores, rounds, bids_made, bids_set.
    """
    rng = random.Random(seed)
    scores = [0, 0]
    dealer = start_dealer
    rounds = 0
    made = 0
    set_ = 0
    # faced_losing[t] = True if, at some round START, team t's opponent was
    # already >= LOSING_THRESHOLD (one makeable 15 from winning the game).
    faced_losing = [False, False]
    # closest_opp_need[t] = the SMALLEST (120 - opponent_score) team t ever
    # faced at a round start = how close the opponent ever got to winning.
    # Stratifies comeback equity by opponent distance (≤15 / 16-20 / 21-25 /
    # 26-30 / never-in-danger) so the desperation T ceiling is testable.
    closest_opp_need = [120, 120]

    while max(scores) < 120 and rounds < MAX_ROUNDS:
        rounds += 1
        if scores[1] >= LOSING_THRESHOLD:
            faced_losing[0] = True
        if scores[0] >= LOSING_THRESHOLD:
            faced_losing[1] = True
        closest_opp_need[0] = min(closest_opp_need[0], 120 - scores[1])
        closest_opp_need[1] = min(closest_opp_need[1], 120 - scores[0])
        d = Deck()
        rng.shuffle(d.cards)      # per-round deal, deterministic from seed
        hands = [d.deal(5) for _ in range(4)]
        kitty = d.deal(3)
        rest = d.cards[:]

        # ── Bid phase ────────────────────────────────────────────────────────
        bids: List[int] = [None, None, None, None]
        suits: List = [None, None, None, None]
        high_bid = 0
        order = [(dealer + 1) % 4, (dealer + 2) % 4, (dealer + 3) % 4, dealer]
        for p in order:
            my_team = p % 2
            ts = scores[my_team]
            os_ = scores[1 - my_team]
            pidx = (p + 2) % 4
            pb = bids[pidx] if bids[pidx] not in (None, -1) else 0
            b, s = seat_policy[p].decide_bid(hands[p], high_bid, p, dealer,
                                             ts, os_, pb)
            bids[p] = b
            suits[p] = s
            if b > high_bid:
                high_bid = b

        # Resolve winner: first max scanning seats 0..3 (matches JS)
        max_b = 0
        winner = dealer
        for i in range(4):
            if (bids[i] or 0) > max_b:
                max_b = bids[i]
                winner = i
        if max_b == 0:               # safety: should never happen (dealer bagged 15)
            winner = dealer
            max_b = 15
            suits[winner] = find_best_trump_suit(hands[winner])['suit']

        trump = suits[winner] or find_best_trump_suit(hands[winner])['suit']

        t0, t1 = _play_round(winner, max_b, trump, hands, kitty, rest, seat_policy,
                             pre_scores=scores[:])
        scores[0] += t0
        scores[1] += t1
        if winner % 2 == 0:
            made += 1 if t0 > 0 and t0 >= max_b else 0
            set_ += 1 if t0 < 0 else 0
        else:
            made += 1 if t1 > 0 and t1 >= max_b else 0
            set_ += 1 if t1 < 0 else 0

        if max(scores) >= 120:
            break
        dealer = (dealer + 1) % 4

    if scores[0] >= 120 and scores[1] >= 120:
        winner_team = winner % 2          # both → bidding team wins
    elif scores[0] >= 120:
        winner_team = 0
    elif scores[1] >= 120:
        winner_team = 1
    else:
        winner_team = 0 if scores[0] >= scores[1] else 1  # cap hit (rare)

    return {
        'winner_team': winner_team,
        'scores': scores,
        'rounds': rounds,
        'bids_made': made,
        'bids_set': set_,
        'faced_losing': faced_losing,            # [team0, team1]
        'closest_opp_need': closest_opp_need,    # [team0, team1]
    }
