"""
targeted_rig_wp.py — Trick-1 lead strategy: weak partner (drew 4-5), stronger opponents (avg drew <4).

Tests whether leading low trump or high offsuit on trick 1 is better than leading the 5
when: bidder holds 5+J (any total trump), partner drew >=4, opponents avg drew <4.

Usage:
  python -m bidding_simulator_v2.targeted_rig_wp
  python -m bidding_simulator_v2.targeted_rig_wp --deals 20000 --seed 42
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


def build_bidder_hand(trump: Suit, rng: random.Random,
                      available_ids: set, all_cards_by_id: dict):
    """Build bidder hand: 5T + JT + 3 random other cards (any mix of low trump/offsuit)."""
    card_5 = Card('5', trump)
    card_J = Card('J', trump)
    hand = [card_5, card_J]
    used = {_cid(card_5), _cid(card_J)}

    # Pool: anything not already used, not 5T, not JT, not A♥ (A♥ is always trump — ok to
    # include, but exclude the fixed trump anchors we already placed)
    pool = [
        c for c in all_cards_by_id.values()
        if _cid(c) in available_ids
        and _cid(c) not in used
    ]
    if len(pool) < 3:
        return None

    hand.extend(rng.sample(pool, 3))
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
# Main deal loop
# ─────────────────────────────────────────────────────────────────────────────

def run_deals(n_deals: int, seed: int) -> dict:
    rng = random.Random(seed)
    deck_proto = full_deck()
    all_by_id = {_cid(c): c for c in deck_proto}

    def new_acc():
        return {v: [0, 0] for v in ('champ', 't1lo', 't1off')}

    overall    = new_acc()
    # by_bidder_trump: how many trump cards total in bidder's manufactured hand
    # possible values: 2 (5+J only), 3, 4, 5
    by_bidder_trump = {k: new_acc() for k in (2, 3, 4, 5)}
    # by_partner_drew: partner drew exactly 4 vs exactly 5
    by_partner_drew = {4: new_acc(), 5: new_acc()}
    # by_opp_avg: opp avg <3.0 (strong) vs 3.0-<4.0 (moderate)
    by_opp_avg = {'strong': new_acc(), 'moderate': new_acc()}

    deals_done = 0
    t0 = time.time()

    while deals_done < n_deals:
        trump = rng.choice(ALL_SUITS)
        deck = deck_proto[:]
        rng.shuffle(deck)
        deck_ids = {_cid(c) for c in deck}

        hand = build_bidder_hand(trump, rng, deck_ids, all_by_id)
        if hand is None:
            continue

        hand_ids = {_cid(c) for c in hand}
        remaining = [c for c in deck if _cid(c) not in hand_ids]
        rng.shuffle(remaining)

        h1, h2, h3 = remaining[:5], remaining[5:10], remaining[10:15]
        rest = remaining[15:]
        base_hands = [hand[:], h1[:], h2[:], h3[:]]

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
        bidder_trump_key = min(bidder_trump_count, 5)  # clamp to 5 max

        partner_drew_key = min(partner_drew, 5)  # 4 or 5

        if opps_avg < 3.0:
            opp_avg_key = 'strong'
        else:
            opp_avg_key = 'moderate'  # 3.0 <= avg < 4.0

        # Play 3 variants on the same hands
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

            overall[variant][0] += m
            overall[variant][1] += 1

            by_bidder_trump[bidder_trump_key][variant][0] += m
            by_bidder_trump[bidder_trump_key][variant][1] += 1

            by_partner_drew[partner_drew_key][variant][0] += m
            by_partner_drew[partner_drew_key][variant][1] += 1

            by_opp_avg[opp_avg_key][variant][0] += m
            by_opp_avg[opp_avg_key][variant][1] += 1

        deals_done += 1
        if deals_done % 1000 == 0:
            pct = 100 * deals_done // n_deals
            ch_r  = overall['champ'][0]  / max(1, overall['champ'][1])
            lo_r  = overall['t1lo'][0]   / max(1, overall['t1lo'][1])
            off_r = overall['t1off'][0]  / max(1, overall['t1off'][1])
            print(
                f"  {deals_done:,}/{n_deals:,} ({pct}%)  "
                f"champ={ch_r:.1%}  t1lo={lo_r:.1%}  t1off={off_r:.1%}",
                flush=True
            )

    elapsed = time.time() - t0
    return {
        'overall':          overall,
        'by_bidder_trump':  by_bidder_trump,
        'by_partner_drew':  by_partner_drew,
        'by_opp_avg':       by_opp_avg,
        'elapsed':          elapsed,
        'deals':            deals_done,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

def report(data: dict):
    elapsed = data['elapsed']
    print(f"\n{'='*110}")
    print(f"  WEAK PARTNER RIG (partner drew >=4, opps avg drew <4)   "
          f"({data['deals']:,} deals,  {elapsed:.0f}s)")
    print(f"  Variants:  champ = lead 5 of trump  |  t1lo = lead lowest non-5/J/AH trump  |  "
          f"t1off = lead highest offsuit")
    print(f"{'='*110}")

    print(f"\n  OVERALL:")
    _row('all qualifying deals', data['overall'])

    print(f"\n  BY BIDDER TRUMP COUNT (total trump in bidder's 5-card hand):")
    for k in (2, 3, 4, 5):
        label = {2: '2 trump (5+J only)',
                 3: '3 trump (5+J+1 low)',
                 4: '4 trump (5+J+2 low)',
                 5: '5 trump (5+J+3 low)'}[k]
        _row(label, data['by_bidder_trump'][k])

    print(f"\n  BY PARTNER DRAW COUNT:")
    for k, label in [(4, 'partner drew exactly 4 (kept 1)'),
                     (5, 'partner drew exactly 5 (kept 0)')]:
        _row(label, data['by_partner_drew'][k])

    print(f"\n  BY OPPONENT AVERAGE DRAW COUNT:")
    for k, label in [('strong',   'opps avg drew <3.0  (strong)'),
                     ('moderate', 'opps avg drew 3.0-<4.0 (moderate)')]:
        _row(label, data['by_opp_avg'][k])

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='Trick-1 lead rig: weak partner, stronger opponents'
    )
    ap.add_argument('--deals', type=int, default=10000,
                    help='Number of qualifying deals to run (default: 10000)')
    ap.add_argument('--seed',  type=int, default=0,
                    help='Random seed (default: 0)')
    args = ap.parse_args()

    print(f"\nTargeted weak-partner trick-1 lead rig  |  "
          f"{args.deals:,} qualifying deals  |  seed={args.seed}")

    data = run_deals(args.deals, seed=args.seed)
    report(data)


if __name__ == '__main__':
    main()
