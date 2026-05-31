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
    per-seat bid counts: bids[s], made[s], set_[s] (= 4-vectors), plus
    by-level dicts keyed by bid amount (15/20/25/30) → {bids, made, set,
    made_pts} for finer headline breakdowns."""
    rng = random.Random(seed)
    scores = [0, 0, 0, 0]
    dealer = start_dealer
    rounds = 0
    bids_count = [0, 0, 0, 0]
    made = [0, 0, 0, 0]
    set_ = [0, 0, 0, 0]
    # by bid amount: bids / made / set / sum of made-pts (for avg)
    by_level = {b: {'bids': 0, 'made': 0, 'set': 0, 'made_pts': 0}
                for b in (15, 20, 25, 30)}
    last_bidder = -1
    # NICKEL-GRAB metric: sum of raw banked pts across all DEFENDERS
    # across all rounds. Defender raw pts = per_player[p] for p != winner
    # (defenders always bank own trick pts). defender_round_count is
    # increments-of-3 per round (3 defenders per cutthroat round) so
    # the per-defender-per-round average is defender_pts / defender_round_count.
    defender_pts = 0
    defender_round_count = 0

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
                                             ts, os_, 0,
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
        last_bidder = winner
        bids_count[winner] += 1
        lvl_key = max_b if max_b in by_level else None
        if lvl_key is not None:
            by_level[lvl_key]['bids'] += 1

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
                    round_delta[p] = -2 * max_b if max_b == 30 else -max_b
            else:
                round_delta[p] = per_player[p]
        for p in range(4):
            scores[p] += round_delta[p]

        if bidder_made:
            made[winner] += 1
            if lvl_key is not None:
                by_level[lvl_key]['made'] += 1
                by_level[lvl_key]['made_pts'] += bidder_pts
        else:
            set_[winner] += 1
            if lvl_key is not None:
                by_level[lvl_key]['set'] += 1

        # Sum raw defender pts (3 defenders' per_player) for nickel-grab.
        for p in range(4):
            if p != winner:
                defender_pts += per_player[p]
                defender_round_count += 1

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
        'by_level': by_level,
        'defender_pts': defender_pts,
        'defender_round_count': defender_round_count,
    }


_CHALLENGER_NAME = None
_SEED_BASE = 0
_CONFIG_A_NAME = None
_CONFIG_B_NAME = None


def _init(name, seed_base=0):
    global _CHALLENGER_NAME, _SEED_BASE
    _CHALLENGER_NAME = name
    _SEED_BASE = seed_base


def _init_symmetric(a_name, b_name, seed_base=0):
    global _CONFIG_A_NAME, _CONFIG_B_NAME, _SEED_BASE
    _CONFIG_A_NAME = a_name
    _CONFIG_B_NAME = b_name
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


def _run_chunk_symmetric(args):
    """args = (start_idx, count). Two whole-table configurations played on
    the SAME deal seeds. Per chunk, returns aggregated tuples for A and B:
        ((a_games, a_bids, a_made, a_set, a_made_pts, a_by_level),
         (b_games, b_bids, b_made, b_set, b_made_pts, b_by_level))
    where bids/made/set are totals across all 4 seats (= all bidder seats)
    and by_level is a dict[int] → {bids, made, set, made_pts}."""
    start, count = args
    pa = REGISTRY[_CONFIG_A_NAME]
    pb = REGISTRY[_CONFIG_B_NAME]
    a_games = b_games = 0
    a_bids = a_made = a_set = a_made_pts = 0
    b_bids = b_made = b_set = b_made_pts = 0
    a_def_pts = b_def_pts = 0
    a_def_n = b_def_n = 0
    a_by = {lvl: {'bids': 0, 'made': 0, 'set': 0, 'made_pts': 0}
            for lvl in (15, 20, 25, 30)}
    b_by = {lvl: {'bids': 0, 'made': 0, 'set': 0, 'made_pts': 0}
            for lvl in (15, 20, 25, 30)}
    for i in range(start, start + count):
        seed = _SEED_BASE + i
        dealer = i % 4
        # Config A: all 4 seats run policy A
        res_a = play_game_cutthroat_with_per_seat_stats(
            [pa, pa, pa, pa], seed, dealer)
        # Config B: SAME seed/dealer, all 4 seats run policy B
        res_b = play_game_cutthroat_with_per_seat_stats(
            [pb, pb, pb, pb], seed, dealer)
        a_games += 1
        b_games += 1
        for s in range(4):
            a_bids += res_a['bids'][s]
            a_made += res_a['made'][s]
            a_set  += res_a['set'][s]
            b_bids += res_b['bids'][s]
            b_made += res_b['made'][s]
            b_set  += res_b['set'][s]
        for lvl in (15, 20, 25, 30):
            for k in ('bids', 'made', 'set', 'made_pts'):
                a_by[lvl][k] += res_a['by_level'][lvl][k]
                b_by[lvl][k] += res_b['by_level'][lvl][k]
        a_made_pts += sum(res_a['by_level'][lvl]['made_pts']
                          for lvl in (15, 20, 25, 30))
        b_made_pts += sum(res_b['by_level'][lvl]['made_pts']
                          for lvl in (15, 20, 25, 30))
        a_def_pts += res_a['defender_pts']
        a_def_n   += res_a['defender_round_count']
        b_def_pts += res_b['defender_pts']
        b_def_n   += res_b['defender_round_count']
    return ((a_games, a_bids, a_made, a_set, a_made_pts, a_by,
             a_def_pts, a_def_n),
            (b_games, b_bids, b_made, b_set, b_made_pts, b_by,
             b_def_pts, b_def_n))


def _two_prop_z(set_a, n_a, set_b, n_b):
    """Two-proportion z-test on set-rate difference (B - A)."""
    if n_a == 0 or n_b == 0:
        return 0.0
    pa = set_a / n_a
    pb = set_b / n_b
    pooled = (set_a + set_b) / (n_a + n_b)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    return (pb - pa) / se if se else 0.0


def run_symmetric(args):
    """Symmetric A-vs-B configuration comparison on the same deal seeds.
    Headline metric: Δ set-rate (B - A); positive = coalition increases
    bidder set-rate (coalition works)."""
    chunk = 250
    tasks = []
    rem = args.deals
    idx = 0
    while rem > 0:
        n = min(chunk, rem)
        tasks.append((idx, n))
        idx += n
        rem -= n

    W = 84
    print('\n' + '=' * W)
    print(f'  SYMMETRIC SET-RATE — {args.config_b}  vs  {args.config_a}')
    print(f'  deals: {args.deals:,}  (games per config = deals; total = '
          f'{2*args.deals:,})  workers: {args.workers}')
    print(f'  seed-base: {args.seed_base:,}')
    print('=' * W)
    t0 = time.time()

    a_games = b_games = 0
    a_bids = a_made = a_set = a_made_pts = 0
    b_bids = b_made = b_set = b_made_pts = 0
    a_def_pts = b_def_pts = 0
    a_def_n = b_def_n = 0
    a_by = {lvl: {'bids': 0, 'made': 0, 'set': 0, 'made_pts': 0}
            for lvl in (15, 20, 25, 30)}
    b_by = {lvl: {'bids': 0, 'made': 0, 'set': 0, 'made_pts': 0}
            for lvl in (15, 20, 25, 30)}

    with Pool(args.workers, initializer=_init_symmetric,
              initargs=(args.config_a, args.config_b, args.seed_base)) as pool:
        for (ra, rb) in pool.imap_unordered(_run_chunk_symmetric, tasks):
            a_games += ra[0]; a_bids += ra[1]; a_made += ra[2]
            a_set   += ra[3]; a_made_pts += ra[4]
            b_games += rb[0]; b_bids += rb[1]; b_made += rb[2]
            b_set   += rb[3]; b_made_pts += rb[4]
            for lvl in (15, 20, 25, 30):
                for k in ('bids', 'made', 'set', 'made_pts'):
                    a_by[lvl][k] += ra[5][lvl][k]
                    b_by[lvl][k] += rb[5][lvl][k]
            a_def_pts += ra[6]; a_def_n += ra[7]
            b_def_pts += rb[6]; b_def_n += rb[7]
            done = a_games / args.deals
            a_rate = a_set / max(a_bids, 1) * 100
            b_rate = b_set / max(b_bids, 1) * 100
            print(f'\r  {done*100:5.1f}%  A={a_games:,}/B={b_games:,}  '
                  f'A:set={a_rate:5.2f}%  B:set={b_rate:5.2f}%',
                  end='', flush=True)

    el = time.time() - t0
    a_rate = a_set / max(a_bids, 1) * 100
    b_rate = b_set / max(b_bids, 1) * 100
    delta = b_rate - a_rate
    zval = _two_prop_z(a_set, a_bids, b_set, b_bids)
    sig = abs(zval) >= 1.96
    sig_lbl = 'SIGNIFICANT' if sig else 'not significant'

    a_avg = a_made_pts / max(a_made, 1)
    b_avg = b_made_pts / max(b_made, 1)

    print('\n\n' + '-' * W)
    print(f'  Config A ({args.config_a}):')
    print(f'    bids {a_bids:,}  made {a_made:,}  set {a_set:,}  '
          f'set-rate {a_rate:6.2f}%')
    print(f'  Config B ({args.config_b}):')
    print(f'    bids {b_bids:,}  made {b_made:,}  set {b_set:,}  '
          f'set-rate {b_rate:6.2f}%')
    print()
    print(f'  Δ set-rate (B − A): {delta:+.2f}pt  z={zval:+.2f}  {sig_lbl}')
    print()
    print(f'  Interpretation: when all 4 seats run "{args.config_b}", bidders')
    if delta > 0:
        print(f'  are SET {abs(delta):.2f}pt MORE often than under "{args.config_a}".')
        if sig:
            print(f'  Coalition is WORKING.')
    elif delta < 0:
        print(f'  are MADE {abs(delta):.2f}pt MORE often than under "{args.config_a}".')
        if sig:
            print(f'  Coalition is HURTING defenders — possible C1/C2 bug.')
    else:
        print(f'  have IDENTICAL set-rate to "{args.config_a}".')
    print()
    print('-' * W)
    print(f'  SANITY: bid volume (should be nearly identical — C1/C2 only')
    print(f'          affect card play, not bidding logic):')
    print(f'    A bids: {a_bids:,}    B bids: {b_bids:,}    '
          f'Δ: {b_bids - a_bids:+,}  ({(b_bids - a_bids)/max(a_bids,1)*100:+.2f}%)')
    print()
    print(f'  AVG made-pts per made-bid (coalition should DEPRESS this —')
    print(f'    defenders steal tricks the bidder would have taken):')
    print(f'    A: {a_avg:6.2f}    B: {b_avg:6.2f}    Δ: {b_avg - a_avg:+.2f}')
    print()
    # NICKEL-GRAB headline metric: avg per-defender raw pts per round.
    # Sum of per_player[p] across the 3 defenders, averaged per
    # defender-round (3 defenders per cutthroat round). Nickel-grab
    # should INCREASE this on B without depressing set-rate — it
    # rebalances post-locked play from "save" to "bank cheap pts".
    a_dpr = a_def_pts / max(a_def_n, 1)
    b_dpr = b_def_pts / max(b_def_n, 1)
    # SE via independent-sample bernoulli-like approx; defender pts
    # per round are bounded 0..15 so we use empirical variance scaling.
    # Conservative SE = sqrt((a_dpr*(15-a_dpr))/a_def_n + (b_dpr*(15-b_dpr))/b_def_n)
    # (treats pts as a 0-15 proportion-of-15 — coarse but defensible).
    se_def = math.sqrt(
        (a_dpr * (15 - a_dpr)) / max(a_def_n, 1)
      + (b_dpr * (15 - b_dpr)) / max(b_def_n, 1)
    ) if (a_def_n and b_def_n) else 0.0
    z_def = (b_dpr - a_dpr) / se_def if se_def else 0.0
    def_sig = 'SIGNIFICANT' if abs(z_def) >= 1.96 else 'not significant'
    print(f'  AVG defender-pts per round (NICKEL-GRAB signal — should')
    print(f'    INCREASE on B if defenders bank more cheap tricks):')
    print(f'    A: {a_dpr:6.3f}    B: {b_dpr:6.3f}    '
          f'Δ: {b_dpr - a_dpr:+.3f}  z={z_def:+.2f}  {def_sig}')
    print(f'    (sample: A {a_def_n:,} def-rounds / B {b_def_n:,} def-rounds)')
    print()
    print('-' * W)
    print(f'  PER-BID-LEVEL SET-RATE:')
    print(f'  {"":>5}  {"A bids":>8} {"A set":>8} {"A rate":>8}    '
          f'{"B bids":>8} {"B set":>8} {"B rate":>8}    {"Δ pt":>7} {"z":>7}')
    for lvl in (15, 20, 25, 30):
        ab = a_by[lvl]['bids']; aset = a_by[lvl]['set']
        bb = b_by[lvl]['bids']; bset = b_by[lvl]['set']
        if ab == 0 and bb == 0:
            continue
        ar = aset / max(ab, 1) * 100
        br = bset / max(bb, 1) * 100
        d = br - ar
        z = _two_prop_z(aset, ab, bset, bb)
        print(f'  {lvl:>5}  {ab:>8,} {aset:>8,} {ar:>7.2f}%    '
              f'{bb:>8,} {bset:>8,} {br:>7.2f}%    {d:>+6.2f} {z:>+7.2f}')
    print()
    print(f'  elapsed {el:.0f}s  '
          f'({(a_games + b_games)/max(el,1):,.0f} games/s)')
    print('-' * W)
    print()


def main():
    ap = argparse.ArgumentParser(
        description='45s cutthroat (FFA) bid set-rate analysis '
                    '(1-vs-3 OR symmetric A-vs-B)'
    )
    ap.add_argument('--symmetric', action='store_true',
                    help='Symmetric mode: compare two whole-table '
                         'configurations on the same deal seeds')
    ap.add_argument('--config-a', choices=sorted(REGISTRY),
                    help='[symmetric] baseline policy run at ALL 4 seats')
    ap.add_argument('--config-b', choices=sorted(REGISTRY),
                    help='[symmetric] comparison policy run at ALL 4 seats')
    ap.add_argument('--challenger', choices=sorted(REGISTRY),
                    help='[1-vs-3] policy to test vs 3x champion-cutthroat')
    ap.add_argument('--deals', type=int, default=2000,
                    help='deals (1-vs-3: games = 4 × deals seat-rotated; '
                         'symmetric: games = 2 × deals, one per config)')
    ap.add_argument('--workers', type=int, default=mp.cpu_count())
    ap.add_argument('--seed-base', type=int, default=0,
                    help='seed offset for hold-out re-validation')
    args = ap.parse_args()

    if args.symmetric:
        if not args.config_a or not args.config_b:
            ap.error('--symmetric requires --config-a and --config-b')
        run_symmetric(args)
        return

    if not args.challenger:
        ap.error('--challenger required for 1-vs-3 mode '
                 '(or pass --symmetric --config-a X --config-b Y)')

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
