"""
bag_has5_analysis.py — ad-hoc analysis: when the dealer gets bagged (all 3
other seats pass, forcing a blind 15-bid), what fraction of the time is the
dealer actually holding the 5 of the suit they end up naming as trump?

Mirrors game_runner.play_game / cutthroat_runner.play_game_cutthroat's bid
phase exactly (same dealing, same order, same CHAMPION policy) so the score
trajectories (and therefore bag frequency) are realistic, not zero-context.
Only instrumentation added: detect "about to bag" (high_bid==0 right before
the dealer's own decide_bid call) and record find_best_trump_suit(hand)['has5']
for that dealer's pre-kitty hand.

Not committed as permanent tooling -- one-off per user request 2026-11-02.
"""
import sys, os, random, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from game_engine import Deck
from bidding_simulator_v2.bidding import find_best_trump_suit
from bidding_simulator_v2.game_runner import _play_round, MAX_ROUNDS
from bidding_simulator_v2.policy import CHAMPION
from bidding_simulator_v2.challengers import CHAMPION_CUTTHROAT


def run_partner(n_games: int, seed0: int = 0):
    policy = [CHAMPION] * 4
    bagged = 0
    bagged_has5 = 0
    bagged_hasJ_no5 = 0
    rounds_total = 0

    for g in range(n_games):
        rng = random.Random(seed0 + g)
        scores = [0, 0]
        dealer = 0
        rounds = 0
        while max(scores) < 120 and rounds < MAX_ROUNDS:
            rounds += 1
            rounds_total += 1
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
                    # About to bag -- record hand quality BEFORE the forced bid.
                    info = find_best_trump_suit(hands[p])
                    bagged += 1
                    if info['has5']:
                        bagged_has5 += 1
                    elif info['hasJ']:
                        bagged_hasJ_no5 += 1
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
            t0, t1 = _play_round(winner, max_b, trump, hands, kitty, rest, policy,
                                  pre_scores=scores[:])
            scores[0] += t0
            scores[1] += t1
            if max(scores) >= 120:
                break
            dealer = (dealer + 1) % 4

    return dict(rounds=rounds_total, bagged=bagged, bagged_has5=bagged_has5,
                bagged_hasJ_no5=bagged_hasJ_no5)


def run_cutthroat(n_games: int, seed0: int = 0):
    policy = [CHAMPION_CUTTHROAT] * 4
    bagged = 0
    bagged_has5 = 0
    bagged_hasJ_no5 = 0
    rounds_total = 0

    for g in range(n_games):
        rng = random.Random(seed0 + g)
        scores = [0, 0, 0, 0]
        dealer = 0
        rounds = 0
        while max(scores) < 120 and rounds < MAX_ROUNDS:
            rounds += 1
            rounds_total += 1
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
                    elif info['hasJ']:
                        bagged_hasJ_no5 += 1
                ts = scores[p]
                os_ = max(scores[(p + 1) % 4], scores[(p + 2) % 4], scores[(p + 3) % 4])
                b, s = policy[p].decide_bid(hands[p], high_bid, p, dealer, ts, os_, 0,
                                             dealer_score=scores[dealer])
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
            _t0, _t1, per_player = _play_round(
                winner, max_b, trump, hands, kitty, rest, policy,
                pre_scores=scores[:], return_per_player=True,
                pre_round_scores=scores[:],
            )
            bidder_pts = per_player[winner]
            bidder_made = bidder_pts >= max_b
            round_delta = [0, 0, 0, 0]
            for p in range(4):
                if p == winner:
                    round_delta[p] = bidder_pts if bidder_made else (-2 * max_b if max_b == 30 else -max_b)
                else:
                    round_delta[p] = per_player[p]
            for p in range(4):
                scores[p] += round_delta[p]
            if max(scores) >= 120:
                break
            dealer = (dealer + 1) % 4

    return dict(rounds=rounds_total, bagged=bagged, bagged_has5=bagged_has5,
                bagged_hasJ_no5=bagged_hasJ_no5)


def report(label, r):
    b = r['bagged']
    pct5 = 100.0 * r['bagged_has5'] / b if b else 0.0
    pctJnoJ = 100.0 * r['bagged_hasJ_no5'] / b if b else 0.0
    pctneither = 100.0 - pct5 - pctJnoJ
    print(f"\n=== {label} ===")
    print(f"rounds simulated: {r['rounds']}")
    print(f"dealer-bagged events: {b}  ({100.0*b/r['rounds']:.1f}% of rounds)")
    print(f"  bagged dealer HAD the 5 (of their best suit): {r['bagged_has5']} ({pct5:.1f}%)")
    print(f"  bagged dealer had J but NOT 5: {r['bagged_hasJ_no5']} ({pctJnoJ:.1f}%)")
    print(f"  bagged dealer had neither 5 nor J: {b - r['bagged_has5'] - r['bagged_hasJ_no5']} ({pctneither:.1f}%)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=3000)
    args = ap.parse_args()

    r_partner = run_partner(args.games, seed0=0)
    report("PARTNER MODE", r_partner)

    r_ct = run_cutthroat(args.games, seed0=1_000_000)
    report("CUTTHROAT MODE", r_ct)
