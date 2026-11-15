"""
bid_divergence_miner_cutthroat.py — cutthroat sibling of bid_divergence_miner.

Reads `bidLogCutthroat/{user}` instead of `bidLog/{user}`, replays each
HUMAN BID through the CHAMPION CUTTHROAT policy (Policy(cutthroat=True)
with all currently-shipped flags at their default), and clusters the
divergences. Used to surface candidate cutthroat-only bidding rules.

Cutthroat record extras (vs partner-mode bidLog):
  - `playerScores` (post-v2.31.84): list of 4 per-player scores so we can
    compute `maxOppScore`, `dealer_score`, and filter spoiler/desperation.
  - `maxOppScore`: convenience field, present iff `playerScores` is.

We filter records to those with `playerScores` (clean hand-strength bids
only). We further filter OUT entries where any opp is at >=110 (treat as
spoiler/desperation, not hand-strength).

NOT a ship tool. Mining-only.

Run:  python -m bidding_simulator_v2.bid_divergence_miner_cutthroat --user robr
      python -m bidding_simulator_v2.bid_divergence_miner_cutthroat --user robr --min 2
      python -m bidding_simulator_v2.bid_divergence_miner_cutthroat --user robr --min 2 --verbose
"""

import sys, os, io, json, argparse, collections, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace')

from game_engine import Card, Suit
from bidding_simulator_v2 import bidding
from bidding_simulator_v2.policy import Policy

DB = "https://fir-nbpt-default-rtdb.firebaseio.com"
_SUIT = {'♠': Suit.SPADES, '♥': Suit.HEARTS,
         '♦': Suit.DIAMONDS, '♣': Suit.CLUBS}

import firebase_admin
from firebase_admin import db as _db
if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'databaseURL': DB})

# Spoiler/desperation cutoff: any opp at this score or above and we treat
# the bid as score-context-driven, not hand-strength.
SPOILER_OPP_THRESHOLD = 110


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


def _fetch_bids(user):
    d = _get(f'bidLogCutthroat/{user}')
    recs = []
    if isinstance(d, dict):
        for game_id, game in d.items():
            if isinstance(game, dict):
                for r in game.values():
                    if isinstance(r, dict):
                        r['_game'] = game_id
                        recs.append(r)
    # sort by ts so divergences print in chronological order
    recs.sort(key=lambda r: r.get('ts', 0))
    return recs


def _hand_pattern(hand, suit):
    """Return a compact human-readable hand pattern key."""
    if suit is None:
        return "no-trump"
    has5 = any(c.rank == '5' and c.suit == suit for c in hand)
    hasJ = any(c.rank == 'J' and c.suit == suit for c in hand)
    hasAH = any(c.rank == 'A' and c.suit == Suit.HEARTS for c in hand)
    hasAT = any(c.rank == 'A' and c.suit == suit and suit != Suit.HEARTS
                for c in hand)
    tc = sum(1 for c in hand
             if c.suit == suit or (c.rank == 'A' and c.suit == Suit.HEARTS))
    bits = []
    if has5: bits.append('5')
    if hasJ: bits.append('J')
    if hasAH: bits.append('AH')
    if hasAT: bits.append('AT')
    bits.append(f"T{tc}")
    return '+'.join(bits)


def _bucket(player_scores, my_seat, high_bid):
    """Game-context bucket. In cutthroat: 'opp' = any non-self seat."""
    if not isinstance(player_scores, list) or len(player_scores) != 4:
        return 'unk'
    me = player_scores[my_seat] or 0
    opps = [s or 0 for i, s in enumerate(player_scores) if i != my_seat]
    max_opp = max(opps) if opps else 0
    if max_opp >= 110:
        return 'OPP-GAME-PT'
    if me >= 100:
        return 'WE-GAME-PT'
    if max_opp >= 80 or me >= 80:
        return 'late'
    return 'early'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', default='robr')
    ap.add_argument('--min', type=int, default=2,
                    help='min cluster size to report (default 2 — small sample)')
    ap.add_argument('--verbose', action='store_true',
                    help='print one example record per cluster')
    ap.add_argument('--keep-spoilers', action='store_true',
                    help='do NOT filter out near-game-point bids')
    args = ap.parse_args()

    recs = _fetch_bids(args.user)
    print(f"\n  bidLogCutthroat/{args.user}: {len(recs)} logged bids")
    if not recs:
        print("  (nothing to mine — need logged cutthroat games for this user)\n")
        return

    with_ps = [r for r in recs if 'playerScores' in r]
    without_ps = len(recs) - len(with_ps)
    print(f"  with playerScores  : {len(with_ps)} (post-v2.31.84)")
    print(f"  without playerScores: {without_ps} (pre-v2.31.84, score context unknown)")

    if with_ps:
        ts_min = min(r.get('ts', 0) for r in with_ps)
        ts_max = max(r.get('ts', 0) for r in with_ps)
        if ts_min:
            import datetime
            print(f"  date range (w/ ps) : "
                  f"{datetime.datetime.fromtimestamp(ts_min/1000).strftime('%Y-%m-%d')} "
                  f"to {datetime.datetime.fromtimestamp(ts_max/1000).strftime('%Y-%m-%d')}")

    # Spoiler / desperation filter (only meaningful on records w/ playerScores)
    def is_spoiler(r):
        ps = r.get('playerScores')
        if not isinstance(ps, list) or len(ps) != 4:
            return False
        my_seat = int(r.get('seat', 0))
        opps = [s or 0 for i, s in enumerate(ps) if i != my_seat]
        return max(opps) >= SPOILER_OPP_THRESHOLD if opps else False

    spoiler_count = sum(1 for r in with_ps if is_spoiler(r))
    if args.keep_spoilers:
        clean = with_ps
        print(f"  spoiler/desperation (opp>={SPOILER_OPP_THRESHOLD}): "
              f"{spoiler_count} (KEEPING per --keep-spoilers)")
    else:
        clean = [r for r in with_ps if not is_spoiler(r)]
        print(f"  spoiler/desperation (opp>={SPOILER_OPP_THRESHOLD}): "
              f"{spoiler_count} (FILTERED OUT)")
    print(f"  clean hand-strength: {len(clean)}")

    # Champion cutthroat = current shipped cutthroat AI bidding policy.
    champ = Policy(cutthroat=True)

    total = diverged = skipped = 0
    clusters = collections.Counter()
    examples = {}
    div_records = []
    for r in clean:
        try:
            hand = _cards(r.get('hand'))
            seat = int(r['seat'])
            dealer = int(r.get('dealer', 0))
            high_bid = int(r.get('highBid', 0) or 0)
            chosen = int(r.get('chosenBid'))
            ps = r.get('playerScores') or [0, 0, 0, 0]
            if not hand or len(hand) != 5:
                skipped += 1; continue
            # In cutthroat, partner_bid is forced to 0 inside bidding.decide_bid
            # but the Policy wraps that; we still pass through whatever was
            # logged for completeness. team_scores/opp_scores are partner-mode
            # concepts; champion-cutthroat zeroes the partner-aware branches.
            # We pass mySeatScore as team_scores and maxOppScore as opp_scores
            # to keep the desperation/cruise context faithful.
            my_seat_score = int(r.get('mySeatScore', ps[seat] or 0))
            max_opp_score = int(r.get('maxOppScore',
                                      max((s or 0) for i, s in enumerate(ps)
                                          if i != seat) if ps else 0))
            dealer_score = int(ps[dealer] or 0) if dealer < len(ps) else 0
            cb, _cs = champ.decide_bid(
                hand, high_bid, seat, dealer,
                my_seat_score, max_opp_score, 0,
                dealer_score=dealer_score)
        except Exception as e:
            skipped += 1; continue
        total += 1
        if cb == chosen:
            continue
        diverged += 1
        # find best suit for hand pattern label
        try:
            fb = bidding.find_best_trump_suit(hand)
            patt = _hand_pattern(hand, fb['suit'])
        except Exception:
            patt = '?'
        gctx = _bucket(ps, seat, high_bid)
        key = (
            gctx,
            f"hb{high_bid}",
            patt,
            'human:higher' if chosen > cb else 'human:lower',
            f"h{chosen}",
            f"ai{cb}",
        )
        clusters[key] += 1
        examples.setdefault(key, r)
        div_records.append((key, r))

    print(f"\n  usable bids   : {total}")
    if total:
        print(f"  champ agrees  : {total-diverged} "
              f"({100*(total-diverged)/total:.1f}%)")
        print(f"  DIVERGED      : {diverged} "
              f"({100*diverged/total:.1f}%)")
    print(f"  skipped       : {skipped}")

    big = [(k, n) for k, n in clusters.most_common() if n >= args.min]
    print(f"\n  CUTTHROAT bid clusters (>= {args.min}); each is a candidate hypothesis:")
    if not big:
        print("    none — all robr bids match shipped cutthroat champion.")
    for k, n in big:
        gctx, hb, patt, dirn, hh, aa = k
        print(f"    [{n:>3}x] {gctx:11} {hb:5} {patt:18} {dirn:13} | "
              f"human {hh:4} vs ai {aa:4}")
        if args.verbose:
            r = examples[k]
            hand_str = ' '.join(r.get('hand', []))
            ps = r.get('playerScores')
            print(f"          e.g. seat={r.get('seat')} dealer={r.get('dealer')} "
                  f"hand=[{hand_str}] scores={ps} bids={r.get('bidsSoFar')} "
                  f"game={r.get('_game', '?')}")

    # also dump ALL singleton divergences for context (n=1, low signal but
    # sometimes a fresh pattern hides here)
    smalls = [(k, n) for k, n in clusters.most_common() if n < args.min]
    if smalls:
        print(f"\n  Singleton/low-count divergences (n<{args.min}): "
              f"{len(smalls)} clusters")
        if args.verbose:
            for k, n in smalls:
                gctx, hb, patt, dirn, hh, aa = k
                print(f"    [{n:>3}x] {gctx:11} {hb:5} {patt:18} {dirn:13} | "
                      f"human {hh:4} vs ai {aa:4}")
    print()


if __name__ == '__main__':
    main()
