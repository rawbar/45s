"""
sweep.py — (T, W) desperation-trigger sweep, comeback equity stratified by
how close the opponent ever got to winning.

Champion baseline = decide_bid defaults (T=30, W=30) — the placeholder.
Challenger cell = desperation trigger `they_need <= T and we_need > W`.

For each (game, team) we record the team's CLOSEST opponent need (smallest
120 - opp_score seen at a round start) and bucket the game into the most
dangerous regime it ever reached:

    B15  opponent got within ≤15  (a made 15 ends it)
    B20  16–20                    (needs a 20)
    B25  21–25                    (needs a 25)
    B30  26–30                    (needs a 30)
    (>30 = never in danger → excluded from conditional)

Per bucket we compare challenger win% vs champion win% (comeback equity).
This makes the T ceiling testable: at B30 a T=15 trigger never fires but
T=30 does. Winner = best OVERALL in-danger equity (z≥1.96, positive) among
cells that do NOT significantly regress unconditional win rate; per-bucket
breakdown shown; winner re-validated on a DISJOINT seed range.

Run:  python -m bidding_simulator_v2.sweep --deals 12000 --holdout 60000
"""

import sys, os, io, argparse, time, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import multiprocessing as mp
from multiprocessing import Pool

from bidding_simulator_v2.policy import Policy
from bidding_simulator_v2 import bidding
from bidding_simulator_v2.game_runner import play_game

T_GRID = [15, 20, 25, 30, 35, 40]
W_GRID = [0, 15, 30]
BUCKETS = ['≤15', '16-20', '21-25', '26-30']   # index 0..3
CHAMP = Policy()

_T = _W = None


def _init(t, w):
    global _T, _W
    _T, _W = t, w


class _ParamPolicy(Policy):
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  desp_they_need=_T, desp_we_need_floor=_W)


def _bucket(need):
    if need <= 15:  return 0
    if need <= 20:  return 1
    if need <= 25:  return 2
    if need <= 30:  return 3
    return -1


def _chunk(args):
    """Returns cw, games, and per-bucket [cLn,cLw,pLn,pLw] (challenger /
    champion n & wins, conditioned on closest opponent need bucket)."""
    start, count, base = args
    chal = _ParamPolicy()
    cw = games = 0
    # per bucket: challenger n,w ; champion n,w
    cLn = [0, 0, 0, 0]; cLw = [0, 0, 0, 0]
    pLn = [0, 0, 0, 0]; pLw = [0, 0, 0, 0]
    for i in range(start, start + count):
        seed = base + i
        dealer = i % 4
        for swap in (0, 1):
            if swap == 0:
                r = play_game([chal, CHAMP, chal, CHAMP], seed, dealer)
                chal_team, champ_team = 0, 1
            else:
                r = play_game([CHAMP, chal, CHAMP, chal], seed, dealer)
                chal_team, champ_team = 1, 0
            w = r['winner_team']
            con = r['closest_opp_need']
            cw += (w == chal_team)
            bc = _bucket(con[chal_team])
            if bc >= 0:
                cLn[bc] += 1; cLw[bc] += (w == chal_team)
            bp = _bucket(con[champ_team])
            if bp >= 0:
                pLn[bp] += 1; pLw[bp] += (w == champ_team)
            games += 1
    return cw, games, cLn, cLw, pLn, pLw


def _two_prop_z(w1, n1, w2, n2):
    if not n1 or not n2:
        return 0.0, 0.0, 0.0
    p1, p2 = w1 / n1, w2 / n2
    pooled = (w1 + w2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se if se else 0.0
    return p1, p2, z


def _run_cell(t, w, deals, workers, seed_base):
    chunk = 250
    tasks, idx, rem = [], 0, deals
    while rem > 0:
        n = min(chunk, rem)
        tasks.append((idx, n, seed_base)); idx += n; rem -= n
    cw = games = 0
    cLn = [0]*4; cLw = [0]*4; pLn = [0]*4; pLw = [0]*4
    with Pool(workers, initializer=_init, initargs=(t, w)) as pool:
        for (a, g, c1, c2, p1, p2) in pool.imap_unordered(_chunk, tasks):
            cw += a; games += g
            for k in range(4):
                cLn[k] += c1[k]; cLw[k] += c2[k]
                pLn[k] += p1[k]; pLw[k] += p2[k]
    p_unc = cw / games
    z_unc = (p_unc - 0.5) / math.sqrt(0.25 / games)
    buckets = []
    for k in range(4):
        cr, pr, z = _two_prop_z(cLw[k], cLn[k], pLw[k], pLn[k])
        buckets.append({'cr': cr, 'pr': pr, 'eq': cr - pr, 'z': z,
                        'cn': cLn[k], 'pn': pLn[k]})
    # overall in-danger (all buckets pooled)
    oc_w, oc_n = sum(cLw), sum(cLn)
    op_w, op_n = sum(pLw), sum(pLn)
    ocr, opr, oz = _two_prop_z(oc_w, oc_n, op_w, op_n)
    return {'t': t, 'w': w, 'games': games, 'p_unc': p_unc, 'z_unc': z_unc,
            'buckets': buckets, 'o_eq': ocr - opr, 'o_z': oz,
            'o_cr': ocr, 'o_pr': opr, 'o_cn': oc_n, 'o_pn': op_n}


def _fmt_cell(r):
    bs = '  '.join(f"{BUCKETS[k]}:{r['buckets'][k]['eq']*100:+5.1f}"
                    f"({r['buckets'][k]['z']:+4.1f})" for k in range(4))
    return (f"  T{r['t']:>2} W{r['w']:>2} | unc {r['p_unc']*100:5.2f}%"
            f"({r['z_unc']:+4.1f}) | OVR {r['o_eq']*100:+5.2f}({r['o_z']:+5.2f}) | {bs}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--deals', type=int, default=12000)
    ap.add_argument('--holdout', type=int, default=60000)
    ap.add_argument('--workers', type=int, default=mp.cpu_count())
    args = ap.parse_args()

    print('\n' + '=' * 100)
    print('  DESPERATION (T,W) SWEEP — comeback equity stratified by opponent distance')
    print(f'  T {T_GRID}  W {W_GRID}  | {args.deals:,} deals/cell '
          f'({2*args.deals:,} games)  baseline T30/W30')
    print('  cols: uncond win%(z) | OVERALL in-danger equity(z) | per-bucket eq%(z)')
    print('=' * 100)
    t0 = time.time()
    rows = []
    for t in T_GRID:
        for w in W_GRID:
            r = _run_cell(t, w, args.deals, args.workers, 0)
            rows.append(r)
            print(_fmt_cell(r), flush=True)

    cands = [r for r in rows
             if r['z_unc'] > -1.96 and r['o_z'] >= 1.96 and r['o_eq'] > 0]
    print('=' * 100)
    if not cands:
        print('  NO cell beats placeholder with significant overall comeback equity.')
        print('  → desperation trigger tuning is a bounded lever; T30/W30 stands.')
        print(f'  (sweep {time.time()-t0:.0f}s)\n')
        return
    best = max(cands, key=lambda r: r['o_eq'])
    print(f"  BEST in-sample: T={best['t']} W={best['w']}  "
          f"overall equity {best['o_eq']*100:+.2f}pt (z={best['o_z']:+.2f}), "
          f"uncond {best['p_unc']*100:.2f}% (z={best['z_unc']:+.2f})")
    for k in range(4):
        b = best['buckets'][k]
        print(f"    {BUCKETS[k]:>6}: eq {b['eq']*100:+5.2f}pt (z={b['z']:+.2f})  "
              f"chal {b['cr']*100:.1f}% vs champ {b['pr']*100:.1f}%  "
              f"n={b['cn']}/{b['pn']}")
    print(f"  Re-validating on DISJOINT seeds ({args.holdout:,} deals)...")
    hv = _run_cell(best['t'], best['w'], args.holdout, args.workers, 10_000_000)
    ok = hv['o_z'] >= 1.96 and hv['o_eq'] > 0 and hv['z_unc'] > -1.96
    print(f"  HOLD-OUT T={best['t']} W={best['w']}: overall equity "
          f"{hv['o_eq']*100:+.2f}pt (z={hv['o_z']:+.2f}), "
          f"uncond {hv['p_unc']*100:.2f}% (z={hv['z_unc']:+.2f})  "
          f"→ {'CONFIRMED' if ok else 'DID NOT HOLD (in-sample noise)'}")
    for k in range(4):
        b = hv['buckets'][k]
        print(f"    {BUCKETS[k]:>6}: eq {b['eq']*100:+5.2f}pt (z={b['z']:+.2f})  n={b['cn']}/{b['pn']}")
    print(f'  (total {time.time()-t0:.0f}s)')
    print('=' * 100 + '\n')


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)
    main()
