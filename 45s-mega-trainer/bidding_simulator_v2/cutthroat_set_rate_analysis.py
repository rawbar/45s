"""
cutthroat_set_rate_analysis.py — measure bid set-rate per seat in CUTTHROAT.

Mirrors set_rate_analysis.py but for the 4-player FFA variant. The headline
question for cutthroat coalition rules: when the challenger sits in a
NON-bidder seat (= acts as a defender against the 3 champions, one of whom
is bidding), do the CHAMPIONS get set MORE often than baseline? If yes →
the coalition defense is working — the challenger's defender play is
pressuring bidders into more failed contracts.

Per-seat tally:
  - bids attempted (rounds where seat won the auction)
  - bids made (banked own pts)
  - bids set (-bid penalty)
  - set-rate %

Run modes (1 challenger vs 3 champion-cutthroat, rotated through 4 seats):
  python -m bidding_simulator_v2.cutthroat_set_rate_analysis \\
      --challenger cutthroat-coalition-v1 --deals 2000

Output: aggregate stats for the CHALLENGER seat across all rotations vs
aggregate stats for the CHAMPION seats (when one of them is bidding while
the challenger defends). Δset-rate of CHAMPIONS is the primary signal —
a higher champion set-rate means the challenger's defender play is
breaking more bids.
"""

import sys, os, io, argparse, time, math, random
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace')

import multiprocessing as mp
from multiprocessing import Pool

from typing import List, Dict
from game_engine import Deck
from bidding_simulator_v2.bidding import find_best_trump_suit
from bidding_simulator_v2.game_runner import _play_round, MAX_ROUNDS
from bidding_simulator_v2.policy import Policy
from bidding_simulator_v2.challengers import REGISTRY, CHAMPION_CUTTHROAT


def play_game_cutthroat_with_per_seat_stats(seat_policy: List[Policy],
                                             seed: int,
                                             start_dealer: int = 0) -> Dict:
    """Same flow as `cutthroat_runner.play_game_cutthroat` but ALSO returns
    per-seat bid counts: bids[s], made[s], set_[s] (= 4-vectors)."""
    rng = random.Random(seed)
    scores = [0, 0, 0, 0]
    dealer = start_dealer
    rounds = 0
    bids_count = [0, 0, 0, 0]
    made = [0, 0, 0, 0]
    set_ = [0, 0, 0, 0]
    last_bidder = -1

    while max(scores) < 120 and rounds < MAX_ROUNDS:
        rounds += 1
        d = Deck()
        rng.shuffle(d.cards)
        hands = [d.deal(5) for _ in range(4)]
        kitty = d.deal(3)
        rest = d.cards[:]

        bids: List = [None, None, None, None]
        suits: List = [None, None, None, None]
        high_bid = 0
        order = [(dealer + 1) % 4, (dealer + 2) % 4, (dealer + 3) % 4, dealer]
        for p in order:
            ts = scores[p]
            os_ = max(scores[(p + 1) % 4], scores[(p + 2) % 4],
                      scores[(p + 3) % 4])
            b, s = seat_policy[p].decide_bid(hands[p], high_bid, p, dealer,
                                             ts, os_, 0)
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
        last_bidder = winner
        bids_count[winner] += 1

        _t0, _t1, per_player = _play_round(
            winner, max_b, trump, hands, kitty, rest, seat_policy,
            pre_scores=scores[:], return_per_player=True
        )

        bidder_pts = per_player[winner]
        bidder_made = bidder_pts >= max_b

        round_delta = [0, 0, 0, 0]
        for p in range(4):
            if p == winner:
                if bidder_made:
                    round_delta[p] = bidder_pts
                else:
                    round_delta[p] = -2 * max_b if max_b == 30 else -max_b
            else:
                round_delta[p] = per_player[p]
        for p in range(4):
            scores[p] += round_delta[p]

        if bidder_made:
            made[winner] += 1
        else:
            set_[winner] += 1

        if max(scores) >= 120:
            break
        dealer = (dealer + 1) % 4

    at_120 = [i for i in range(4) if scores[i] >= 120]
    if len(at_120) == 1:
        winner_seat = at_120[0]
    elif len(at_120) >= 2:
        if last_bidder in at_120:
            winner_seat = last_bidder
        else:
            winner_seat = max(at_120, key=lambda s: (scores[s], -s))
    else:
        winner_seat = max(range(4), key=lambda s: (scores[s], -s))

    return {
        'winner': winner_seat,
        'final_scores': scores,
        'rounds': rounds,
        'bids': bids_count,
        'made': made,
        'set': set_,
    }


_CHALLENGER_NAME = None
_SEED_BASE = 0


def _init(name, seed_base=0):
    global _CHALLENGER_NAME, _SEED_BASE
    _CHALLENGER_NAME = name
    _SEED_BASE = seed_base


def _run_chunk(args):
    """args = (start_idx, count). Returns aggregated counters across all
    seat-rotation passes:
        (games, ch_bids, ch_made, ch_set, chmp_bids, chmp_made, chmp_set,
         ch_wins, chmp_wins)
    where 'ch' = challenger seat tally and 'chmp' = the OTHER three (champion)
    seats summed (per-game = 3 champion seats × 1 row each)."""
    start, count = args
    chal = REGISTRY[_CHALLENGER_NAME]
    champ = CHAMPION_CUTTHROAT
    games = 0
    ch_bids = ch_made = ch_set = 0
    chmp_bids = chmp_made = chmp_set = 0
    ch_wins = chmp_wins = 0
    for i in range(start, start + count):
        seed = _SEED_BASE + i
        dealer = i % 4
        for chal_seat in range(4):
            policies = [champ, champ, champ, champ]
            policies[chal_seat] = chal
            res = play_game_cutthroat_with_per_seat_stats(policies, seed, dealer)
            for s in range(4):
                if s == chal_seat:
                    ch_bids += res['bids'][s]
                    ch_made += res['made'][s]
                    ch_set  += res['set'][s]
                else:
                    chmp_bids += res['bids'][s]
                    chmp_made += res['made'][s]
                    chmp_set  += res['set'][s]
            if res['winner'] == chal_seat:
                ch_wins += 1
            else:
                chmp_wins += 1
            games += 1
    return (games, ch_bids, ch_made, ch_set,
            chmp_bids, chmp_made, chmp_set, ch_wins, chmp_wins)


def main():
    ap = argparse.ArgumentParser(
        description='45s cutthroat (FFA) per-seat bid set-rate analysis'
    )
    ap.add_argument('--challenger', required=True, choices=sorted(REGISTRY),
                    help='policy to test vs 3x champion-cutthroat')
    ap.add_argument('--deals', type=int, default=2000,
                    help='deals (games = 4 × deals; seat-rotated passes)')
    ap.add_argument('--workers', type=int, default=mp.cpu_count())
    ap.add_argument('--seed-base', type=int, default=0,
                    help='seed offset for hold-out re-validation')
    args = ap.parse_args()

    chunk = 250
    tasks = []
    rem = args.deals
    idx = 0
    while rem > 0:
        n = min(chunk, rem)
        tasks.append((idx, n))
        idx += n
        rem -= n

    W = 80
    print('\n' + '=' * W)
    print(f'  SET-RATE (CUTTHROAT): challenger {args.challenger}  '
          f'vs 3x champion-cutthroat')
    print(f'  deals: {args.deals:,}  (passes: 4*deals = {4*args.deals:,} games)'
          f'  workers: {args.workers}')
    print('=' * W)
    t0 = time.time()

    games = 0
    ch_bids = ch_made = ch_set = 0
    chmp_bids = chmp_made = chmp_set = 0
    ch_wins = chmp_wins = 0
    with Pool(args.workers, initializer=_init,
              initargs=(args.challenger, args.seed_base)) as pool:
        for (g, cb, cm, cs, mb, mm, ms, cw, mw) in pool.imap_unordered(
                _run_chunk, tasks):
            games += g
            ch_bids += cb;  ch_made += cm;  ch_set += cs
            chmp_bids += mb; chmp_made += mm; chmp_set += ms
            ch_wins += cw;  chmp_wins += mw
            done = games / (4 * args.deals)
            ch_rate = ch_set / max(ch_bids, 1) * 100
            mp_rate = chmp_set / max(chmp_bids, 1) * 100
            print(f'\r  {done*100:5.1f}%  {games:,} games  '
                  f'ch:set={ch_rate:5.2f}%  chmp:set={mp_rate:5.2f}%',
                  end='', flush=True)

    el = time.time() - t0
    ch_rate = ch_set / max(ch_bids, 1) * 100
    mp_rate = chmp_set / max(chmp_bids, 1) * 100
    delta = ch_rate - mp_rate

    print('\n\n' + '-' * W)
    print(f"{'':>26}  {'bids':>8} {'made':>8} {'set':>8}  {'set-rate':>9}")
    print(f"  {'challenger seat':>24}  "
          f"{ch_bids:>8,} {ch_made:>8,} {ch_set:>8,}  {ch_rate:>8.2f}%")
    print(f"  {'champion seats (3x)':>24}  "
          f"{chmp_bids:>8,} {chmp_made:>8,} {chmp_set:>8,}  {mp_rate:>8.2f}%")
    print()
    print(f"  Δ set-rate (chal − chmp): {delta:+.2f}pt")
    print(f"     (negative = challenger sets LESS as bidder; positive = "
          f"champions set MORE as bidder against challenger defense)")
    print()
    # Win-rate banner
    tg = ch_wins + chmp_wins
    cwr = ch_wins / max(tg, 1) * 100
    print(f"  win rate: challenger {cwr:5.2f}%  vs 25% baseline  "
          f"({ch_wins:,} / {tg:,})")
    print()
    print(f'  elapsed {el:.0f}s  ({games/max(el,1):,.0f} games/s)')
    print('-' * W)
    print()


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)
    main()
