"""
test_sampler.py — constraint suite for mc_sampler.

A biased determinized sampler makes MC confidently wrong, so every sampled
world must provably satisfy: exact hand sizes, all knownVoids constraints,
sampled cards drawn only from the unseen pool, no duplicates, decider hand
fixed. Run: python -m bidding_simulator_v2.test_sampler
"""

import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from game_engine import Card, Suit, RANKS, get_trump_rank
from bidding_simulator_v2.mc_sampler import (
    sample_world, remaining_counts, _cid, _full_deck)


def _rand_state(rng):
    """Random legal-ish mid-round snapshot: deal 4×5, play 0..3 full tricks
    + a partial current trick, attach random plausible knownVoids."""
    trump = rng.choice(list(Suit))
    deck = _full_deck(); rng.shuffle(deck)
    hands = [deck[i*5:(i+1)*5][:] for i in range(4)]
    player = rng.randint(0, 3)
    completed = rng.randint(0, 3)
    play_history = []
    leader = 0
    for t in range(completed):
        for s in range(4):
            pi = (leader + s) % 4
            play_history.append((pi, hands[pi].pop()))
        leader = (leader + 1) % 4
    cur = []
    for s in range(rng.randint(0, 3)):
        pi = (leader + s) % 4
        if pi == player:
            break
        cur.append((pi, hands[pi].pop()))
    kv = [{}, {}, {}, {}]
    for i in range(4):
        if i == player:
            continue
        r = rng.random()
        if r < 0.20:
            kv[i]['trump'] = True
        elif r < 0.35:
            kv[i]['trump'] = 'reneging'
            kv[i]['possibleTrump'] = [f"5{trump.value}", "A♥"]
            kv[i]['noLowTrump'] = True
        if rng.random() < 0.30:
            kv[i][rng.choice(list(Suit)).value] = True
    return player, hands[player][:], play_history, cur, kv, trump, hands


def main():
    rng = random.Random(20260516)
    N = 4000
    bad = 0
    for t in range(N):
        player, myh, ph, cur, kv, trump, true_hands = _rand_state(rng)
        seen = {_cid(c) for c in myh} | {_cid(c) for (_, c) in ph} \
               | {_cid(c) for (_, c) in cur}
        pool_ids = {_cid(c) for c in _full_deck()} - seen
        counts = remaining_counts(player, myh, ph, cur)
        try:
            world = sample_world(player, myh, ph, cur, kv, trump,
                                 random.Random(rng.random()))
        except Exception as e:
            bad += 1;
            if bad <= 3: print("EXC", e)
            continue
        errs = []
        # decider hand fixed
        if [_cid(c) for c in world[player]] != [_cid(c) for c in myh]:
            errs.append("decider hand changed")
        allids = []
        for i in range(4):
            allids += [_cid(c) for c in world[i]]
        # no duplicates across all hands
        if len(allids) != len(set(allids)):
            errs.append("duplicate card across hands")
        for i in range(4):
            if i == player:
                continue
            if len(world[i]) != counts[i]:
                errs.append(f"size seat{i} {len(world[i])}!={counts[i]}")
            for c in world[i]:
                if _cid(c) not in pool_ids:
                    errs.append(f"seat{i} got non-pool {_cid(c)}")
                v = kv[i]
                ct = get_trump_rank(c, trump) >= 0
                vs = {k for k, val in v.items()
                      if k not in ('trump', 'possibleTrump', 'noLowTrump') and val is True}
                if c.suit.value in vs and not ct:
                    errs.append(f"seat{i} void-suit viol {_cid(c)}")
                if ct and v.get('trump') is True:
                    errs.append(f"seat{i} trump-void viol {_cid(c)}")
                if ct and v.get('trump') == 'reneging' \
                        and _cid(c) not in set(v.get('possibleTrump', [])):
                    errs.append(f"seat{i} reneging viol {_cid(c)}")
        if errs:
            bad += 1
            if bad <= 5:
                print(f"[{t}] FAIL:", errs[:4])
    print(f"\n{N - bad}/{N} worlds satisfied ALL constraints  "
          f"→ {'PASS' if bad == 0 else f'FAIL ({bad} bad)'}")


if __name__ == '__main__':
    main()
