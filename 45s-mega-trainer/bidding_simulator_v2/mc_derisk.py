"""
mc_derisk.py — settle whether the MC +2.5pt is REAL or a self-referential
artifact, before committing to a JS PIMC port.

The prior sweep's only winning config (k100_heuristic, ~+2.5pt) used the
champion ImprovedAI as its OWN rollout — PIMC rolling the champion out
against itself. That can "win" by predicting a known opponent perfectly
rather than by superior strategy; it would not transfer to humans.
random/greedy rollouts lost, but they are too weak to be a fair test.

Decisive experiment — fix k=100, vary ONLY the rollout world-model:
  heuristic : champion ImprovedAI rollout      (CIRCULAR — reproduce +2.5)
  indep     : competent, structurally-decorrelated player  (THE TEST)
  greedy    : weak floor                       (sanity — expect ~loss)

Verdict:
  indep ≈ heuristic (clearly >50, holds out)  → REAL skill. Flip to SHIP;
                                                 then run --latency budget.
  indep collapses toward greedy (tie/loss)    → ARTIFACT. Confirm NO ship.

Run:  python -m bidding_simulator_v2.mc_derisk --screen 1500 --final 6000
      python -m bidding_simulator_v2.mc_derisk --latency 120
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
from bidding_simulator_v2.mc_policy import MCPolicy
from bidding_simulator_v2.game_runner import play_game

CHAMP = Policy()
SPECS = ['k100_heuristic', 'k100_indep', 'k100_greedy']
_MC = None


def _make(spec, max_rollouts=12000):
    roll = spec.split('_', 1)[1]
    return MCPolicy(k_worlds=100, rollout=roll, max_rollouts=max_rollouts)


def _init(spec):
    global _MC
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


def _latency(deals, max_rollouts):
    """Single-process: device-independent node counts + wall ms per
    decision, split by trick, for the decorrelated indep config."""
    mc = _make('k100_indep', max_rollouts=max_rollouts)
    for i in range(deals):
        play_game([mc, CHAMP, mc, CHAMP], 7_000_000 + i, i % 4)
    s = mc.stats
    d, t = max(1, s['decisions']), s['time']
    print(f"  indep  max_rollouts={max_rollouts:<6}  "
          f"{s['decisions']} decisions over {deals} deals")
    print(f"    avg {s['rollouts']/d:8.0f} rollouts/decision   "
          f"{1000*t/d:6.1f} ms/decision   {1000*t/d:6.1f} avg")
    for tn in sorted(s['by_trick']):
        b = s['by_trick'][tn]
        n = max(1, b['n'])
        print(f"    trick {tn}:  {b['roll']/n:8.0f} rollouts   "
              f"{1000*b['t']/n:6.1f} ms/decision")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--screen', type=int, default=1500)
    ap.add_argument('--final', type=int, default=6000)
    ap.add_argument('--workers', type=int, default=mp.cpu_count())
    ap.add_argument('--latency', type=int, default=0,
                    help='if >0: run N-deal single-proc latency/node probe')
    ap.add_argument('--budget', type=int, default=1500,
                    help='mobile rollout cap for the latency probe')
    ap.add_argument('--specs', type=str, default=','.join(SPECS),
                    help='CSV subset of specs to screen (heuristic is the '
                         'known ~52.5%% circular baseline; skip to save ~8h)')
    args = ap.parse_args()
    specs = [s.strip() for s in args.specs.split(',') if s.strip()]

    if args.latency:
        print('\n' + '=' * 70)
        print('  MC LATENCY / NODE PROBE — decorrelated indep rollout')
        print('=' * 70)
        _latency(args.latency, 12000)
        print(f'  -- mobile budget cap (max_rollouts={args.budget}) --')
        _latency(args.latency, args.budget)
        print()
        return

    print('\n' + '=' * 70)
    print('  MC DE-RISK — is +2.5pt real or a self-referential artifact?')
    print('=' * 70)
    t0 = time.time()

    print(f'\n  SCREEN @ {args.screen:,} deals/config '
          f'({2*args.screen:,} games):')
    rows = []
    for sp in specs:
        r = _run(sp, args.screen, args.workers)
        rows.append(r)
        flag = ('beats' if r['z'] >= 1.96
                else 'LOSES' if r['z'] <= -1.96 else 'tie')
        print(f"    {sp:<16} {r['p']*100:6.2f}%  z={r['z']:+5.2f}  "
              f"[{flag}]  ({time.time()-t0:.0f}s)", flush=True)

    R = {r['spec']: r for r in rows}
    ind = R.get('k100_indep')
    if ind is None:
        print("  (no k100_indep in --specs — nothing decisive to judge)\n")
        return
    h = R.get('k100_heuristic')
    g = R.get('k100_greedy')
    # established prior-sweep circular baseline (memory): ~52.5% screen/heldout
    h_txt = (f"{h['p']*100:.2f}%" if h else "~52.5% (prior sweep)")
    g_txt = (f"{g['p']*100:.2f}%" if g else "~loss (prior sweep)")
    print('=' * 70)
    print(f"  circular(heuristic) {h_txt}   "
          f"DECORRELATED(indep) {ind['p']*100:.2f}%   "
          f"floor(greedy) {g_txt}")

    decisive = (ind['z'] >= 1.96 and ind['p'] > 0.5)
    if decisive:
        print(f"  indep BEATS champion at screen — running disjoint "
              f"held-out @ {args.final:,} deals...")
        hv = _run('k100_indep', args.final, args.workers, base=8_000_000)
        ok = hv['z'] >= 1.96 and hv['p'] > 0.5
        print(f"  HOLD-OUT indep: {hv['p']*100:.2f}% (z={hv['z']:+.2f}) "
              f"→ {'CONFIRMED' if ok else 'did NOT hold (screen noise)'}")
        if ok:
            print("  VERDICT: gain is REAL (survives a decorrelated world "
                  "model). Recommendation FLIPS → port worth it; next run "
                  "--latency to size the mobile budget.")
        else:
            print("  VERDICT: screen win did not replicate — treat as NOISE,"
                  " do NOT ship.")
    else:
        print("  indep does NOT beat champion. The +2.5pt was a "
              "SELF-REFERENTIAL ARTIFACT (PIMC only wins when it rolls the "
              "champion out against itself).")
        print("  VERDICT: confirmed — do NOT ship the JS PIMC port. The "
              "cleaned heuristic is the practical ceiling.")
    print(f'  (total {time.time()-t0:.0f}s)\n')


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)
    main()
