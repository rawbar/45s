"""
spoiler_eval.py — test the OPT-IN 'spoiler' bid rule in a GAME context
(full games to 120, real team scores).

Champion baseline = Policy() (rule absent → bit-identical faithful port).
Challenger        = REGISTRY['spoiler'] (rule on).

Rule fires when an opponent holds a bid that — given overmake (focus-sim:
15→≥20 59%, ≥25 35%) — likely carries them to 120, and champion would
otherwise let it stand: seize the contract with the minimum overbid (a
sacrifice). When it never fires the policies are identical, so any delta
is attributable to the spoiler. Stratify on the challenger team's CLOSEST
opponent need across the game:

   trig   closest opp need <= 25   (spoiler can fire)
   near   26..35                   (almost-trigger)
   safe   > 35                     (spoiler never fires → equity must be ~0)

Paired mirrored deals (same seed, swap which team is challenger) so deal
luck cancels. Per-bucket equity is challenger-vs-CHAMPION (selection bias
cancels). Winner = not regressing overall AND positive `trig` equity
(z>=1.96); re-validated on disjoint seeds.

Run:  python -m bidding_simulator_v2.spoiler_eval --deals 8000 --holdout 40000
"""

import sys, os, io, argparse, time, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace')

import multiprocessing as mp
from multiprocessing import Pool

from bidding_simulator_v2.policy import Policy
from bidding_simulator_v2.challengers import REGISTRY
from bidding_simulator_v2.game_runner import play_game

CHAMP = Policy()
CHAL = REGISTRY['spoiler']


def _bucket(need):
    if need <= 25:  return 0          # trig  (spoiler can fire)
    if need <= 35:  return 1          # near
    return 2                          # safe  (spoiler never fires)


def _zp(w1, n1, w2, n2):
    """Two-proportion z (challenger vs champion within a bucket)."""
    if not n1 or not n2:
        return 0.0, 0.0, 0.0
    p1, p2 = w1 / n1, w2 / n2
    pool = (w1 + w2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    return p1, p2, ((p1 - p2) / se if se else 0.0)


def _chunk(args):
    """Paired challenger-vs-champion. Bucket EACH team by its OWN closest
    opponent need so the (outcome-correlated) selection bias is identical
    for challenger and champion and cancels in the per-bucket equity."""
    start, count = args
    cw = games = 0
    cLn = [0, 0, 0]; cLw = [0, 0, 0]      # challenger team n / wins / bucket
    pLn = [0, 0, 0]; pLw = [0, 0, 0]      # champion   team n / wins / bucket
    for i in range(start, start + count):
        seed, dealer = i, i % 4
        for swap in (0, 1):
            if swap == 0:
                r = play_game([CHAL, CHAMP, CHAL, CHAMP], seed, dealer)
                cteam, pteam = 0, 1
            else:
                r = play_game([CHAMP, CHAL, CHAMP, CHAL], seed, dealer)
                cteam, pteam = 1, 0
            w = r['winner_team']
            con = r['closest_opp_need']
            cw += (w == cteam); games += 1
            bc = _bucket(con[cteam]); cLn[bc] += 1; cLw[bc] += (w == cteam)
            bp = _bucket(con[pteam]); pLn[bp] += 1; pLw[bp] += (w == pteam)
    return cw, games, cLn, cLw, pLn, pLw


def _run(deals, workers, base=0):
    tasks, idx, rem = [], base, deals
    while rem > 0:
        n = min(250, rem)
        tasks.append((idx, n)); idx += n; rem -= n
    cw = games = 0
    cLn = [0, 0, 0]; cLw = [0, 0, 0]; pLn = [0, 0, 0]; pLw = [0, 0, 0]
    with Pool(workers) as pool:
        for (a, g, c1, c2, p1, p2) in pool.imap_unordered(_chunk, tasks):
            cw += a; games += g
            for k in range(3):
                cLn[k] += c1[k]; cLw[k] += c2[k]
                pLn[k] += p1[k]; pLw[k] += p2[k]
    p = cw / games
    z = (p - 0.5) / math.sqrt(0.25 / games)
    out = {'p': p, 'z': z, 'games': games, 'buckets': []}
    for k in range(3):
        cr, pr, bz = _zp(cLw[k], cLn[k], pLw[k], pLn[k])
        out['buckets'].append({'cr': cr, 'pr': pr, 'eq': cr - pr,
                               'z': bz, 'cn': cLn[k], 'pn': pLn[k]})
    return out


def _fmt(tag, r):
    b = r['buckets']
    def cell(j, nm):
        x = b[j]
        return (f"{nm} eq{x['eq']*100:+5.2f}(z={x['z']:+4.1f}) "
                f"[{x['cr']*100:.1f}v{x['pr']*100:.1f} n={x['cn']}/{x['pn']}]")
    return (f"  {tag}: overall {r['p']*100:5.2f}%(z={r['z']:+.2f}) | "
            f"{cell(0,'trig')}  {cell(1,'near')}  {cell(2,'safe')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--deals', type=int, default=8000)
    ap.add_argument('--holdout', type=int, default=40000)
    ap.add_argument('--workers', type=int, default=mp.cpu_count())
    args = ap.parse_args()

    print('\n' + '=' * 78)
    print('  SPOILER (opt-in) — game-context paired bid test vs champion')
    print('  trig=closest oppNeed<=25 (can fire)  near=26-35  safe=>35 (no-op)')
    print('=' * 78)
    t0 = time.time()
    sc = _run(args.deals, args.workers, base=0)
    print(_fmt('SCREEN', sc), f"  ({time.time()-t0:.0f}s)", flush=True)

    trig = sc['buckets'][0]
    safe = sc['buckets'][2]
    # equity vs the CHAMPION team in the same bucket cancels selection bias.
    ok_screen = (sc['z'] > -1.96 and trig['z'] >= 1.96 and trig['eq'] > 0)
    # sanity: safe-bucket equity MUST be ~0 (rule never fires there → both
    # teams are champion play; any large |eq| = harness asymmetry / leak).
    if abs(safe['eq']) > 0.03 and safe['cn'] > 500:
        print(f"  ⚠ safe-bucket equity {safe['eq']*100:+.2f}pt — rule leaking "
              f"outside trigger or harness asymmetry; investigate first.")
    print('=' * 78)
    if not ok_screen:
        print("  NO WIN at screen: spoiler does not significantly beat "
              "champion in the trigger regime without regressing overall.")
        print(f"  → keep it OFF (champion). (total {time.time()-t0:.0f}s)\n")
        return
    print(f"  Screen win in trigger regime (eq +{trig['eq']*100:.2f}pt "
          f"z={trig['z']:+.2f}). Re-validating on {args.holdout:,} disjoint "
          f"deals...")
    hv = _run(args.holdout, args.workers, base=20_000_000)
    print(_fmt('HOLDOUT', hv))
    ht = hv['buckets'][0]
    confirmed = (hv['z'] > -1.96 and ht['z'] >= 1.96 and ht['eq'] > 0)
    print('=' * 78)
    print("  VERDICT: " + ("CONFIRMED — spoiler helps the trigger "
          "regime and does not regress overall. Candidate to ship "
          "(pending user authorization)." if confirmed else
          "did NOT hold on held-out — treat screen as noise, keep OFF."))
    print(f"  (total {time.time()-t0:.0f}s)\n")


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)
    main()
