"""
audit.py — all-rules ablation audit.

For every situational rule (each card-play rule + desperation/cruise), run
"champion with that ONE rule OFF" vs champion over paired mirrored deals.

Interpretation per rule:
  challenger (rule OFF) win% significantly < 50  → rule CARRIES WEIGHT (keep)
  ≈ 50 (not significant)                          → rule is INERT (cut candidate)
  significantly > 50                              → rule HURTS (cut / fix)

Also reports conditional comeback equity (champion vs challenger from the
losing state, opp ≥105) so a rare-but-real effect isn't hidden by the
whole-game average. Ranked table; champion self-test row must read ~50%.

Run:  python -m bidding_simulator_v2.audit --deals 10000
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
_NAME = None


def _init(name):
    global _NAME
    _NAME = name


def _chunk(args):
    start, count = args
    chal = REGISTRY[_NAME]
    cw = games = 0
    cLn = cLw = pLn = pLw = 0
    for i in range(start, start + count):
        seed, dealer = i, i % 4
        rA = play_game([chal, CHAMP, chal, CHAMP], seed, dealer)
        wA, flA = rA['winner_team'], rA['faced_losing']
        cw += (wA == 0)
        if flA[0]: cLn += 1; cLw += (wA == 0)
        if flA[1]: pLn += 1; pLw += (wA == 1)
        rB = play_game([CHAMP, chal, CHAMP, chal], seed, dealer)
        wB, flB = rB['winner_team'], rB['faced_losing']
        cw += (wB == 1)
        if flB[1]: cLn += 1; cLw += (wB == 1)
        if flB[0]: pLn += 1; pLw += (wB == 0)
        games += 2
    return cw, games, cLn, cLw, pLn, pLw


def _run(name, deals, workers):
    tasks, idx, rem = [], 0, deals
    while rem > 0:
        n = min(250, rem)
        tasks.append((idx, n)); idx += n; rem -= n
    cw = games = cLn = cLw = pLn = pLw = 0
    with Pool(workers, initializer=_init, initargs=(name,)) as pool:
        for (a, g, c1, c2, p1, p2) in pool.imap_unordered(_chunk, tasks):
            cw += a; games += g; cLn += c1; cLw += c2; pLn += p1; pLw += p2
    p = cw / games
    z = (p - 0.5) / math.sqrt(0.25 / games)
    cr = cLw / cLn if cLn else 0.0
    pr = pLw / pLn if pLn else 0.0
    if cLn and pLn:
        pl = (cLw + pLw) / (cLn + pLn)
        se = math.sqrt(pl * (1 - pl) * (1 / cLn + 1 / pLn))
        zc = (cr - pr) / se if se else 0.0
    else:
        zc = 0.0
    return {'name': name, 'p': p, 'z': z, 'eq': cr - pr, 'zc': zc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--deals', type=int, default=10000)
    ap.add_argument('--workers', type=int, default=mp.cpu_count())
    args = ap.parse_args()

    names = ['champion'] + [n for n in REGISTRY if n != 'champion']
    print('\n' + '=' * 92)
    print(f'  ALL-RULES ABLATION AUDIT — {args.deals:,} deals/rule '
          f'({2*args.deals:,} games)  rule OFF vs champion')
    print('=' * 92)
    t0 = time.time()
    rows = []
    for nm in names:
        r = _run(nm, args.deals, args.workers)
        rows.append(r)
        print(f"  {nm:<40} win {r['p']*100:6.2f}% (z={r['z']:+5.2f})  "
              f"cb-equity {r['eq']*100:+5.2f} (z={r['zc']:+5.2f})", flush=True)

    print('=' * 92)
    print('  RANKED — rules whose removal most hurts win rate carry the most weight:')
    ranked = sorted([r for r in rows if r['name'] != 'champion'],
                    key=lambda r: r['p'])
    for r in ranked:
        if r['z'] <= -1.96:
            verdict = 'CARRIES WEIGHT (keep)'
        elif r['z'] >= 1.96:
            verdict = 'HURTS (cut/fix)'
        else:
            verdict = 'inert (cut candidate)'
        print(f"  {r['name']:<40} {r['p']*100:6.2f}% (z={r['z']:+5.2f})  → {verdict}")
    print(f'  (champion self-test {rows[0]["p"]*100:.2f}% — must be ~50)')
    print(f'  total {time.time()-t0:.0f}s')
    print('=' * 92 + '\n')


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)
    main()
