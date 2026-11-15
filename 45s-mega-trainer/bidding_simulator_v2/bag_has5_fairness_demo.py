"""
bag_has5_fairness_demo.py — rigorous breakdown of WHY a bagged dealer holds
the 5-of-trump ~37% of the time under fair dealing, to answer player
complaints that "the dealing logic is rigged toward the bagged player."

Three numbers, same shuffle algorithm as the real game (verified: app.src.html
shuffleDeck() is a textbook Fisher-Yates, confirmed unbiased):

  A) FLAT baseline: P(a specific card is in a specific 5-card hand from a
     52-card deck) = 5/52. The wrong intuition players are using.

  B) BEST-SUIT SELECTION baseline: deal purely random hands (no bidding at
     all), and for EVERY hand ask "does MY best suit's 5 happen to be in my
     own hand?" This isolates the real reason B > A: find_best_trump_suit
     picks whichever suit you're already strongest in -- which correlates
     with also holding that suit's 5. Nothing to do with bidding or bagging.

  C) FULL BAGGED-DEALER rate (what was reported to the user): same as B,
     but additionally conditioned on "all 3 other seats passed" (the actual
     bagging trigger). Isolates how much MORE the bagging condition itself
     adds on top of B.

  D) Per-suit breakdown + per-seat breakdown of raw 5-of-trump holding
     across ALL dealt hands (not conditioned on anything) -- a direct
     fairness check: each of the 4 suit-5s should land in each of the 4
     seats at ~5/52 regardless of suit or seat position. Any seat/suit
     skew here would be real evidence of a shuffle bug; none is expected.
"""
import sys, os, random, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from game_engine import Deck
from bidding_simulator_v2.bidding import find_best_trump_suit
from bidding_simulator_v2.policy import CHAMPION
from bidding_simulator_v2.challengers import CHAMPION_CUTTHROAT
from bidding_simulator_v2.game_runner import _play_round, MAX_ROUNDS


def flat_baseline():
    return 5.0 / 52.0


def best_suit_baseline(n_hands: int, seed0: int = 0):
    """Deal N random 5-card hands (fully independent, no game context at
    all). For each, does the hand's own best suit also contain that suit's
    5? No bidding, no bagging -- isolates the best-suit selection effect
    alone."""
    rng = random.Random(seed0)
    has5 = 0
    for i in range(n_hands):
        d = Deck()
        rng.shuffle(d.cards)
        hand = d.deal(5)
        info = find_best_trump_suit(hand)
        if info['has5']:
            has5 += 1
    return has5 / n_hands


def seat_suit_fairness(n_hands_per_seat: int, seed0: int = 0):
    """Direct shuffle-fairness check: deal many full 4-hand rounds, and for
    each of the 4 seats x 4 suits, count how often that seat holds that
    suit's 5. Every cell should land near 5/52 = 9.615% with no systematic
    skew by seat or by suit -- a real shuffle bug would show up here as a
    skewed row/column, not as "bagged dealers have too many 5s" (which is
    fully explained by B/C above, not a dealing defect)."""
    rng = random.Random(seed0)
    suits = ['♠', '♥', '♦', '♣']
    counts = {s: [0, 0, 0, 0] for s in suits}  # counts[suit][seat]
    rounds = 0
    while rounds * 4 < n_hands_per_seat * 4:
        rounds += 1
        d = Deck()
        rng.shuffle(d.cards)
        hands = [d.deal(5) for _ in range(4)]
        for seat in range(4):
            fives_in_hand = {c.suit.value for c in hands[seat] if c.rank == '5'}
            for s in suits:
                if s in fives_in_hand:
                    counts[s][seat] += 1
    return counts, rounds


def bagged_dealer_rate(n_games: int, cutthroat: bool, seed0: int):
    """Reuses the exact bid-phase logic from the prior analysis (champion
    policy, realistic score trajectories) -- this is the already-reported
    'C' number, re-derived here for a single coherent script/output."""
    policy = [CHAMPION_CUTTHROAT if cutthroat else CHAMPION] * 4
    bagged = 0
    bagged_has5 = 0
    for g in range(n_games):
        rng = random.Random(seed0 + g)
        scores = [0, 0, 0, 0] if cutthroat else [0, 0]
        dealer = 0
        rounds = 0
        while max(scores) < 120 and rounds < MAX_ROUNDS:
            rounds += 1
            d = Deck()
            rng.shuffle(d.cards)
            hands = [d.deal(5) for _ in range(4)]
            kitty = d.deal(3)
            rest = d.cards[:]
            bids = [None, None, None, None]
            suits = [None, None, None, None]
            high_bid = 0
            order = [(dealer + 1) % 4, (dealer + 2) % 4, (dealer + 3) % 4, dealer]
            for p in order:
                if p == dealer and high_bid == 0:
                    info = find_best_trump_suit(hands[p])
                    bagged += 1
                    if info['has5']:
                        bagged_has5 += 1
                if cutthroat:
                    ts = scores[p]
                    os_ = max(scores[(p + 1) % 4], scores[(p + 2) % 4], scores[(p + 3) % 4])
                    b, s = policy[p].decide_bid(hands[p], high_bid, p, dealer, ts, os_, 0,
                                                 dealer_score=scores[dealer])
                else:
                    my_team = p % 2
                    ts = scores[my_team]
                    os_ = scores[1 - my_team]
                    pidx = (p + 2) % 4
                    pb = bids[pidx] if bids[pidx] not in (None, -1) else 0
                    b, s = policy[p].decide_bid(hands[p], high_bid, p, dealer, ts, os_, pb)
                bids[p] = b
                suits[p] = s
                if b > high_bid:
                    high_bid = b
            max_b = 0
            winner = dealer
            for i in range(4):
                if (bids[i] or 0) > max_b:
                    max_b = bids[i]
                    winner = i
            if max_b == 0:
                winner = dealer
                max_b = 15
                suits[winner] = find_best_trump_suit(hands[winner])['suit']
            trump = suits[winner] or find_best_trump_suit(hands[winner])['suit']
            if cutthroat:
                _t0, _t1, per_player = _play_round(
                    winner, max_b, trump, hands, kitty, rest, policy,
                    pre_scores=scores[:], return_per_player=True, pre_round_scores=scores[:])
                bidder_made = per_player[winner] >= max_b
                for p in range(4):
                    if p == winner:
                        scores[p] += per_player[p] if bidder_made else (-2 * max_b if max_b == 30 else -max_b)
                    else:
                        scores[p] += per_player[p]
            else:
                t0, t1 = _play_round(winner, max_b, trump, hands, kitty, rest, policy, pre_scores=scores[:])
                scores[0] += t0
                scores[1] += t1
            if max(scores) >= 120:
                break
            dealer = (dealer + 1) % 4
    return bagged, bagged_has5


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--best-suit-n", type=int, default=200_000)
    ap.add_argument("--fairness-n", type=int, default=50_000)
    ap.add_argument("--games", type=int, default=5000)
    args = ap.parse_args()

    A = flat_baseline()
    print(f"A) Flat baseline (specific card in a specific 5-card hand): {A*100:.2f}%  [= 5/52]")

    B = best_suit_baseline(args.best_suit_n)
    print(f"B) Best-suit-selection baseline (n={args.best_suit_n}, no bidding/bagging at all): {B*100:.2f}%")

    print(f"\nFairness grid (n={args.fairness_n} deals, counts of each suit's 5 landing in each seat):")
    counts, rounds = seat_suit_fairness(args.fairness_n)
    suit_names = {'♠': 'S', '♥': 'H', '♦': 'D', '♣': 'C'}
    print(f"{'suit':6}" + "".join(f"seat{i}".rjust(10) for i in range(4)))
    for s, c in counts.items():
        pct = [f"{100*v/rounds:.2f}%".rjust(10) for v in c]
        print(f"{suit_names[s]:6}" + "".join(pct))
    print(f"(expect ~9.62% in every cell, n={rounds} deals per cell)")

    for cutthroat, label in [(False, "PARTNER"), (True, "CUTTHROAT")]:
        bagged, bagged_has5 = bagged_dealer_rate(args.games, cutthroat, seed0=(0 if not cutthroat else 1_000_000))
        C = bagged_has5 / bagged if bagged else 0.0
        print(f"\nC) {label} bagged-dealer rate (n={bagged} bag events): {C*100:.2f}%")
        print(f"   delta vs flat baseline A: +{(C-A)*100:.2f}pp")
        print(f"   delta vs best-suit baseline B: +{(C-B)*100:.2f}pp  <- this is what bagging ITSELF adds")
