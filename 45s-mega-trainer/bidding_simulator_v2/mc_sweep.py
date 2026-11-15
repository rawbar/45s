"""
mc_sweep.py — MC card-play strength vs the cleaned v2.31.26 champion.

Decision gate (latency already cleared): does any flat-PIMC config CLEARLY
beat the cleaned heuristic champion (enough to justify a risky JS card-engine
rewrite + PIMC's signalling weakness)? Marginal ≠ ship.

Coarse-to-fine: screen all configs at small N, deep-validate only the best.
Configs: rollout ∈ {random, greedy, heuristic} × k ∈ {40, 100}.
Paired mirrored deals (deal luck cancels). Champion = Policy() (cleaned).

Run:  python -m bidding_simulator_v2.mc_sweep --screen 1500 --final 8000
"""

import sys, os, io, argparse, time, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import multiprocessing as mp
from multiprocessing import Pool

from bidding_simulator_v2.policy import Policy
from bidding_simulator_v2.mc_policy import MCPolicy
from bidding_simulator_v2.game_runner import play_game

CHAMP = Policy()
SPECS = ['k40_random', 'k100_random', 'k40_greedy', 'k100_greedy',
         'k40_heuristic', 'k100_heuristic']
_SPEC = None
_MC = None


def _make(spec):
    k = 40 if spec.startswith('k40') else 100
    roll = spec.split('_', 1)[1]
    return MCPolicy(k_worlds=k, rollout=roll, max_rollouts=12000)


def _init(spec):
    global _SPEC, _MC
    _SPEC = spec
    _MC = _make(spec)


def _chunk(args):
    start, count = args
    cw = games = 0
    for i in range(start, start + count):
        seed, dealer = i, i % 4
        rA = play_game([_MC, CHAMP, _MC, CHAMP], seed, dealer)
        cw += (rA['winner_team'] == 0)
        rB = play_game([CHAMP, _MC, CHAMP, _MC], seed, dealer)
        cw += (rB['winner_team'] == 1)
        games += 2
    return cw, games


def _run(spec, deals, workers, base=0):
    tasks, idx, rem = [], base, deals
    while rem > 0:
        n = min(200, rem)
        tasks.append((idx, n)); idx += n; rem -= n
    cw = games = 0
    with Pool(workers, initializer=_init, initargs=(spec,)) as pool:
        for (a, g) in pool.imap_unordered(_chunk, tasks):
            cw += a; games += g
    p = cw / games
    z = (p - 0.5) / math.sqrt(0.25 / games)
    return {'spec': spec, 'p': p, 'z': z, 'games': games}


def _sanity(n=300):
    mc = _make('k40_random')
    for i in range(n):
        for sp in ([mc, CHAMP, mc, CHAMP], [CHAMP, mc, CHAMP, mc]):
            r = play_game(sp, 900000 + i, i % 4)
            assert r['winner_team'] in (0, 1)
    print(f'  sanity: {n*2} games, no exceptions / illegal plays — OK')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--screen', type=int, default=1500)
    ap.add_argument('--final', type=int, default=8000)
    ap.add_argument('--workers', type=int, default=mp.cpu_count())
    args = ap.parse_args()

    print('\n' + '=' * 70)
    print('  MC STRENGTH SWEEP vs cleaned v2.31.26 champion')
    print('=' * 70)
    t0 = time.time()
    print('  legality sanity...')
    _sanity(300)

    print(f'\n  SCREEN @ {args.screen:,} deals/config ({2*args.screen:,} games):')
    rows = []
    for sp in SPECS:
        r = _run(sp, args.screen, args.workers)
        rows.append(r)
        flag = 'beats' if r['z'] >= 1.96 else ('LOSES' if r['z'] <= -1.96 else 'tie')
        print(f"    {sp:<16} {r['p']*100:6.2f}%  z={r['z']:+5.2f}  [{flag}]  "
              f"({time.time()-t0:.0f}s)", flush=True)

    winners = [r for r in rows if r['z'] >= 1.96 and r['p'] > 0.5]
    print('=' * 70)
    if not winners:
        best = max(rows, key=lambda r: r['p'])
        print(f"  NO config beats champion at screen. Best: {best['spec']} "
              f"{best['p']*100:.2f}% (z={best['z']:+.2f}).")
        print('  → Flat PIMC does not clear the cleaned heuristic. Recommendation:')
        print('    shelve the JS MC rewrite; cleaned heuristic is the ceiling.')
        print(f'  (total {time.time()-t0:.0f}s)\n')
        return
    best = max(winners, key=lambda r: r['p'])
    print(f"  Screen leader: {best['spec']} {best['p']*100:.2f}% (z={best['z']:+.2f})")
    print(f"  Deep-validate @ {args.final:,} disjoint deals...")
    hv = _run(best['spec'], args.final, args.workers, base=5_000_000)
    ok = hv['z'] >= 1.96 and hv['p'] > 0.5
    print(f"  HOLD-OUT {best['spec']}: {hv['p']*100:.2f}% (z={hv['z']:+.2f}) "
          f"→ {'CONFIRMED — MC beats champion' if ok else 'did NOT hold (screen noise)'}")
    print(f'  (total {time.time()-t0:.0f}s)\n')


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)
    main()
