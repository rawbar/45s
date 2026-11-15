"""Dump jack2112 bid divergence cluster hands for analysis.

Targets:
  A) 37x early hb0 h20 ai15  — Jack opens 20 clean auction, AI bids 15
  B) 22x early hb15 h0 ai20  — Jack passes when AI fires UPBID15
  C) 10x early hb20 h25 ai0  — Jack overbids to 25 at hb=20
"""
import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from game_engine import Card, Suit
from bidding_simulator_v2 import bidding
from bidding_simulator_v2.bid_divergence_miner import _fetch_bids, _cards, _partner_bid, _bucket

USER = 'jack2112'
recs = _fetch_bids(USER)

def hand_str(hand):
    return ' '.join(f"{c.rank}{c.suit.value}" for c in hand)

def find_trump(hand):
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

def feats(hand, suit):
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
    return '+'.join(bits)

def can20(hand, suit):
    has5 = any(c.rank == '5' and c.suit == suit for c in hand)
    hasJ = any(c.rank == 'J' and c.suit == suit for c in hand)
    hasAH = any(c.rank == 'A' and c.suit == Suit.HEARTS for c in hand)
    hasAT = any(c.rank == 'A' and c.suit == suit and suit != Suit.HEARTS for c in hand)
    tc = sum(1 for c in hand
             if c.suit == suit or (c.rank == 'A' and c.suit == Suit.HEARTS))
    return (has5 or (hasJ and hasAH and tc >= 2) or (hasJ and hasAT and tc >= 2) or
            (hasJ and tc >= 3) or (hasAH and tc >= 4) or (hasAT and tc >= 4))

clusters = {'A': [], 'B': [], 'C': []}

for r in recs:
    try:
        hand = _cards(r.get('hand'))
        if not hand or len(hand) != 5:
            continue
        seat = int(r['seat'])
        dealer = int(r.get('dealer', 0))
        hb = int(r.get('highBid', 0) or 0)
        ts_ = int(r.get('teamScore') or 0)
        os_ = int(r.get('oppScore') or 0)
        chosen = int(r.get('chosenBid'))
        pb = _partner_bid(r.get('bidsSoFar'), seat)
        bctx = _bucket(ts_, os_, hb)
        if bctx != 'early':
            continue
        cb, _ = bidding.decide_bid(hand, hb, seat, dealer, ts_, os_, pb,
                                   enable_spoiler=True)
        suit = find_trump(hand)
        rec = {
            'hand': hand, 'suit': suit, 'seat': seat, 'dealer': dealer,
            'ts': ts_, 'os': os_, 'pb': pb, 'game': r.get('_game', '?'),
            'ai_bid': cb, 'chosen': chosen, 'hb': hb,
            'is_dealer': (seat == dealer),
        }
        if hb == 0 and chosen == 20 and cb == 15:
            clusters['A'].append(rec)
        elif hb == 15 and chosen == 0 and cb == 20:
            clusters['B'].append(rec)
        elif hb == 20 and chosen == 25 and cb == 0:
            clusters['C'].append(rec)
    except Exception:
        continue

for label, title in [
    ('A', 'Jack opens 20 (clean auction hb=0), AI bids 15'),
    ('B', 'Jack passes at hb=15, AI fires UPBID15 to 20'),
    ('C', 'Jack overbids to 25 at hb=20, AI passes'),
]:
    grp = clusters[label]
    print(f"\n{'='*70}")
    print(f"CLUSTER {label}: {title}  [{len(grp)} hands]")
    print(f"{'='*70}")
    for i, h in enumerate(grp, 1):
        s = h['suit']
        f = feats(h['hand'], s)
        c = can20(h['hand'], s)
        dealer_flag = ' [DEALER]' if h['is_dealer'] else ''
        print(f"  [{i:2}] {hand_str(h['hand'])}  trump={s.value}  {f}  can20={c}{dealer_flag}")
        print(f"       seat={h['seat']} dealer={h['dealer']} pb={h['pb']} "
              f"ts={h['ts']} os={h['os']} game={h['game']}")
