"""
targeted_rig_5j3.py — Targeted bid-make-rate test for bidder 5+J ≤3 trump trick-1 lead.

Manufactures the bidder's 5-card hand for each deal (bypasses bidding/discard),
then plays the round 3 ways on the same opponent cards:
  t1lo   — challenger: lead lowest offsuit trick 1
  t1hi   — challenger: lead highest offsuit trick 1
  champ  — champion: lead 5 of trump trick 1 (baseline)

Three hand categories:
  5j-only : [5T, JT] + 3 random non-trump non-AH cards
  5j+1    : [5T, JT] + 1 random low trump (not 5/J/AH) + 2 non-trump cards
  5j+2    : [5T, JT] + 2 random low trumps (not 5/J/AH) + 1 non-trump card

Results are stratified by:
  - Partner (seat 2) draw count: strong (drew 0-1), moderate (drew 2-3), weak (drew 4-5)
  - Avg opponent (seats 1,3) draw count: strong (<3 avg), weak (>=3 avg)

The bidder is always seat 0, bid = 20, trump = random suit each deal.
Opponent hands are randomly dealt; opponents use champion AI with normal discard/draw.

Usage:
  python -m bidding_simulator_v2.targeted_rig_5j3
  python -m bidding_simulator_v2.targeted_rig_5j3 --deals 10000 --seed 42
  python -m bidding_simulator_v2.targeted_rig_5j3 --category 5j-only --deals 5000
"""

import sys, os, io, argparse, random, math, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from game_engine import Card, Suit
from bidding_simulator_v2.improved_ai import ImprovedAI, _is_trump
from bidding_simulator_v2.round_runner import play_round

HEARTS = Suit.HEARTS
ALL_SUITS = list(Suit)
ALL_RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
CATEGORIES = ['5j-only', '5j+1', '5j+2']

# Partner draw buckets
PARTNER_BUCKETS = [
    ('p_drew_01', 'partner drew 0-1  (strong, kept 4-5)',  lambda d: d <= 1),
    ('p_drew_2',  'partner drew 2     (moderate, kept 3)',  lambda d: d == 2),
    ('p_drew_3',  'partner drew 3     (moderate, kept 2)',  lambda d: d == 3),
    ('p_drew_4p', 'partner drew 4-5  (weak, kept 0-1)',    lambda d: d >= 4),
]

# Opponent strength buckets (avg of opp1+opp2 draw counts)
OPP_BUCKETS = [
    ('opps_strong', 'opps avg drew <3  (strong)', lambda a: a < 3.0),
    ('opps_weak',   'opps avg drew >=3 (weak)',   lambda a: a >= 3.0),
]


def _cid(c: Card) -> str:
    return c.rank + c.suit.value


def full_deck():
    return [Card(r, s) for s in Suit for r in ALL_RANKS]


class FixedHandAI(ImprovedAI):
    """Bidder AI that never discards — preserves the manufactured 5-card hand."""
    def choose_discards(self, hand, trump, is_bid_winner, bid_amount, five_card_draw):
        return []


def _wilson_ci(wins, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return p, centre - half, centre + half


def _zstat(p_chal, p_champ, n):
    if n == 0:
        return 0.0
    p_pool = (p_chal + p_champ) / 2
    if p_pool <= 0 or p_pool >= 1:
        return 0.0
    se = math.sqrt(p_pool * (1 - p_pool) * (2 / n))
    return (p_chal - p_champ) / se if se > 0 else 0.0


def build_bidder_hand(trump: Suit, category: str, rng: random.Random,
                      available_ids: set, all_cards_by_id: dict):
    card_5 = Card('5', trump)
    card_J = Card('J', trump)
    hand = [card_5, card_J]
    used = {_cid(card_5), _cid(card_J)}

    low_trump_pool = [
        c for c in all_cards_by_id.values()
        if _is_trump(c, trump)
        and c.rank != '5'
        and not (c.rank == 'J' and c.suit == trump)
        and not (c.rank == 'A' and c.suit == HEARTS)
        and _cid(c) in available_ids
        and _cid(c) not in used
    ]
    offsuit_pool = [
        c for c in all_cards_by_id.values()
        if not _is_trump(c, trump)
        and not (c.rank == 'A' and c.suit == HEARTS)
        and _cid(c) in available_ids
        and _cid(c) not in used
    ]

    extra_trump_count = {'5j-only': 0, '5j+1': 1, '5j+2': 2}[category]
    if len(low_trump_pool) < extra_trump_count:
        return None
    if extra_trump_count > 0:
        chosen_extra = rng.sample(low_trump_pool, extra_trump_count)
        hand.extend(chosen_extra)
        for c in chosen_extra:
            used.add(_cid(c))

    offsuit_needed = 5 - len(hand)
    if len(offsuit_pool) < offsuit_needed:
        return None
    hand.extend(rng.sample(offsuit_pool, offsuit_needed))
    return hand


def compute_draw_count(hand, trump, seat, bid=20):
    """Simulate choose_discards to estimate how many cards this player will draw."""
    ai = ImprovedAI(seat)
    discards = ai.choose_discards(hand, trump, seat == 0, bid, False)
    kept = max(0, len(hand) - len(discards))
    return max(0, 5 - kept)


def run_deals(category: str, n_deals: int, seed: int) -> dict:
    rng = random.Random(seed)
    deck_proto = full_deck()
    all_by_id = {_cid(c): c for c in deck_proto}

    # Accumulators: overall + per-partner-bucket + per-opp-bucket
    # Each entry: {'lo': [makes, total], 'hi': [...], 'champ': [...]}
    def new_acc():
        return {v: [0, 0] for v in ('lo', 'hi', 'champ')}

    overall = new_acc()
    by_partner = {bk: new_acc() for bk, _, _ in PARTNER_BUCKETS}
    by_opp = {bk: new_acc() for bk, _, _ in OPP_BUCKETS}
    # 2D: partner bucket × opp bucket
    by_p_o = {(pb, ob): new_acc()
               for pb, _, _ in PARTNER_BUCKETS
               for ob, _, _ in OPP_BUCKETS}

    deals_done = 0
    t0 = time.time()

    while deals_done < n_deals:
        trump = rng.choice(ALL_SUITS)
        deck = deck_proto[:]
        rng.shuffle(deck)
        deck_ids = {_cid(c) for c in deck}

        hand = build_bidder_hand(trump, category, rng, deck_ids, all_by_id)
        if hand is None:
            continue

        hand_ids = {_cid(c) for c in hand}
        remaining = [c for c in deck if _cid(c) not in hand_ids]
        rng.shuffle(remaining)

        h1, h2, h3 = remaining[:5], remaining[5:10], remaining[10:15]
        rest = remaining[15:]
        base_hands = [hand[:], h1[:], h2[:], h3[:]]

        # Pre-compute draw counts (same logic play_round will use)
        # Seat 0 (bidder): FixedHandAI → always draws 0
        d0 = 0
        d1 = compute_draw_count(h1, trump, 1, bid=20)
        d2 = compute_draw_count(h2, trump, 2, bid=20)   # partner
        d3 = compute_draw_count(h3, trump, 3, bid=20)

        partner_drew = d2
        opps_avg = (d1 + d3) / 2.0

        # Identify which buckets this deal falls into
        pbk = next(k for k, _, fn in PARTNER_BUCKETS if fn(partner_drew))
        obk = next(k for k, _, fn in OPP_BUCKETS if fn(opps_avg))

        # Play 3 variants
        for variant, flags in [('lo', {'bidder_5j_t3_off_t1lo': True}),
                                ('hi', {'bidder_5j_t3_off_t1hi': True}),
                                ('champ', {})]:
            ai_players = [
                FixedHandAI(0, flags),
                ImprovedAI(1),
                ImprovedAI(2),
                ImprovedAI(3),
            ]
            made, _, _ = play_round(
                bid=20,
                trump_suit=trump,
                hands=[h[:] for h in base_hands],
                kitty=[],
                remaining_deck=rest[:],
                ai_players=ai_players,
            )
            m = int(made)
            overall[variant][0] += m;   overall[variant][1] += 1
            by_partner[pbk][variant][0] += m; by_partner[pbk][variant][1] += 1
            by_opp[obk][variant][0] += m;     by_opp[obk][variant][1] += 1
            by_p_o[(pbk, obk)][variant][0] += m
            by_p_o[(pbk, obk)][variant][1] += 1

        deals_done += 1
        if deals_done % 2000 == 0:
            pct = 100 * deals_done // n_deals
            lo_r = overall['lo'][0] / max(1, overall['lo'][1])
            ch_r = overall['champ'][0] / max(1, overall['champ'][1])
            print(f"  {deals_done:,}/{n_deals:,} ({pct}%)  "
                  f"t1lo={lo_r:.1%}  champ={ch_r:.1%}", flush=True)

    elapsed = time.time() - t0
    return {'overall': overall, 'by_partner': by_partner, 'by_opp': by_opp,
            'by_p_o': by_p_o, 'elapsed': elapsed, 'deals': deals_done}


def _row(label, acc, width=42):
    lo_m, lo_n = acc['lo']
    hi_m, hi_n = acc['hi']
    ch_m, ch_n = acc['champ']
    if ch_n == 0:
        return
    ch_p = ch_m / ch_n
    lo_p = lo_m / lo_n if lo_n else 0.0
    hi_p = hi_m / hi_n if hi_n else 0.0
    dlo = lo_p - ch_p
    dhi = hi_p - ch_p
    zlo = _zstat(lo_p, ch_p, ch_n)
    zhi = _zstat(hi_p, ch_p, hi_n)
    s_lo = '**' if abs(zlo) >= 2 else '  '
    s_hi = '**' if abs(zhi) >= 2 else '  '
    print(f"  {label:<{width}}  n={ch_n:>5}  "
          f"champ={ch_p:.1%}  "
          f"t1lo={lo_p:.1%}({dlo:+.1%} z={zlo:+.1f}{s_lo})  "
          f"t1hi={hi_p:.1%}({dhi:+.1%} z={zhi:+.1f}{s_hi})")


def report_category(category: str, data: dict):
    elapsed = data['elapsed']
    print(f"\n{'='*100}")
    print(f"  CATEGORY: {category}   ({data['deals']:,} deals,  {elapsed:.0f}s)")
    print(f"{'='*100}")

    print(f"\n  OVERALL:")
    _row('all deals', data['overall'])

    print(f"\n  BY PARTNER DRAW COUNT:  (partner = seat 2 / bidder's partner)")
    for bk, label, _ in PARTNER_BUCKETS:
        _row(label, data['by_partner'][bk])

    print(f"\n  BY OPPONENT STRENGTH:  (avg draw count of seats 1+3)")
    for bk, label, _ in OPP_BUCKETS:
        _row(label, data['by_opp'][bk])

    print(f"\n  2D: PARTNER × OPPONENTS:")
    for pb, plabel, _ in PARTNER_BUCKETS:
        for ob, olabel, _ in OPP_BUCKETS:
            bk = (pb, ob)
            acc = data['by_p_o'][bk]
            if acc['champ'][1] >= 20:
                _row(f"{plabel[:26]} | {olabel[:18]}", acc, width=48)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--deals', type=int, default=5000)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--category', choices=CATEGORIES + ['all'], default='all')
    args = ap.parse_args()

    cats = CATEGORIES if args.category == 'all' else [args.category]
    print(f"\nTargeted 5J trick-1 lead rig (stratified)  |  "
          f"{args.deals:,} deals/category  |  seed={args.seed}")

    for i, cat in enumerate(cats):
        data = run_deals(cat, args.deals, seed=args.seed + i * 999983)
        report_category(cat, data)
    print()


if __name__ == '__main__':
    main()
