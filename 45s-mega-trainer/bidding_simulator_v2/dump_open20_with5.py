"""Dump the hands from robr's open-at-20-with-5 cluster (hb=0, human=20, ai=15, has5).
Check score context to detect bait bids (robr opens 20 to lure AI to 25).
"""
import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from game_engine import Card, Suit
from bidding_simulator_v2 import bidding
from bidding_simulator_v2.bid_divergence_miner import _fetch_bids, _cards, _partner_bid

USER = 'robr'

def hand_str(hand):
    return ' '.join(f"{c.rank}{c.suit.value}" for c in hand)

def best_suit(hand):
    best, best_score = None, -1
    for s in Suit:
        has5 = any(c.rank == '5' and c.suit == s for c in hand)
        hasJ = any(c.rank == 'J' and c.suit == s for c in hand)
        hasAH = any(c.rank == 'A' and c.suit == Suit.HEARTS for c in hand)
        hasAT = any(c.rank == 'A' and c.suit == s and s != Suit.HEARTS for c in hand)
        tc = sum(1 for c in hand
                 if c.suit == s or (c.rank == 'A' and c.suit == Suit.HEARTS))
        score = (50 if has5 else 0) + (30 if hasJ else 0) + (20 if hasAH else 0) + \
                (15 if hasAT else 0) + tc * 5
        if score > best_score:
            best, best_score = s, score
    return best

def hand_features(hand, suit):
    has5 = any(c.rank == '5' and c.suit == suit for c in hand)
    hasJ = any(c.rank == 'J' and c.suit == suit for c in hand)
    hasAH = any(c.rank == 'A' and c.suit == Suit.HEARTS for c in hand)
    hasAT = any(c.rank == 'A' and c.suit == suit and suit != Suit.HEARTS for c in hand)
    tc = sum(1 for c in hand
             if c.suit == suit or (c.rank == 'A' and c.suit == Suit.HEARTS))
    bits = []
    if has5: bits.append('5')
    if hasJ: bits.append('J')
    if hasAH: bits.append('A♥')
    if hasAT: bits.append('AT')
    bits.append(f"T{tc}")
    return '+'.join(bits) if bits else '?'

def can20_at_60pct(hand, suit):
    has5 = any(c.rank == '5' and c.suit == suit for c in hand)
    hasJ = any(c.rank == 'J' and c.suit == suit for c in hand)
    hasAH = any(c.rank == 'A' and c.suit == Suit.HEARTS for c in hand)
    hasAT = any(c.rank == 'A' and c.suit == suit and suit != Suit.HEARTS for c in hand)
    tc = sum(1 for c in hand
             if c.suit == suit or (c.rank == 'A' and c.suit == Suit.HEARTS))
    return (has5 or
            (hasJ and hasAH and tc >= 2) or
            (hasJ and hasAT and tc >= 2) or
            (hasJ and tc >= 3) or
            (hasAH and tc >= 4) or
            (hasAT and tc >= 4))

recs = _fetch_bids(USER)
print(f"\nbidLog/{USER}: {len(recs)} total bids")

hits = []
for r in recs:
    try:
        hand = _cards(r.get('hand'))
        if not hand or len(hand) != 5:
            continue
        seat = int(r['seat'])
        dealer = int(r.get('dealer', 0))
        high_bid = int(r.get('highBid', 0) or 0)
        ts_ = int(r.get('teamScore') or 0)
        os_ = int(r.get('oppScore') or 0)
        chosen = int(r.get('chosenBid'))
        pb = _partner_bid(r.get('bidsSoFar'), seat)

        if high_bid != 0 or chosen != 20:
            continue

        suit = best_suit(hand)
        has5 = any(c.rank == '5' and c.suit == suit for c in hand)
        if not has5:
            continue

        cb, _ = bidding.decide_bid(hand, high_bid, seat, dealer, ts_, os_, pb,
                                   enable_spoiler=True)
        if cb != 15:
            continue

        hits.append({
            'hand': hand, 'suit': suit, 'seat': seat, 'dealer': dealer,
            'ts': ts_, 'os': os_, 'pb': pb, 'game': r.get('_game', '?'),
            'bids_so_far': r.get('bidsSoFar', []),
            'ai_bid': cb,
        })
    except Exception as e:
        continue

print(f"open-at-20-with-5 cluster (hb=0, human=20, ai=15): {len(hits)} hands\n")

# Group by score context
early = [h for h in hits if h['os'] < 80 and h['ts'] < 80]
late  = [h for h in hits if h['os'] >= 80 or h['ts'] >= 80]
spoiler = [h for h in hits if h['os'] >= 100]

print(f"  Score context breakdown:")
print(f"    early (both <80)   : {len(early)}")
print(f"    late (either >=80) : {len(late)}")
print(f"    spoiler (opp>=100) : {len(spoiler)}")

print(f"\n{'─'*70}")
for ctx_name, group in [('EARLY (both<80)', early), ('LATE (either>=80)', late)]:
    if not group:
        continue
    print(f"\n  {ctx_name} — {len(group)} hands:")
    for i, h in enumerate(group, 1):
        suit = h['suit']
        feats = hand_features(h['hand'], suit)
        c20 = can20_at_60pct(h['hand'], suit)
        opp_near_win = h['os'] >= 100
        # Check if robr has 5 only (bare 5, likely bait) or 5 + support (genuine)
        has_support = any(c20 and feats != '5+T1' for _ in [0])
        note = ''
        if opp_near_win:
            note = '  ← OPP NEAR WIN (spoiler context)'
        elif feats in ('5+T1', '5+T2') and not any(x in feats for x in ['J', 'A♥', 'AT']):
            note = '  ← BARE 5 / low support (possible bait?)'
        print(f"    [{i:2}] {hand_str(h['hand'])}  "
              f"trump={suit.value}  feats={feats}  can20={c20}")
        print(f"         seat={h['seat']} dealer={h['dealer']} pb={h['pb']} "
              f"ts={h['ts']} os={h['os']} game={h['game']}{note}")
