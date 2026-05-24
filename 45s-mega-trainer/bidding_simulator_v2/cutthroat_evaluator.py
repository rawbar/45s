"""
cutthroat_evaluator.py — head-to-head evaluator for the CUTTHROAT (FFA) variant.

Pattern: 1 challenger vs 3 champion-cutthroats. Per deal, the challenger
rotates through ALL 4 seats while the same shuffle seed/dealer is used —
so deal luck is held constant across the 4 passes and only the seat (and
hence policy at each position) varies. This IS the variance-reduction
mechanism, analogous to the partner evaluator's mirrored pairing.

Metrics:
  - WIN RATE (1st place): fraction of games where the challenger finishes
    1st. 4-seat champion-vs-champion baseline = 25%.
  - PLACE SCORE: 1st=3, 2nd=2, 3rd=1, 4th=0. Mean across all games.
    Baseline = (3+2+1+0)/4 = 1.5.
  - PLACE DISTRIBUTION: % of games at each finishing position.

Place determined by final_scores; ties broken by closeness to 120
(higher score = better), then by being the round's bidder if at 120,
then by seat order. (Bidder-wins-tie at exactly 120 is already handled
inside play_game_cutthroat; here we rank for non-winners too.)

Usage:
  python -m bidding_simulator_v2.cutthroat_evaluator \\
      --challenger champion-cutthroat --deals 1000
  python -m bidding_simulator_v2.cutthroat_evaluator \\
      --challenger my-challenger --deals 5000 --workers 16
"""

import sys, os, io, argparse, time, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace')

import multiprocessing as mp
from multiprocessing import Pool

from bidding_simulator_v2.challengers import REGISTRY, CHAMPION_CUTTHROAT
from bidding_simulator_v2.cutthroat_runner import play_game_cutthroat


_CHALLENGER_NAME = None
_SEED_BASE = 0


def _init(name, seed_base=0):
    global _CHALLENGER_NAME, _SEED_BASE
    _CHALLENGER_NAME = name
    _SEED_BASE = seed_base


def _place(scores: list, winner: int) -> list:
    """Return places [p0, p1, p2, p3] where place=0 means 1st, 1=2nd, etc.
    Uses final_scores desc; the dict winner takes 1st by definition (handles
    the at-120 tie rule from cutthroat_runner). For 2nd/3rd/4th among the
    remaining seats, sort by score desc then by seat asc (stable tiebreak)."""
    others = sorted([s for s in range(4) if s != winner],
                    key=lambda s: (-scores[s], s))
    place_for = [0] * 4
    place_for[winner] = 0
    for rank, seat in enumerate(others, start=1):
        place_for[seat] = rank
    return place_for


def _run_chunk(args):
    """args = (start_idx, count).
    Returns counts: (games, wins, sum_place_score, place_hist[4])."""
    start, count = args
    chal = REGISTRY[_CHALLENGER_NAME]
    champ = CHAMPION_CUTTHROAT
    games = 0
    wins = 0           # challenger 1st-place count
    sum_pts = 0        # sum of place-score (3/2/1/0) for challenger
    hist = [0, 0, 0, 0]
    for i in range(start, start + count):
        seed = _SEED_BASE + i
        dealer = i % 4
        # 4 passes: challenger at seat 0, 1, 2, 3 (same seed → same shuffle
        # → identical deals, only seat assignment changes).
        for chal_seat in range(4):
            policies = [champ, champ, champ, champ]
            policies[chal_seat] = chal
            res = play_game_cutthroat(policies, seed, dealer)
            places = _place(res['final_scores'], res['winner'])
            chal_place = places[chal_seat]    # 0..3 (0=1st)
            score = 3 - chal_place             # 3,2,1,0
            sum_pts += score
            hist[chal_place] += 1
            if chal_place == 0:
                wins += 1
            games += 1
    return games, wins, sum_pts, hist


def _wilson(wins, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return p, centre - half, centre + half


def main():
    ap = argparse.ArgumentParser(
        description='45s cutthroat (FFA) head-to-head evaluator'
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

    W = 72
    print('\n' + '=' * W)
    print(f'  HEAD-TO-HEAD (CUTTHROAT): challenger {args.challenger}  '
          f'vs 3x champion-cutthroat')
    print(f'  deals: {args.deals:,}  (passes: 4*deals = {4*args.deals:,} games)'
          f'  workers: {args.workers}')
    print('=' * W)
    t0 = time.time()

    games = wins = sum_pts = 0
    hist = [0, 0, 0, 0]
    with Pool(args.workers, initializer=_init,
              initargs=(args.challenger, args.seed_base)) as pool:
        for (g, w, sp, h) in pool.imap_unordered(_run_chunk, tasks):
            games += g
            wins += w
            sum_pts += sp
            for i in range(4):
                hist[i] += h[i]
            done = games / (4 * args.deals)
            cur_wr = wins / max(games, 1)
            cur_ps = sum_pts / max(games, 1)
            print(f'\r  {done*100:5.1f}%  {games:,} games  '
                  f'wr={cur_wr*100:5.2f}%  ps={cur_ps:.3f}',
                  end='', flush=True)

    el = time.time() - t0

    # Win-rate stats vs 25% baseline
    wr, lo, hi = _wilson(wins, games)
    # Under H0: p=0.25, SE = sqrt(0.25*0.75/n)
    se_wr = math.sqrt(0.25 * 0.75 / games) if games else 0
    z_wr = (wr - 0.25) / se_wr if se_wr else 0.0

    # Place-score stats vs 1.5 baseline
    avg_ps = sum_pts / games if games else 0.0
    # Variance of place score under uniform random placement: E[X^2]=(9+4+1+0)/4
    # = 3.5; Var = 3.5 - 1.5^2 = 3.5 - 2.25 = 1.25; SE = sqrt(1.25/n)
    se_ps = math.sqrt(1.25 / games) if games else 0
    z_ps = (avg_ps - 1.5) / se_ps if se_ps else 0.0

    print('\n\n' + '-' * W)
    print(f'  win rate (1st place): {wr*100:5.2f}%   '
          f'(95% CI {lo*100:.2f}–{hi*100:.2f}%)')
    print(f'    vs 25% baseline   : {(wr-0.25)*100:+.2f} pts   z={z_wr:+.2f}   '
          f'{"SIGNIFICANT" if abs(z_wr) >= 1.96 else "not significant"}')
    print()
    print(f'  avg place score    : {avg_ps:5.3f} pts   '
          f'(3=1st, 2=2nd, 1=3rd, 0=4th)')
    print(f'    vs 1.5 baseline   : {(avg_ps-1.5):+.3f} pts   z={z_ps:+.2f}   '
          f'{"SIGNIFICANT" if abs(z_ps) >= 1.96 else "not significant"}')
    print()
    total = max(games, 1)
    print(f'  place distribution : '
          f'1st {hist[0]/total*100:5.2f}% / '
          f'2nd {hist[1]/total*100:5.2f}% / '
          f'3rd {hist[2]/total*100:5.2f}% / '
          f'4th {hist[3]/total*100:5.2f}%')
    print()
    print(f'  elapsed {el:.0f}s  ({games/max(el,1):,.0f} games/s)')
    print('-' * W)
    if args.challenger == 'champion-cutthroat' and not (23.5 <= wr*100 <= 26.5):
        print('  ⚠️  champion-cutthroat self-test off 25% — '
              'harness bias, investigate!')
    print()


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)
    main()
