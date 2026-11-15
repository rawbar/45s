"""
bag_has5_real.py — mine REAL logged bidLog/bidLogCutthroat data (not a
simulation) for actual bagging events: a dealer record where seat==dealer
and highBid==0 (all 3 other seats passed before the dealer's own bid).
For each such real event, check whether the dealer's actual dealt hand
held the 5 of their best suit.

Pulls ALL users at once via the Admin SDK (same auth path as
bid_divergence_miner.py), not just one username.
"""
import sys, os, io, collections, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from game_engine import Card, Suit
from bidding_simulator_v2.bidding import find_best_trump_suit

import firebase_admin
from firebase_admin import db as _db

DB = "https://fir-nbpt-default-rtdb.firebaseio.com"
if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'databaseURL': DB})

_SUIT = {'♠': Suit.SPADES, '♥': Suit.HEARTS, '♦': Suit.DIAMONDS, '♣': Suit.CLUBS}


def _card(cid):
    if not cid or not isinstance(cid, str):
        return None
    return Card(cid[:-1], _SUIT[cid[-1]])


def _cards(lst):
    out = []
    for x in (lst or []):
        c = _card(x)
        if c is not None:
            out.append(c)
    return out


def _get(path):
    try:
        return _db.reference(path).get()
    except Exception as e:
        print(f"  _get({path}) failed: {e}")
        return None


def mine(root):
    """root = 'bidLog' or 'bidLogCutthroat'. Returns (bagged, bagged_has5,
    bagged_hasJ_no5, users_seen, games_seen)."""
    d = _get(root)
    bagged = bagged_has5 = bagged_hasJ_no5 = 0
    users_seen = set()
    games_seen = set()
    if not isinstance(d, dict):
        return bagged, bagged_has5, bagged_hasJ_no5, users_seen, games_seen
    for user, games in d.items():
        if not isinstance(games, dict):
            continue
        for game_id, recs in games.items():
            if not isinstance(recs, dict):
                continue
            for r in recs.values():
                if not isinstance(r, dict):
                    continue
                try:
                    seat = int(r['seat'])
                    dealer = int(r.get('dealer', -1))
                    high_bid = int(r.get('highBid', 0) or 0)
                except (KeyError, TypeError, ValueError):
                    continue
                if seat != dealer or high_bid != 0:
                    continue  # not a real bagging event
                hand = _cards(r.get('hand'))
                if len(hand) != 5:
                    continue
                users_seen.add(user)
                games_seen.add((user, game_id))
                bagged += 1
                info = find_best_trump_suit(hand)
                if info['has5']:
                    bagged_has5 += 1
                elif info['hasJ']:
                    bagged_hasJ_no5 += 1
    return bagged, bagged_has5, bagged_hasJ_no5, users_seen, games_seen


def report(label, root):
    bagged, has5, hasJ_no5, users, games = mine(root)
    print(f"\n=== {label} ({root}) — REAL logged data ===")
    print(f"distinct users: {len(users)}  distinct games: {len(games)}")
    print(f"real bagging events found: {bagged}")
    if bagged == 0:
        print("  (none logged yet)")
        return
    pct5 = 100.0 * has5 / bagged
    pctJ = 100.0 * hasJ_no5 / bagged
    pctN = 100.0 - pct5 - pctJ
    print(f"  bagged dealer HAD the 5: {has5} ({pct5:.1f}%)")
    print(f"  bagged dealer had J, no 5: {hasJ_no5} ({pctJ:.1f}%)")
    print(f"  neither: {bagged - has5 - hasJ_no5} ({pctN:.1f}%)")


if __name__ == '__main__':
    report("PARTNER", "bidLog")
    report("CUTTHROAT", "bidLogCutthroat")
