"""
bid_divergence_miner.py — replay logged HUMAN BID decisions through the
champion decideBid and surface SYSTEMATIC disagreements.

Companion to divergence_miner.py (which does the same for card play). The
per-player bid logger (index-test.html v2.31.35+, bidLog/{user}/{game})
captures the exact pre-bid state a human faced INCLUDING live game scores
— the game-context the scoreless 5M oracle does NOT cover, and exactly
where the spoiler win came from. We rebuild that decision, ask the champion
what IT would bid (faithful = enable_spoiler=True, since shipped JS
decideBid runs the spoiler unconditionally), and cluster the divergences.

Why this matters for the expert (jack2112): he plays SOLO vs 3 champion
AI, so there is no human-reading edge — if his decisions equalled the
champion his team would win ~50%. His ~68% lifetime is a large
REPRODUCIBLE decision edge the rig must be able to find. Card-play
suspects (H-A / H-B / bidder_trump_save_lead) were all debunked, leaving
game-context BIDDING as the prime suspect. Each big lopsided cluster here
is an opt-in evaluator hypothesis (test in the rig, ship only if it wins).

NOT a ship tool. Read-only Firebase pull via the REST endpoint.

Run:  python -m bidding_simulator_v2.bid_divergence_miner --user jack2112
      python -m bidding_simulator_v2.bid_divergence_miner --user jack2112 --min 8
      python -m bidding_simulator_v2.bid_divergence_miner --user jack2112 --winstat
"""

import sys, os, io, json, argparse, subprocess, collections, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace')

from game_engine import Card, Suit
from bidding_simulator_v2 import bidding

DB = "https://fir-nbpt-default-rtdb.firebaseio.com"
_SUIT = {'♠': Suit.SPADES, '♥': Suit.HEARTS,
         '♦': Suit.DIAMONDS, '♣': Suit.CLUBS}
# baseline snapshot for win%-since-logging tracking
_BASE = os.path.join(os.path.dirname(__file__), 'winstat_baseline.json')

# Admin SDK init (migrated 2026-05-22 from unauthenticated curl REST
# because App Check enforcement now blocks REST reads without a token).
# Uses GOOGLE_APPLICATION_CREDENTIALS env var to point at the SA key.
import firebase_admin
from firebase_admin import credentials, db as _db
if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'databaseURL': DB})


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
    """Read a node from RTDB via Admin SDK (bypasses App Check enforcement)."""
    try:
        return _db.reference(path).get()
    except Exception as e:
        print(f"  _get({path}) failed: {e}")
        return None


def _fetch_bids(user):
    d = _get(f'bidLog/{user}')
    recs = []
    if isinstance(d, dict):
        for game_id, game in d.items():
            if isinstance(game, dict):
                for r in game.values():
                    if isinstance(r, dict):
                        r['_game'] = game_id
                        recs.append(r)
    return recs


def _partner_bid(bids_so_far, seat):
    """Mirror JS: bids[partner] unless null/-1 (not-yet / pass) → 0."""
    if not isinstance(bids_so_far, list):
        return 0
    pi = (seat + 2) % 4
    if pi < len(bids_so_far):
        v = bids_so_far[pi]
        if v is not None and v != -1:
            return v
    return 0


def _bucket(team_score, opp_score, high_bid):
    """Game-context bucket the divergence lives in."""
    they_need = 120 - (opp_score or 0)
    we_need = 120 - (team_score or 0)
    if they_need <= 20 and high_bid in (15, 20, 25):
        g = 'OPP-GAME-PT'           # spoiler regime
    elif we_need <= 20:
        g = 'WE-GAME-PT'            # we are about to win
    elif they_need <= 40 or we_need <= 40:
        g = 'late'
    else:
        g = 'early'
    return g


def _winstat(user):
    """Win% since logging started, via lifetime-stats delta vs a stored
    baseline snapshot. He plays solo vs 3 champion AI → champion-equivalent
    expectation is ~50%; a sustained gap is the edge to explain."""
    uid = None
    users = _get('users')
    if isinstance(users, dict):
        for k, v in users.items():
            if isinstance(v, dict):
                p = v.get('profile') or v
                if str(p.get('username', '')).lower() == user.lower():
                    uid = k
                    break
    if uid is None:
        print(f"  winstat: user '{user}' not found in /users"); return
    st = (_get(f'users/{uid}/stats') or {})
    gp, gw = int(st.get('gamesPlayed', 0)), int(st.get('gamesWon', 0))
    base = None
    if os.path.exists(_BASE):
        try:
            base = json.load(open(_BASE)).get(user.lower())
        except Exception:
            base = None
    print(f"\n  WIN% TRACKER — {user} (uid {uid})")
    print(f"    lifetime : {gw}/{gp} = {100*gw/gp:.1f}%" if gp else
          "    lifetime : (no games)")
    if base:
        dgp, dgw = gp - base['gp'], gw - base['gw']
        when = time.strftime('%Y-%m-%d',
                             time.localtime(base.get('ts', 0)))
        if dgp > 0:
            print(f"    since baseline ({when}): {dgw}/{dgp} = "
                  f"{100*dgw/dgp:.1f}%  (expected ~50% vs champion AI)")
            edge = 100*dgw/dgp - 50.0
            print(f"    → decision edge over champion baseline: "
                  f"{edge:+.1f}pt"
                  + ("  ← REPRODUCIBLE EDGE TO FIND" if edge > 8 else ""))
        else:
            print(f"    since baseline ({when}): no new games yet "
                  f"(need accumulation)")
    else:
        json.dump({user.lower(): {'gp': gp, 'gw': gw, 'ts': time.time()}},
                  open(_BASE, 'w'))
        print(f"    baseline SNAPSHOT written ({gw}/{gp}). Re-run later "
              f"to see win% since.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', default='jack2112')
    ap.add_argument('--min', type=int, default=6,
                    help='min cluster size to report as a hypothesis')
    ap.add_argument('--winstat', action='store_true',
                    help='also report win% since logging baseline')
    args = ap.parse_args()

    if args.winstat:
        _winstat(args.user)

    recs = _fetch_bids(args.user)
    print(f"\n  bidLog/{args.user}: {len(recs)} logged bids")
    if not recs:
        print("  (nothing to mine — need logged games for this user)\n")
        return

    total = diverged = skipped = 0
    clusters = collections.Counter()
    examples = {}
    for r in recs:
        try:
            hand = _cards(r.get('hand'))
            seat = int(r['seat'])
            dealer = int(r.get('dealer', 0))
            high_bid = int(r.get('highBid', 0) or 0)
            ts_ = r.get('teamScore') or 0
            os_ = r.get('oppScore') or 0
            chosen = int(r.get('chosenBid'))
            if not hand or len(hand) != 5:
                skipped += 1; continue
            pb = _partner_bid(r.get('bidsSoFar'), seat)
            # FAITHFUL champion = shipped JS: spoiler runs unconditionally.
            cb, _cs = bidding.decide_bid(
                hand, high_bid, seat, dealer, ts_, os_, pb,
                enable_spoiler=True)
        except Exception:
            skipped += 1; continue
        total += 1
        if cb == chosen:
            continue
        diverged += 1
        key = (
            _bucket(ts_, os_, high_bid),
            f"hb{high_bid}",
            'human:higher' if chosen > cb else 'human:lower',
            f"h{chosen}",
            f"ai{cb}",
        )
        clusters[key] += 1
        examples.setdefault(key, (chosen, cb, r.get('_game', '?')))

    print(f"  usable bids   : {total}")
    if total:
        print(f"  champ agrees  : {total-diverged} "
              f"({100*(total-diverged)/total:.1f}%)")
        print(f"  DIVERGED      : {diverged} "
              f"({100*diverged/total:.1f}%)")
    print(f"  skipped       : {skipped}")
    big = [(k, n) for k, n in clusters.most_common() if n >= args.min]
    print(f"\n  SYSTEMATIC bid clusters (>= {args.min}); each is an "
          f"evaluator hypothesis:")
    if not big:
        print("    none yet — need more logged games for this user.")
    for k, n in big:
        hc, ac, g = examples[k]
        gctx, hb, dirn, hh, aa = k
        print(f"    [{n:>3}x] {gctx:11} {hb:5} {dirn:13} | "
              f"human bids {hh:4} ai bids {aa:4}  e.g. {hc} vs {ac} "
              f"(game {g})")
    print(f"\n  → feed the biggest lopsided clusters to the evaluator as "
          f"opt-in bid-rule hypotheses (test, ship only if they win).\n")


if __name__ == '__main__':
    main()
