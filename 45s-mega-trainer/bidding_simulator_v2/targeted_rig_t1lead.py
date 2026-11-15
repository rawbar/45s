"""
targeted_rig_t1lead.py — Trick-1 lead strategy for bidders holding 5 of trump.

Tests leading low trump (t1lo) or high offsuit (t1off) vs leading the 5 of trump (champ)
when partner drew >=4 and opponents avg drew <4.

Tests four hand archetypes: 5only (no J, no AH), 5j (has J, no AH),
5ah (has AH, no J), 5j_ah (has both J and AH).

Usage:
  python -m bidding_simulator_v2.targeted_rig_t1lead
  python -m bidding_simulator_v2.targeted_rig_t1lead --deals 15000 --seed 42
  python -m bidding_simulator_v2.targeted_rig_t1lead --category 5only --deals 20000
"""

import sys, os, io, argparse, random, math, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from game_engine import Card, Suit, get_trump_rank, get_offsuit_rank
from bidding_simulator_v2.improved_ai import ImprovedAI, _is_trump
from bidding_simulator_v2.round_runner import play_round

HEARTS = Suit.HEARTS
ALL_SUITS = list(Suit)
ALL_RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
CATEGORIES = ['5only', '5j', '5ah', '5j_ah']


def _cid(c: Card) -> str:
    return c.rank + c.suit.value


def full_deck():
    return [Card(r, s) for s in Suit for r in ALL_RANKS]


# ─────────────────────────────────────────────────────────────────────────────
# Custom bidder AI: overrides trick-1 lead based on variant
# ─────────────────────────────────────────────────────────────────────────────

class T1BidderAI(ImprovedAI):
    """Bidder AI that preserves the manufactured hand and optionally overrides trick-1 lead."""

    def __init__(self, seat: int, lead_variant: str = 'champ'):
        super().__init__(seat)
        self.lead_variant = lead_variant

    def choose_discards(self, hand, trump, is_bid_winner, bid_amount, five_card_draw):
        # Always preserve the manufactured 5-card hand
        return []

    def choose_card(self, state, play_history):
        is_leading_t1 = (
            state.trick_num == 1
            and len(state.current_trick) == 0
            and state.trick_leader == self.player_idx
        )

        if is_leading_t1:
            hand = state.hands[self.player_idx]
            trump = state.trump_suit

            if self.lead_variant == 't1lo_trump':
                # Lead lowest trump that is NOT the 5, NOT the J of trump, NOT A♥
                candidates = [
                    c for c in hand
                    if _is_trump(c, trump)
                    and not (c.rank == '5' and c.suit == trump)
                    and not (c.rank == 'J' and c.suit == trump)
                    and not (c.rank == 'A' and c.suit == HEARTS)
                ]
                if candidates:
                    return min(candidates, key=lambda c: get_trump_rank(c, trump))
                # Fall through to champion if no candidates

            elif self.lead_variant == 't1off':
                # Lead highest non-trump card
                candidates = [c for c in hand if not _is_trump(c, trump)]
                if candidates:
                    return max(candidates, key=get_offsuit_rank)
                # Fall through to champion if no candidates

        # 'champ' or fallthrough: use normal champion AI
        return super().choose_card(state, play_history)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _zstat(p_chal, p_champ, n):
    if n == 0:
        return 0.0
    p_pool = (p_chal + p_champ) / 2
    if p_pool <= 0 or p_pool >= 1:
        return 0.0
    se = math.sqrt(p_pool * (1 - p_pool) * (2 / n))
    return (p_chal - p_champ) / se if se > 0 else 0.0


def compute_draw_count(hand, trump, seat, bid=20):
    """Simulate choose_discards to estimate how many cards this player will draw."""
    ai = ImprovedAI(seat)
    discards = ai.choose_discards(hand, trump, seat == 0, bid, False)
    kept = max(0, len(hand) - len(discards))
    return max(0, 5 - kept)


def build_bidder_hand(trump: Suit, category: str, rng: random.Random,
                      available_ids: set, all_cards_by_id: dict):
    """Build bidder hand for given category. Returns hand or None if not enough cards."""
    card_5  = Card('5', trump)
    card_J  = Card('J', trump)
    card_AH = Card('A', HEARTS)

    required = [card_5]
    if category in ('5j', '5j_ah'):
        required.append(card_J)
    if category in ('5ah', '5j_ah'):
        required.append(card_AH)

    # Check all required cards are available in the current deck
    for c in required:
        if _cid(c) not in available_ids:
            return None

    hand = list(required)
    used = {_cid(c) for c in required}

    # Pool: everything available except what's already placed and what's
    # category-forbidden (JT excluded for non-J categories; AH excluded for
    # non-AH categories; 5T always excluded).
    exclude_from_pool = {_cid(card_5)}
    if category not in ('5j', '5j_ah'):
        exclude_from_pool.add(_cid(card_J))   # don't allow J in non-J categories
    if category not in ('5ah', '5j_ah'):
        exclude_from_pool.add(_cid(card_AH))  # don't allow AH in non-AH categories
    exclude_from_pool.update(used)            # already-placed required cards

    pool = [
        c for c in all_cards_by_id.values()
        if _cid(c) in available_ids and _cid(c) not in exclude_from_pool
    ]

    needed = 5 - len(hand)
    if len(pool) < needed:
        return None
    hand.extend(rng.sample(pool, needed))
    return hand


# ─────────────────────────────────────────────────────────────────────────────
# Reporting helper
# ─────────────────────────────────────────────────────────────────────────────

def _row(label, acc, width=42):
    ch_m, ch_n = acc['champ']
    lo_m, lo_n = acc['t1lo']
    off_m, off_n = acc['t1off']
    if ch_n == 0:
        return
    ch_p  = ch_m  / ch_n
    lo_p  = lo_m  / lo_n  if lo_n  else 0.0
    off_p = off_m / off_n if off_n else 0.0
    dlo  = lo_p  - ch_p
    doff = off_p - ch_p
    zlo  = _zstat(lo_p,  ch_p, ch_n)
    zoff = _zstat(off_p, ch_p, ch_n)
    s_lo  = '**' if abs(zlo)  >= 2.0 else '  '
    s_off = '**' if abs(zoff) >= 2.0 else '  '
    print(
        f"  {label:<{width}}  n={ch_n:>5}  "
        f"champ={ch_p:.1%}  "
        f"t1lo={lo_p:.1%}({dlo:+.1%} z={zlo:+.1f}{s_lo})  "
        f"t1off={off_p:.1%}({doff:+.1%} z={zoff:+.1f}{s_off})"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Trump-count labels per category
# ─────────────────────────────────────────────────────────────────────────────

# For each category the minimum trump count possible in the hand:
#   5only  → min 1 (just the 5)
#   5j     → min 2 (5+J)
#   5ah    → min 2 (5+AH, AH is always trump)
#   5j_ah  → min 3 (5+J+AH)
CAT_MIN_TRUMP = {'5only': 1, '5j': 2, '5ah': 2, '5j_ah': 3}

def _trump_labels(category: str) -> dict:
    """Return {trump_count: label_string} for a given category."""
    if category == '5only':
        return {
            1: '1 trump (5 only)',
            2: '2 trump (5+1 low)',
            3: '3 trump (5+2 low)',
            4: '4 trump (5+3 low)',
            5: '5 trump (5+4 low)',
        }
    elif category == '5j':
        return {
            2: '2 trump (5+J only)',
            3: '3 trump (5+J+1 low)',
            4: '4 trump (5+J+2 low)',
            5: '5 trump (5+J+3 low)',
        }
    elif category == '5ah':
        return {
            2: '2 trump (5+AH only)',
            3: '3 trump (5+AH+1 low)',
            4: '4 trump (5+AH+2 low)',
            5: '5 trump (5+AH+3 low)',
        }
    else:  # 5j_ah
        return {
            3: '3 trump (5+J+AH only)',
            4: '4 trump (5+J+AH+1 low)',
            5: '5 trump (5+J+AH+2 low)',
        }


# ─────────────────────────────────────────────────────────────────────────────
# Main deal loop
# ─────────────────────────────────────────────────────────────────────────────

def run_deals(n_deals: int, seed: int, categories: list) -> dict:
    rng = random.Random(seed)
    deck_proto = full_deck()
    all_by_id = {_cid(c): c for c in deck_proto}

    def new_acc():
        return {v: [0, 0] for v in ('champ', 't1lo', 't1off')}

    # Per-category accumulators
    results = {}
    for cat in categories:
        results[cat] = {
            'overall':         new_acc(),
            'by_bidder_trump': {k: new_acc() for k in range(1, 6)},
            'by_opp_avg':      {'strong': new_acc(), 'moderate': new_acc()},
            'deals':           0,
            't0':              time.time(),
            'elapsed':         0.0,
        }

    deals_done_per_cat = {cat: 0 for cat in categories}
    total_progress = 0
    t0 = time.time()

    while any(deals_done_per_cat[cat] < n_deals for cat in categories):
        trump = rng.choice(ALL_SUITS)
        deck = deck_proto[:]
        rng.shuffle(deck)
        deck_ids = {_cid(c) for c in deck}

        for cat in categories:
            if deals_done_per_cat[cat] >= n_deals:
                continue

            hand = build_bidder_hand(trump, cat, rng, deck_ids, all_by_id)
            if hand is None:
                continue

            hand_ids = {_cid(c) for c in hand}
            remaining = [c for c in deck if _cid(c) not in hand_ids]
            rng.shuffle(remaining)

            h1, h2, h3 = remaining[:5], remaining[5:10], remaining[10:15]
            rest = remaining[15:]

            # Pre-compute draw counts
            # Seat 0 (bidder): T1BidderAI → always draws 0
            d1 = compute_draw_count(h1, trump, 1, bid=20)
            d2 = compute_draw_count(h2, trump, 2, bid=20)   # partner
            d3 = compute_draw_count(h3, trump, 3, bid=20)

            partner_drew = d2
            opps_avg = (d1 + d3) / 2.0

            # Filter: partner weak (drew 4-5), opponents moderate-to-strong (avg <4.0)
            if partner_drew < 4:
                continue
            if opps_avg >= 4.0:
                continue

            # Classify deal for breakdown accumulators
            bidder_trump_count = sum(1 for c in hand if _is_trump(c, trump))
            bidder_trump_key = min(bidder_trump_count, 5)

            if opps_avg < 3.0:
                opp_avg_key = 'strong'
            else:
                opp_avg_key = 'moderate'  # 3.0 <= avg < 4.0

            # Play 3 variants on the same hands
            base_hands = [hand[:], h1[:], h2[:], h3[:]]
            for variant, lead_v in [('champ', 'champ'), ('t1lo', 't1lo_trump'), ('t1off', 't1off')]:
                ai_players = [
                    T1BidderAI(0, lead_v),
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
                m = int(bool(made))

                r = results[cat]
                r['overall'][variant][0] += m
                r['overall'][variant][1] += 1

                r['by_bidder_trump'][bidder_trump_key][variant][0] += m
                r['by_bidder_trump'][bidder_trump_key][variant][1] += 1

                r['by_opp_avg'][opp_avg_key][variant][0] += m
                r['by_opp_avg'][opp_avg_key][variant][1] += 1

            deals_done_per_cat[cat] += 1
            total_progress += 1

            if total_progress % 1000 == 0:
                parts = []
                for c in categories:
                    n = deals_done_per_cat[c]
                    ch = results[c]['overall']['champ']
                    ch_r = ch[0] / max(1, ch[1])
                    parts.append(f"{c}:{n}/{n_deals}({ch_r:.1%})")
                elapsed = time.time() - t0
                print(f"  [{elapsed:.0f}s] {' | '.join(parts)}", flush=True)

    # Record elapsed per category
    total_elapsed = time.time() - t0
    for cat in categories:
        results[cat]['deals'] = deals_done_per_cat[cat]
        results[cat]['elapsed'] = total_elapsed  # shared wall time

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

def report_category(category: str, data: dict):
    n = data['deals']
    elapsed = data['elapsed']
    sep = '=' * 110

    print(f"\n{sep}")
    print(f"  CATEGORY: {category}   ({n:,} qualifying deals,  {elapsed:.0f}s)")
    print(f"  Filter: partner drew >=4 | opps avg drew <4")
    print(f"  Variants: champ=lead 5 of trump  |  t1lo=lead lowest non-5/J/AH trump  |  t1off=lead highest offsuit")
    print(sep)

    print(f"\n  OVERALL:")
    _row('all qualifying deals', data['overall'])

    labels = _trump_labels(category)
    print(f"\n  BY BIDDER TRUMP COUNT:")
    for k in sorted(labels.keys()):
        _row(labels[k], data['by_bidder_trump'][k])

    print(f"\n  BY OPPONENT STRENGTH:")
    _row('opps avg drew <3.0  (strong)', data['by_opp_avg']['strong'])
    _row('opps avg drew 3.0-<4.0 (mod)', data['by_opp_avg']['moderate'])


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='Trick-1 lead rig: all 5-of-trump hand archetypes, weak partner, stronger opponents'
    )
    ap.add_argument('--deals', type=int, default=10000,
                    help='Number of qualifying deals per category (default: 10000)')
    ap.add_argument('--seed',  type=int, default=0,
                    help='Random seed (default: 0)')
    ap.add_argument('--category', choices=CATEGORIES + ['all'], default='all',
                    help='Which hand category to test (default: all)')
    args = ap.parse_args()

    cats = CATEGORIES if args.category == 'all' else [args.category]

    print(f"\nTargeted trick-1 lead rig (5-of-trump archetypes)  |  "
          f"{args.deals:,} qualifying deals/category  |  seed={args.seed}")
    print(f"Categories: {', '.join(cats)}")
    print(f"Filter: partner_drew>=4 AND opps_avg_drew<4.0")

    results = run_deals(args.deals, seed=args.seed, categories=cats)

    for cat in cats:
        report_category(cat, results[cat])
    print()


if __name__ == '__main__':
    main()
