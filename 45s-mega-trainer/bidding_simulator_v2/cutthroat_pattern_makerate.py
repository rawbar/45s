"""
cutthroat_pattern_makerate.py — per-hand-pattern bidding make-rate analyzer.

For each bid made in cutthroat games (all 4 seats = champion-cutthroat),
classifies the bidder's POST-DRAW hand into a coarse pattern bucket and
records (bid_amount, made T/F). Output: pattern × bid-level table sorted
by make-rate desc within each level.

Pattern classification (intentionally human-readable buckets, not a full
combinatorial fan-out):
  - top_anchors = subset of {5, J, AH, AT} that are in the hand
    (5 = 5-of-trump, J = J-of-trump, AH = A-hearts as trump,
    AT = A-of-trump (only if trump != hearts)).
  - trump_count = total trump in hand (post-kitty for bidder, post-draw
    for non-bidder).
  - off_high = 'K' if a non-trump K (or higher-ranked) is held; 'none' else.

Bucket name format: ANCHORS+TN[+offK]
  ANCHORS = '5J', '5JAH', '5JAHAT', '5J AH', '5+only', 'J', 'AH-only', etc.
            ordering 5,J,AH,AT (so '5JAH' = has 5+J+AH; 'J' = has only J; etc.)
  TN      = trump-count band:  T2 (=2), T3 (=3), T4 (=4), T5 (=5)
  +offK   = appended if hand has an offsuit K (non-trump K) — a junk-saver.

About a dozen relevant anchor combos × 4 trump-count bands = ~30 buckets;
sparse ones (n<5) are collapsed into "OTHER" within their bid level.

CLI:
  python -m bidding_simulator_v2.cutthroat_pattern_makerate \\
      --deals 2000 [--policy champion-cutthroat]

This tool is INFORMATIONAL — no ship gate.
"""

import sys, os, io, argparse, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace')

import multiprocessing as mp
from multiprocessing import Pool
from collections import defaultdict

from typing import List, Dict
from game_engine import Deck, Suit, is_trump
from bidding_simulator_v2.bidding import find_best_trump_suit
from bidding_simulator_v2.game_runner import _play_round, MAX_ROUNDS
from bidding_simulator_v2.challengers import REGISTRY
from bidding_simulator_v2 import bidding as bidlib


HEARTS = Suit.HEARTS


def classify_hand(hand, trump: Suit) -> str:
    """Return bucket name for this post-discard/draw bidder hand."""
    h5 = bidlib.has_five(hand, trump)
    hj = bidlib.has_jack(hand, trump)
    hah = bidlib.has_ace_hearts(hand)
    hat = bidlib.has_ace_trump(hand, trump)
    tc = bidlib.count_trumps(hand, trump)
    # offsuit K (non-trump K): note A-hearts is trump always so won't appear
    # as offsuit-A.
    off_k = any(c.rank == 'K' and not is_trump(c, trump) for c in hand)
    off_a = any(c.rank == 'A' and not is_trump(c, trump) for c in hand)
    anchors = []
    if h5: anchors.append('5')
    if hj: anchors.append('J')
    if hah: anchors.append('AH')
    if hat: anchors.append('AT')
    anc = ''.join(anchors) if anchors else 'none'
    name = f"{anc}+T{tc}"
    # Append offsuit extras (visible high cards that affect makeability):
    if off_a:
        name += '+oA'
    elif off_k:
        name += '+oK'
    return name


def play_game_cutthroat_recorded(seat_policy, seed, start_dealer, records):
    """Like cutthroat_runner.play_game_cutthroat but appends to `records`
    a tuple (pattern, bid_amount, made_bool) for every made bid (the
    auction winner's hand POST-discard-draw, evaluated by the actual
    round outcome). Records-only; no need to return the game result."""
    rng = random.Random(seed)
    scores = [0, 0, 0, 0]
    dealer = start_dealer
    rounds = 0

    while max(scores) < 120 and rounds < MAX_ROUNDS:
        rounds += 1
        d = Deck()
        rng.shuffle(d.cards)
        hands = [d.deal(5) for _ in range(4)]
        kitty = d.deal(3)
        rest = d.cards[:]

        bids = [None, None, None, None]
        suits = [None, None, None, None]
        high_bid = 0
        order = [(dealer + 1) % 4, (dealer + 2) % 4, (dealer + 3) % 4, dealer]
        for p in order:
            ts = scores[p]
            os_ = max(scores[(p + 1) % 4], scores[(p + 2) % 4],
                       scores[(p + 3) % 4])
            b, s = seat_policy[p].decide_bid(hands[p], high_bid, p, dealer,
                                              ts, os_, 0)
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

        # Build the bidder's POST-kitty-pre-discard hand for pattern. We
        # want the post-discard-and-draw hand actually played. Simulate
        # the discard the bidder would do here (the simulator does this
        # too inside _play_round, but the simulator doesn't expose the
        # post-discard hand). Easiest: do the same discard logic now,
        # classify, then run _play_round (which redoes it internally —
        # deterministic given the same hand+kitty+rest, so equivalent).
        from bidding_simulator_v2.improved_ai import ImprovedAI
        b_hand = hands[winner] + kitty
        b_ai_flags = seat_policy[winner]._effective_ai_flags() \
            if hasattr(seat_policy[winner], '_effective_ai_flags') else None
        b_ai = ImprovedAI(winner, b_ai_flags)
        discards = b_ai.choose_discards(b_hand, trump, True, max_b, False)
        b_hand2 = [c for c in b_hand if c not in discards]
        # post-draw: bidder draws back up to 5; the drawn cards may add
        # extras but we want to evaluate the BIDDER'S DECISION hand =
        # the cards the bidder ACTUALLY plays. So include the draw too.
        # Approximate: peel the same `rest` order the _play_round uses.
        # _play_round draws in seat order (0..3), so the bidder's draws
        # depend on what 0..winner-1 took. We just simulate:
        deck_for_draw = rest[:]
        # Simulate discard-then-draw in seat order (matches _play_round).
        sim_hands = [h[:] for h in hands]
        sim_hands[winner] = b_hand2
        for i in range(4):
            if i != winner:
                disc_i = seat_policy[i].choose_discards(
                    sim_hands[i], trump, False, max_b
                )
                for c in disc_i:
                    if c in sim_hands[i]:
                        sim_hands[i].remove(c)
            nd = max(0, 5 - len(sim_hands[i]))
            for _ in range(nd):
                if deck_for_draw:
                    sim_hands[i].append(deck_for_draw.pop())
        final_bidder_hand = sim_hands[winner]
        pattern = classify_hand(final_bidder_hand, trump)

        _t0, _t1, per_player = _play_round(
            winner, max_b, trump, hands, kitty, rest, seat_policy,
            pre_scores=scores[:], return_per_player=True,
            pre_round_scores=scores[:],
        )
        bidder_pts = per_player[winner]
        made = bidder_pts >= max_b

        # Apply scoring for the next round's score-aware AI rules
        for p in range(4):
            if p == winner:
                scores[p] += bidder_pts if made else (
                    -2 * max_b if max_b == 30 else -max_b)
            else:
                scores[p] += per_player[p]

        records.append((pattern, max_b, made))
        if max(scores) >= 120:
            break
        dealer = (dealer + 1) % 4


_POLICY_NAME = None
_SEED_BASE = 0


def _init(name, seed_base=0):
    global _POLICY_NAME, _SEED_BASE
    _POLICY_NAME = name
    _SEED_BASE = seed_base


def _run_chunk(args):
    start, count = args
    pol = REGISTRY[_POLICY_NAME]
    seat_pol = [pol, pol, pol, pol]
    records = []
    for i in range(start, start + count):
        seed = _SEED_BASE + i
        dealer = i % 4
        play_game_cutthroat_recorded(seat_pol, seed, dealer, records)
    return records


def aggregate(records):
    """records → {bid_level: {pattern: [n_bids, n_made]}}"""
    out = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for (pat, lvl, made) in records:
        slot = out[lvl][pat]
        slot[0] += 1
        if made:
            slot[1] += 1
    return out


def print_table(agg, min_n=3):
    """Print one table per bid level, patterns sorted by make-rate desc.
    Buckets with n < min_n collapsed into OTHER."""
    W = 70
    for lvl in (15, 20, 25, 30):
        if lvl not in agg:
            continue
        rows = []
        other_n = other_m = 0
        for pat, (n, m) in agg[lvl].items():
            if n < min_n:
                other_n += n
                other_m += m
                continue
            rows.append((pat, n, m, m / n if n else 0.0))
        if other_n > 0:
            rows.append(('OTHER (n<%d combined)' % min_n,
                         other_n, other_m,
                         other_m / other_n if other_n else 0.0))
        rows.sort(key=lambda r: (-r[3], -r[1]))
        tot_n = sum(r[1] for r in rows)
        tot_m = sum(r[2] for r in rows)
        tot_r = tot_m / tot_n if tot_n else 0.0
        print()
        print('=' * W)
        print(f'  BIDS OF {lvl}   (n_bids={tot_n:,}   make-rate={tot_r*100:5.2f}%)')
        print('=' * W)
        print(f'  {"pattern":<26}  {"n":>6}  {"made":>6}  {"rate":>6}')
        print('-' * W)
        for (pat, n, m, r) in rows:
            print(f'  {pat:<26}  {n:>6,}  {m:>6,}  {r*100:>5.1f}%')


def main():
    ap = argparse.ArgumentParser(
        description='Per-hand-pattern bidding make-rate analyzer '
                    '(cutthroat, all-4-seats same policy).'
    )
    ap.add_argument('--deals', type=int, default=2000,
                    help='deals to simulate (each runs a full game to 120)')
    ap.add_argument('--policy', default='champion-cutthroat',
                    choices=sorted(REGISTRY),
                    help='policy to place at all 4 seats')
    ap.add_argument('--workers', type=int, default=mp.cpu_count())
    ap.add_argument('--seed-base', type=int, default=0)
    ap.add_argument('--min-n', type=int, default=3,
                    help='collapse buckets with fewer than this many bids '
                         'into OTHER')
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

    W = 70
    print('\n' + '=' * W)
    print(f'  PATTERN MAKE-RATE — policy {args.policy}')
    print(f'  deals: {args.deals:,}   workers: {args.workers}   '
          f'seed-base: {args.seed_base}')
    print('=' * W)
    t0 = time.time()

    all_records = []
    with Pool(args.workers, initializer=_init,
              initargs=(args.policy, args.seed_base)) as pool:
        done = 0
        for recs in pool.imap_unordered(_run_chunk, tasks):
            all_records.extend(recs)
            done += 1
            print(f'\r  chunks {done}/{len(tasks)}  '
                  f'records: {len(all_records):,}', end='', flush=True)
    el = time.time() - t0
    print(f'\n  elapsed {el:.0f}s   total bids: {len(all_records):,}')

    agg = aggregate(all_records)
    print_table(agg, min_n=args.min_n)
    print()


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)
    main()
