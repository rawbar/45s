"""Round-level paired A/B: SamplingPolicy vs champion on identical deals.
Metric: challenger-team round net minus opponent-team round net (points)."""
import sys, os, random, time, math, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))) + '/45s-mega-trainer') if False else None
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import multiprocessing as mp
from game_engine import Deck
from bidding_simulator_v2.bidding import find_best_trump_suit
from bidding_simulator_v2.policy import Policy
from bidding_simulator_v2.game_runner import _play_round
from bidding_simulator_v2.endgame_sampler import SamplingPolicy

def _deal_and_bid(seed, champ):
    rng = random.Random(seed)
    dealer = seed % 4
    d = Deck(); rng.shuffle(d.cards)
    hands = [d.deal(5) for _ in range(4)]
    kitty = d.deal(3); rest = d.cards[:]
    bids = [None]*4; suits = [None]*4; hb = 0
    for p in [(dealer+1)%4, (dealer+2)%4, (dealer+3)%4, dealer]:
        pb = bids[(p+2)%4] if bids[(p+2)%4] not in (None, -1) else 0
        b, s = champ.decide_bid(hands[p], hb, p, dealer, 0, 0, pb)
        bids[p] = b; suits[p] = s
        if b > hb: hb = b
    mx = 0; w = dealer
    for i in range(4):
        if (bids[i] or 0) > mx: mx = bids[i]; w = i
    if mx == 0:
        w = dealer; mx = 15; suits[w] = find_best_trump_suit(hands[w])['suit']
    trump = suits[w] or find_best_trump_suit(hands[w])['suit']
    return w, mx, trump, hands, kitty, rest

def _chunk(args):
    start, count, n_worlds, start_trick, eps, cheat, oc, cons = args
    champ = Policy()
    S = SamplingPolicy(n_worlds=n_worlds, start_trick=start_trick, eps=eps, seed=start+1, cheat=cheat, oracle_counts=oc, consistency=cons)
    diffs = []
    for seed in range(start, start+count):
        w, mx, trump, hands, kitty, rest = _deal_and_bid(seed, champ)
        a0, a1 = _play_round(w, mx, trump, hands, kitty, rest, [S, champ, S, champ], pre_scores=[0, 0])
        b0, b1 = _play_round(w, mx, trump, hands, kitty, rest, [champ, S, champ, S], pre_scores=[0, 0])
        diffs.append(((a0 - a1) + (b1 - b0)) / 2.0)   # challenger-minus-opp, avg over both seatings
    return diffs, S.stats

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--rounds', type=int, default=400)
    ap.add_argument('--worlds', type=int, default=16)
    ap.add_argument('--start-trick', type=int, default=3)
    ap.add_argument('--eps', type=float, default=0.0)
    ap.add_argument('--oracle-counts', action='store_true')
    ap.add_argument('--consistency', action='store_true')
    ap.add_argument('--cheat', action='store_true')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--seed-base', type=int, default=0)
    a = ap.parse_args()
    t0 = time.time(); chunk = max(1, a.rounds // (a.workers*4))
    tasks = [(a.seed_base+i, min(chunk, a.rounds-i), a.worlds, a.start_trick, a.eps, a.cheat, a.oracle_counts, a.consistency) for i in range(0, a.rounds, chunk)]
    with mp.Pool(a.workers) as pool:
        res = pool.map(_chunk, tasks)
    d = [x for r in res for x in r[0]]
    dec = sum(r[1]['decisions'] for r in res); dev = sum(r[1]['deviations'] for r in res)
    n = len(d); m = sum(d)/n
    sd = math.sqrt(sum((x-m)**2 for x in d)/(n-1)); se = sd/math.sqrt(n)
    print(f'rounds={n} worlds={a.worlds} start_trick={a.start_trick} eps={a.eps}')
    print(f'mean challenger-minus-opp round points: {m:+.3f}  SE {se:.3f}  z={m/se:+.2f}')
    print('acc/cand', sum(r[1].get('acc',0) for r in res), sum(r[1].get('cand',0) for r in res))
    print(f'sampled decisions={dec} deviations={dev} ({100*dev/max(1,dec):.1f}%)  elapsed {time.time()-t0:.0f}s')
