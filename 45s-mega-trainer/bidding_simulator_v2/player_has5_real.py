"""
player_has5_real.py — for a given real username, mine decisionLog /
decisionLogCutthroat (trickNum==1 records = one per hand actually played,
excluding AI-seat records logged under this username) and report:
total hands played, and how many of them the player held the 5 of trump
at the start of play (post-discard if they were the bidder).
"""
import sys, os, io, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import firebase_admin
from firebase_admin import db as _db

DB = "https://fir-nbpt-default-rtdb.firebaseio.com"
if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'databaseURL': DB})


def _get(path):
    try:
        return _db.reference(path).get()
    except Exception as e:
        print(f"  _get({path}) failed: {e}")
        return None


def mine(root, user):
    d = _get(f'{root}/{user}')
    hands = 0
    has5 = 0
    if not isinstance(d, dict):
        return hands, has5
    for game_id, recs in d.items():
        if not isinstance(recs, dict):
            continue
        for r in recs.values():
            if not isinstance(r, dict):
                continue
            if r.get('aiSeat'):
                continue
            if int(r.get('trickNum', 0) or 0) != 1:
                continue
            trump = r.get('trump')
            hand = r.get('hand') or []
            hands += 1
            if any(isinstance(c, str) and c[:-1] == '5' and c[-1] == trump for c in hand):
                has5 += 1
    return hands, has5


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', required=True)
    args = ap.parse_args()
    u = args.user.lower()

    for label, root in [("PARTNER", "decisionLog"), ("CUTTHROAT", "decisionLogCutthroat")]:
        hands, has5 = mine(root, u)
        pct = 100.0 * has5 / hands if hands else 0.0
        print(f"{label}: {hands} hands played, held 5-of-trump {has5} times ({pct:.1f}%)")
