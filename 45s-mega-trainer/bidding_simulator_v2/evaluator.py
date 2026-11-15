"""
evaluator.py — head-to-head AI evaluator with paired mirrored deals.

Each "deal" = one seed + start_dealer, played TWICE:
  game A: challenger drives team 0 (seats 0,2), champion team 1
  game B: SAME seed/dealer, challenger drives team 1, champion team 0
Deal luck cancels across the pair → small win-rate edges become detectable.

Reports challenger win rate over all games (2 × deals), Wilson 95% CI, and
two-sided significance vs 50%. champion-vs-champion must read ~50.0%.

Usage:
  python -m bidding_simulator_v2.evaluator --challenger no-desperation --deals 25000
  python -m bidding_simulator_v2.evaluator --challenger champion --deals 10000
"""

import sys, os, io, argparse, time, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import multiprocessing as mp
from multiprocessing import Pool

from bidding_simulator_v2.policy import Policy
from bidding_simulator_v2.challengers import REGISTRY
from bidding_simulator_v2.game_runner import play_game

CHAMP = Policy()
_CHALLENGER_NAME = None  # set per-worker via initializer
_SEED_BASE = 0           # offset for disjoint-seed hold-out re-validation


def _init(name, seed_base=0):
    global _CHALLENGER_NAME, _SEED_BASE
    _CHALLENGER_NAME = name
    _SEED_BASE = seed_base


def _run_chunk(args):
    """args = (start_idx, count).
    Returns (cw, games, rounds_sum,
             chal_L_n, chal_L_w, champ_L_n, champ_L_w)
    where *_L_* are conditional on that policy's team having faced the
    losing state (opponent >= LOSING_THRESHOLD at some round start)."""
    start, count = args
    chal = REGISTRY[_CHALLENGER_NAME]
    cw = games = rounds_sum = 0
    cLn = cLw = pLn = pLw = 0  # challenger / champion losing-state n & wins
    for i in range(start, start + count):
        seed = _SEED_BASE + i
        dealer = i % 4
        # game A: challenger = team 0 (seats 0,2), champion = team 1
        rA = play_game([chal, CHAMP, chal, CHAMP], seed, dealer)
        wA = rA['winner_team']
        flA = rA['faced_losing']
        cw += (wA == 0)
        rounds_sum += rA['rounds']
        if flA[0]:                       # challenger team faced losing
            cLn += 1; cLw += (wA == 0)
        if flA[1]:                       # champion team faced losing
            pLn += 1; pLw += (wA == 1)
        # game B: SAME seed/dealer, challenger = team 1 (seats 1,3)
        rB = play_game([CHAMP, chal, CHAMP, chal], seed, dealer)
        wB = rB['winner_team']
        flB = rB['faced_losing']
        cw += (wB == 1)
        rounds_sum += rB['rounds']
        if flB[1]:                       # challenger team faced losing
            cLn += 1; cLw += (wB == 1)
        if flB[0]:                       # champion team faced losing
            pLn += 1; pLw += (wB == 0)
        games += 2
    return cw, games, rounds_sum, cLn, cLw, pLn, pLw


def _wilson(wins, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return p, centre - half, centre + half


def main():
    ap = argparse.ArgumentParser(description='45s head-to-head AI evaluator')
    ap.add_argument('--challenger', required=True, choices=sorted(REGISTRY),
                    help='policy to test vs champion')
    ap.add_argument('--deals', type=int, default=20000,
                    help='mirrored deal pairs (games = 2 × deals)')
    ap.add_argument('--workers', type=int, default=mp.cpu_count())
    ap.add_argument('--seed-base', type=int, default=0,
                    help='seed offset for a DISJOINT-seed hold-out re-validation '
                         '(e.g. 5000000); 0 = the standard 0..deals range')
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

    W = 64
    print('\n' + '=' * W)
    print(f'  HEAD-TO-HEAD: {args.challenger}  vs  champion')
    print(f'  deals: {args.deals:,}  (games: {2*args.deals:,})  workers: {args.workers}')
    print('=' * W)
    t0 = time.time()

    cw = games = rsum = 0
    cLn = cLw = pLn = pLw = 0
    with Pool(args.workers, initializer=_init,
              initargs=(args.challenger, args.seed_base)) as pool:
        for (c, g, r, a, b, e, f) in pool.imap_unordered(_run_chunk, tasks):
            cw += c; games += g; rsum += r
            cLn += a; cLw += b; pLn += e; pLw += f
            done = games / (2 * args.deals)
            print(f'\r  {done*100:5.1f}%  {games:,} games  '
                  f'{cw/max(games,1)*100:5.2f}% win', end='', flush=True)

    el = time.time() - t0
    p, lo, hi = _wilson(cw, games)
    se = math.sqrt(0.25 / games) if games else 0
    zval = (p - 0.5) / se if se else 0.0
    sig = abs(zval) >= 1.96

    print('\n\n' + '-' * W)
    print('  UNCONDITIONAL (whole game):')
    print(f'    challenger wins : {cw:,} / {games:,}')
    print(f'    win rate        : {p*100:.2f}%   (95% CI {lo*100:.2f}–{hi*100:.2f}%)')
    print(f'    vs 50%          : {(p-0.5)*100:+.2f} pts   z={zval:+.2f}   '
          f'{"SIGNIFICANT" if sig else "not significant"}')
    print()
    # Conditional comeback equity: among games where that policy's team
    # faced the losing state, did it win? Compare challenger vs champion.
    cr = cLw / cLn if cLn else 0.0
    pr = pLw / pLn if pLn else 0.0
    freq = (cLn + pLn) / (2 * games) if games else 0.0
    print(f'  CONDITIONAL on facing losing state (opp ≥ 105):')
    print(f'    occurred in     : {(cLn+pLn):,} of {2*games:,} team-games '
          f'({freq*100:.1f}%)')
    print(f'    challenger (rule on) wins : {cLw:,}/{cLn:,}  = {cr*100:.2f}%')
    print(f'    champion  (baseline) wins : {pLw:,}/{pLn:,}  = {pr*100:.2f}%')
    if cLn and pLn:
        pooled = (cLw + pLw) / (cLn + pLn)
        se2 = math.sqrt(pooled * (1 - pooled) * (1 / cLn + 1 / pLn))
        z2 = (cr - pr) / se2 if se2 else 0.0
        print(f'    comeback equity : {(cr-pr)*100:+.2f} pts   z={z2:+.2f}   '
              f'{"SIGNIFICANT" if abs(z2) >= 1.96 else "not significant"}')
    print(f'\n  avg rounds/game : {rsum/max(games,1):.1f}'
          f'   elapsed {el:.0f}s  ({games/max(el,1):,.0f} games/s)')
    print('-' * W)
    if args.challenger == 'champion' and not (48.5 <= p*100 <= 51.5):
        print('  ⚠️  champion self-test off 50% — harness bias, investigate!')
    print()


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)
    main()
