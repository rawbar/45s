"""
cutthroat_bid_rig.py — Make-rate for fixed trump-composition hands bidding 15.

Bidder holds a FIXED manufactured hand (no discard/draw).
Opponents deal 5 random cards and draw normally per ImprovedAI.

Tests four anchor families across all trump-count sub-categories:
  J  family: J alone, J+1lo, J+2lo, J+3lo, J+4lo        (no 5T, no AH)
  AH family: AH alone, AH+1lo, AH+2lo, AH+3lo           (no 5T, no JT)
  5  family: 5 alone, 5+1lo, 5+2lo                       (no JT, no AH)  [ref]
  5J family: 5+J, 5+J+1lo, 5+J+2lo                      [ref]

z-stat vs 50% (EV breakeven for bidding):
  ** = |z| >= 2.0  (significantly above or below 50%)

Usage:
  python -m bidding_simulator_v2.cutthroat_bid_rig
  python -m bidding_simulator_v2.cutthroat_bid_rig --deals 20000 --seed 42
"""

import sys, os, io, argparse, random, math, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from game_engine import Card, Suit, get_trump_rank, get_offsuit_rank
from bidding_simulator_v2.improved_ai import ImprovedAI, _is_trump
from bidding_simulator_v2.round_runner import play_round
from bidding_simulator_v2.challengers import CHAMPION_CUTTHROAT

# Cutthroat champion flags (c1 take-from-bidder + c2 dont-overtake + cutthroat=True)
_CT_FLAGS = CHAMPION_CUTTHROAT._effective_ai_flags()

HEARTS = Suit.HEARTS
ALL_SUITS = list(Suit)
ALL_RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _cid(c: Card) -> str:
    return c.rank + c.suit.value


def full_deck():
    return [Card(r, s) for s in Suit for r in ALL_RANKS]


class FixedHandCTBidderAI(ImprovedAI):
    """Bidder keeps manufactured hand — no discards. Uses cutthroat card-play logic."""
    def __init__(self, seat: int):
        super().__init__(seat, _CT_FLAGS)

    def choose_discards(self, hand, trump, is_bid_winner, bid_amount, five_card_draw):
        return []


def make_ct_opponent(seat: int) -> ImprovedAI:
    """Create a cutthroat-champion opponent (c1 + c2 flags on)."""
    return ImprovedAI(seat, _CT_FLAGS)


def _is_low_trump(c: Card, trump: Suit) -> bool:
    """True iff c is trump but NOT 5T, JT, or A♥."""
    if not _is_trump(c, trump):
        return False
    if c.rank == '5' and c.suit == trump:
        return False
    if c.rank == 'J' and c.suit == trump:
        return False
    if c.rank == 'A' and c.suit == HEARTS:
        return False
    return True


def anchor_card(spec: str, trump: Suit) -> Card:
    if spec == '5T':  return Card('5', trump)
    if spec == 'JT':  return Card('J', trump)
    if spec == 'AH':  return Card('A', HEARTS)
    raise ValueError(f"Unknown anchor spec: {spec}")


# ─────────────────────────────────────────────────────────────────────────────
# Category definitions
# ─────────────────────────────────────────────────────────────────────────────

CATS = [
    # ── J family (no 5T, no AH) ──────────────────────────────────────────────
    {'key': 'j0',  'anchors': ['JT'],        'low': 0, 'label': 'J              (1T)'},
    {'key': 'j1',  'anchors': ['JT'],        'low': 1, 'label': 'J + 1 low      (2T)'},
    {'key': 'j2',  'anchors': ['JT'],        'low': 2, 'label': 'J + 2 low      (3T)'},
    {'key': 'j3',  'anchors': ['JT'],        'low': 3, 'label': 'J + 3 low      (4T)'},
    {'key': 'j4',  'anchors': ['JT'],        'low': 4, 'label': 'J + 4 low      (5T)'},
    # ── AH family (no 5T, no JT) ─────────────────────────────────────────────
    {'key': 'ah0', 'anchors': ['AH'],        'low': 0, 'label': 'AH             (1T)'},
    {'key': 'ah1', 'anchors': ['AH'],        'low': 1, 'label': 'AH + 1 low     (2T)'},
    {'key': 'ah2', 'anchors': ['AH'],        'low': 2, 'label': 'AH + 2 low     (3T)'},
    {'key': 'ah3', 'anchors': ['AH'],        'low': 3, 'label': 'AH + 3 low     (4T)'},
    # ── 5 family (no JT, no AH) — reference baseline ────────────────────────
    {'key': '5x0', 'anchors': ['5T'],        'low': 0, 'label': '5              (1T)'},
    {'key': '5x1', 'anchors': ['5T'],        'low': 1, 'label': '5 + 1 low      (2T)'},
    {'key': '5x2', 'anchors': ['5T'],        'low': 2, 'label': '5 + 2 low      (3T)'},
    # ── 5+J family — reference ───────────────────────────────────────────────
    {'key': '5j0', 'anchors': ['5T', 'JT'],  'low': 0, 'label': '5 + J          (2T)'},
    {'key': '5j1', 'anchors': ['5T', 'JT'],  'low': 1, 'label': '5 + J + 1 low  (3T)'},
    {'key': '5j2', 'anchors': ['5T', 'JT'],  'low': 2, 'label': '5 + J + 2 low  (4T)'},
]

CAT_LABEL = {c['key']: c['label'] for c in CATS}

GROUPS = [
    ('J family  (no 5, no AH)',     ['j0', 'j1', 'j2', 'j3', 'j4']),
    ('AH family (no 5, no J)',      ['ah0', 'ah1', 'ah2', 'ah3']),
    ('5  family (no J, no AH) REF', ['5x0', '5x1', '5x2']),
    ('5+J family             REF',  ['5j0', '5j1', '5j2']),
]


# ─────────────────────────────────────────────────────────────────────────────
# Hand builder
# ─────────────────────────────────────────────────────────────────────────────

def build_hand(cat: dict, trump: Suit, rng: random.Random,
               available_ids: set, all_by_id: dict):
    """Build a 5-card bidder hand for the given category. Returns None if impossible."""
    hand, used = [], set()

    # Place anchor cards
    for spec in cat['anchors']:
        c = anchor_card(spec, trump)
        cid = _cid(c)
        if cid not in available_ids:
            return None
        if cid in used:
            continue  # duplicate anchor (e.g. 5T=AH when trump=hearts edge case)
        hand.append(c)
        used.add(cid)

    # Add low trump fillers
    n_low = cat['low']
    if n_low:
        pool = [c for c in all_by_id.values()
                if _cid(c) in available_ids
                and _cid(c) not in used
                and _is_low_trump(c, trump)]
        if len(pool) < n_low:
            return None
        chosen = rng.sample(pool, n_low)
        hand.extend(chosen)
        used.update(_cid(c) for c in chosen)

    # Fill remainder with offsuit cards (never trump)
    n_off = 5 - len(hand)
    if n_off:
        pool = [c for c in all_by_id.values()
                if _cid(c) in available_ids
                and _cid(c) not in used
                and not _is_trump(c, trump)]
        if len(pool) < n_off:
            return None
        hand.extend(rng.sample(pool, n_off))

    return hand


# ─────────────────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────────────────

def _z50(made: int, n: int) -> float:
    """z-stat vs 50% make rate (EV-breakeven for bidding)."""
    if n == 0:
        return 0.0
    p = made / n
    se = math.sqrt(0.25 / n)
    return (p - 0.5) / se if se > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────

def run_deals(n_per_cat: int, seed: int) -> tuple:
    rng = random.Random(seed)
    deck_proto = full_deck()
    all_by_id = {_cid(c): c for c in deck_proto}

    made_ct = {c['key']: 0 for c in CATS}
    total_ct = {c['key']: 0 for c in CATS}
    done    = {c['key']: 0 for c in CATS}

    total_iters = 0
    t0 = time.time()

    while any(done[c['key']] < n_per_cat for c in CATS):
        trump = rng.choice(ALL_SUITS)
        deck  = deck_proto[:]
        rng.shuffle(deck)
        deck_ids = {_cid(c) for c in deck}

        for cat in CATS:
            key = cat['key']
            if done[key] >= n_per_cat:
                continue

            hand = build_hand(cat, trump, rng, deck_ids, all_by_id)
            if hand is None:
                continue

            hand_ids = {_cid(c) for c in hand}
            remaining = [c for c in deck if _cid(c) not in hand_ids]
            rng.shuffle(remaining)
            h1, h2, h3 = remaining[:5], remaining[5:10], remaining[10:15]
            rest = remaining[15:]

            ai_players = [
                FixedHandCTBidderAI(0),
                make_ct_opponent(1),
                make_ct_opponent(2),
                make_ct_opponent(3),
            ]
            made, _, _ = play_round(
                bid=15,
                trump_suit=trump,
                hands=[hand[:], h1[:], h2[:], h3[:]],
                kitty=[],
                remaining_deck=rest[:],
                ai_players=ai_players,
            )
            if made:
                made_ct[key] += 1
            total_ct[key] += 1
            done[key] += 1
            total_iters += 1

        if total_iters % 10000 == 0 and total_iters > 0:
            elapsed = time.time() - t0
            lines = [[], [], []]
            for i, c in enumerate(CATS):
                k = c['key']
                m, n = made_ct[k], total_ct[k]
                r = m / n if n else 0.0
                lines[i // 5].append(f"{k}:{done[k]:>5}({r:.0%})")
            for ln in lines:
                print(f"  [{elapsed:.0f}s] {' | '.join(ln)}", flush=True)

    return made_ct, total_ct, time.time() - t0


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

def report(made_ct: dict, total_ct: dict, elapsed: float, n_per_cat: int):
    sep = '=' * 72
    print(f"\n{sep}")
    print(f"  CUTTHROAT BID RIG  |  bid=15  |  bidder hand fixed, no draw")
    print(f"  {n_per_cat:,} deals/category  |  {elapsed:.0f}s elapsed")
    print(f"  z vs 50% breakeven:  ** |z|>=3  * |z|>=2")
    print(sep)

    for group_name, keys in GROUPS:
        print(f"\n  ─── {group_name} ───")
        print(f"  {'Hand':<26}  {'n':>6}  {'make%':>6}  {'z vs 50%':>10}")
        for k in keys:
            m, n = made_ct[k], total_ct[k]
            if n == 0:
                continue
            p = m / n
            z = _z50(m, n)
            if abs(z) >= 3.0:
                sig = '**'
            elif abs(z) >= 2.0:
                sig = ' *'
            else:
                sig = '  '
            direction = 'MAKE' if p > 0.5 else 'BUST'
            print(f"  {CAT_LABEL[k]:<26}  {n:>6,}  {p:>5.1%}  {z:>+9.1f}{sig}  {direction if abs(z)>=2 else ''}")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='Make-rate rig for fixed trump hands bidding 15'
    )
    ap.add_argument('--deals', type=int, default=10000,
                    help='Deals per category (default: 10000)')
    ap.add_argument('--seed',  type=int, default=0)
    args = ap.parse_args()

    print(f"\nCutthroat bid rig  |  {args.deals:,} deals/category  |  seed={args.seed}")
    print(f"AI: champion-cutthroat (c1+c2 flags) for all 4 seats")
    print(f"15 categories × {args.deals:,} = ~{15 * args.deals:,} total games")

    made_ct, total_ct, elapsed = run_deals(args.deals, args.seed)
    report(made_ct, total_ct, elapsed, args.deals)


if __name__ == '__main__':
    main()
