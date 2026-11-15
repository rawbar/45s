"""Dump the actual hands jack2112 used for the 20-over-15 + 20-open clusters
so we can derive a tighter rig hypothesis than 'loosen all 20-bids'."""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from game_engine import Card, Suit
from bidding_simulator_v2 import bidding
from bidding_simulator_v2.bid_divergence_miner import _fetch_bids, _cards, _partner_bid, _bucket

USER = 'jack2112'
recs = _fetch_bids(USER)

def hand_str(cards):
    return ' '.join(f"{c.rank}{c.suit.value}" for c in cards)

def hand_features(cards):
    """Quick summary of trump-relevant content the bidding sim uses."""
    by_suit = {s: [c for c in cards if c.suit == s] for s in Suit}
    feats = []
    for s, group in by_suit.items():
        ranks = sorted([c.rank for c in group])
        if not group:
            continue
        has5 = '5' in ranks
        hasJ = 'J' in ranks
        hasA = 'A' in ranks
        size = len(group)
        feats.append(f"{s.value}={size}{'+5' if has5 else ''}{'+J' if hasJ else ''}{'+A' if hasA else ''}")
    ah = any(c.rank == 'A' and c.suit == Suit.HEARTS for c in cards)
    if ah:
        feats.append("A♥")
    return ' / '.join(feats)

groups = {}
for r in recs:
    try:
        hand = _cards(r.get('hand'))
        if not hand or len(hand) != 5:
            continue
        seat = int(r['seat'])
        dealer = int(r.get('dealer', 0))
        high_bid = int(r.get('highBid', 0) or 0)
        ts_ = r.get('teamScore') or 0
        os_ = r.get('oppScore') or 0
        chosen = int(r.get('chosenBid'))
        pb = _partner_bid(r.get('bidsSoFar'), seat)
        cb, _ = bidding.decide_bid(hand, high_bid, seat, dealer, ts_, os_, pb,
                                   enable_spoiler=True)
        if cb == chosen:
            continue
        key = (_bucket(ts_, os_, high_bid), high_bid, chosen, cb)
        groups.setdefault(key, []).append({
            'hand': hand, 'ts': ts_, 'os': os_, 'pb': pb,
            'seat': seat, 'dealer': dealer, 'game': r.get('_game'),
        })
    except Exception as e:
        continue

for key in sorted(groups, key=lambda k: -len(groups[k])):
    gctx, hb, hh, aa = key
    rs = groups[key]
    print(f"\n=== {gctx} hb={hb} | human={hh} ai={aa} ({len(rs)}x) ===")
    for r in rs:
        print(f"  hand: {hand_str(r['hand'])}  ({hand_features(r['hand'])})")
        print(f"    seat={r['seat']} dealer={r['dealer']} pb={r['pb']} ts={r['ts']} os={r['os']} game={r['game']}")
