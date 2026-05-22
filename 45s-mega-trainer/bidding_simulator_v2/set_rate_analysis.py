"""
set_rate_analysis.py — measure bid set-rate per policy.

The head-to-head evaluator answers "which policy wins more games?"
This script answers a DIFFERENT question: "how often does a team using
each policy get SET when it bids?" — useful to check whether a more
aggressive bid rule (upbid15, open_5_at_20) makes the AI look
'stupid more often' in absolute terms, even if it wins on net.

Per-team stats are reconstructed by patching play_game inline to
record (bidder_seat, made_or_set) per round. Seats 0,2 share team A's
policy; seats 1,3 share team B's. We run paired-mirrored deals
(seat policies swapped on a second pass) to cancel deal luck.

Run:  python -m bidding_simulator_v2.set_rate_analysis --policy bid:no-upbid15
      python -m bidding_simulator_v2.set_rate_analysis --policy bid:no-open5_20
      python -m bidding_simulator_v2.set_rate_analysis --policy egd:on --deals 5000
"""
import sys, os, argparse, random
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import List, Dict
from game_engine import Deck, Suit
from bidding_simulator_v2.bidding import find_best_trump_suit
from bidding_simulator_v2.game_runner import _play_round, LOSING_THRESHOLD, MAX_ROUNDS
from bidding_simulator_v2.policy import Policy, CHAMPION
from bidding_simulator_v2.challengers import REGISTRY


def play_game_with_per_team_bid_stats(seat_policy, seed, start_dealer=0):
    """Same flow as play_game, but also returns per-team bid counts."""
    rng = random.Random(seed)
    scores = [0, 0]
    dealer = start_dealer
    rounds = 0
    bids = [0, 0]       # bids attempted by team 0 / team 1
    made = [0, 0]
    set_ = [0, 0]
    while max(scores) < 120 and rounds < MAX_ROUNDS:
        rounds += 1
        d = Deck()
        rng.shuffle(d.cards)
        hands = [d.deal(5) for _ in range(4)]
        kitty = d.deal(3)
        rest = d.cards[:]
        bids_round = [None, None, None, None]
        suits = [None, None, None, None]
        high_bid = 0
        order = [(dealer + 1) % 4, (dealer + 2) % 4, (dealer + 3) % 4, dealer]
        for p in order:
            my_team = p % 2
            ts = scores[my_team]
            os_ = scores[1 - my_team]
            pidx = (p + 2) % 4
            pb = bids_round[pidx] if bids_round[pidx] not in (None, -1) else 0
            b, s = seat_policy[p].decide_bid(hands[p], high_bid, p, dealer,
                                             ts, os_, pb)
            bids_round[p] = b
            suits[p] = s
            if b > high_bid:
                high_bid = b
        max_b = 0
        winner = dealer
        for i in range(4):
            if (bids_round[i] or 0) > max_b:
                max_b = bids_round[i]
                winner = i
        if max_b == 0:
            winner = dealer
            max_b = 15
            suits[winner] = find_best_trump_suit(hands[winner])['suit']
        trump = suits[winner] or find_best_trump_suit(hands[winner])['suit']
        bidder_team = winner % 2
        bids[bidder_team] += 1
        t0, t1 = _play_round(winner, max_b, trump, hands, kitty, rest,
                              seat_policy, pre_scores=scores[:])
        scores[0] += t0
        scores[1] += t1
        if bidder_team == 0:
            if t0 < 0:
                set_[0] += 1
            else:
                made[0] += 1
        else:
            if t1 < 0:
                set_[1] += 1
            else:
                made[1] += 1
        if max(scores) >= 120:
            break
        dealer = (dealer + 1) % 4
    winner_team = 0 if scores[0] >= scores[1] else 1
    return {'winner_team': winner_team, 'bids': bids, 'made': made, 'set': set_}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--policy', required=True,
                    help='challenger policy name (compares vs champion)')
    ap.add_argument('--deals', type=int, default=10000,
                    help='paired deal count (2x = games)')
    args = ap.parse_args()

    if args.policy not in REGISTRY:
        print(f"Policy '{args.policy}' not in REGISTRY")
        sys.exit(1)

    challenger = REGISTRY[args.policy]
    champion = CHAMPION

    # Paired mirrored runs: on pass A challenger is team 0; on pass B team 1.
    ch_bids = ch_made = ch_set = 0
    chmp_bids = chmp_made = chmp_set = 0
    ch_wins = chmp_wins = 0
    for i in range(args.deals):
        # Pass A: challenger seats 0,2; champion seats 1,3
        sp_a = [challenger, champion, challenger, champion]
        r = play_game_with_per_team_bid_stats(sp_a, seed=i, start_dealer=i % 4)
        ch_bids  += r['bids'][0];  ch_made  += r['made'][0];  ch_set  += r['set'][0]
        chmp_bids += r['bids'][1]; chmp_made += r['made'][1]; chmp_set += r['set'][1]
        if r['winner_team'] == 0: ch_wins += 1
        else: chmp_wins += 1
        # Pass B: champion seats 0,2; challenger seats 1,3
        sp_b = [champion, challenger, champion, challenger]
        r = play_game_with_per_team_bid_stats(sp_b, seed=i, start_dealer=i % 4)
        chmp_bids += r['bids'][0]; chmp_made += r['made'][0]; chmp_set += r['set'][0]
        ch_bids  += r['bids'][1];  ch_made  += r['made'][1];  ch_set  += r['set'][1]
        if r['winner_team'] == 1: ch_wins += 1
        else: chmp_wins += 1

    games = 2 * args.deals
    print()
    print('=' * 64)
    print(f"  SET-RATE: {args.policy} vs champion · {args.deals:,} paired ({games:,} games)")
    print('=' * 64)
    print(f"\n{'':>14}  {'bids':>8} {'made':>8} {'set':>8}  {'set-rate':>9}")
    ch_rate = ch_set / max(ch_bids, 1) * 100
    chmp_rate = chmp_set / max(chmp_bids, 1) * 100
    print(f"  {args.policy:>12}  {ch_bids:>8,} {ch_made:>8,} {ch_set:>8,}  {ch_rate:>8.2f}%")
    print(f"  {'champion':>12}  {chmp_bids:>8,} {chmp_made:>8,} {chmp_set:>8,}  {chmp_rate:>8.2f}%")
    print()
    print(f"  bid-volume diff: {ch_bids - chmp_bids:+,}  ({(ch_bids-chmp_bids)/max(chmp_bids,1)*100:+.1f}%)")
    print(f"  set-rate diff:   {ch_rate - chmp_rate:+.2f}pt")
    print(f"  win rate:        {args.policy} {ch_wins/games*100:.2f}%  vs champion {chmp_wins/games*100:.2f}%")
    print()


if __name__ == '__main__':
    main()
