"""
cutthroat_real_pattern_makerate.py — per-hand-pattern bidding make-rate
analyzer for REAL (human) gameplay in the cutthroat alpha.

Companion / counterpart to cutthroat_pattern_makerate.py (which runs the
champion bot against itself at all 4 seats and reports pattern make-rates
from simulation). This tool reads the LOGGED HUMAN BIDS from RTDB at
`bidLogCutthroat/{user}/{gameId}/{auto-id}` (forked from `bidLog/` in
v2.31.70 to keep partner-mode mining clean) and reports the same pattern
buckets, plus a side-by-side delta vs the rig prediction.

A bid is considered MADE if the auction winner's score delta from the
round-start scores to the next-round-start scores equals the bid amount
or higher. SET if delta is negative (-bid, or -2*bid for 30).

CAVEAT 1 — HAND-STAGE MISMATCH: The rig analyzer classifies the bidder's
POST-DISCARD/POST-DRAW 5-card hand (what they actually play with).
The bidLog only captures the PRE-BID 5-card hand (no kitty, no discard,
no draw). Pre-bid classification is a strict subset of information vs
post-draw — kitty access only adds anchors, never removes them. Pre-bid
T2 may often become post-draw T3+ after kitty pickup. So:
  * Pre-bid pattern X is a LOWER BOUND on post-draw anchors.
  * Comparing real-play X make-rate vs rig-post-draw X make-rate
    UNDERSTATES real-play because real-play X often grew anchors after
    the kitty/draw the rig classification already includes.
  * This is INTENTIONAL — we surface it in the header so the reader
    discounts negative deltas accordingly.

CAVEAT 2 — alpha-stage dataset: cutthroat is alpha-only. If total bid
count < 50, the analyzer leads with "INSUFFICIENT DATA — directional only"
and the deltas are noisy.

CLI:
  python -m bidding_simulator_v2.cutthroat_real_pattern_makerate
  python -m bidding_simulator_v2.cutthroat_real_pattern_makerate --user jack2112
  python -m bidding_simulator_v2.cutthroat_real_pattern_makerate --min-n 5

Read-only; no Firebase writes; no rig sim writes.
"""

import sys, os, io, argparse, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace')

from collections import defaultdict
from typing import List, Dict, Optional, Tuple

from game_engine import Card, Suit, is_trump
from bidding_simulator_v2 import bidding as bidlib
from bidding_simulator_v2.cutthroat_pattern_makerate import classify_hand

import firebase_admin
from firebase_admin import db as _db

DB = "https://fir-nbpt-default-rtdb.firebaseio.com"
_SUIT = {'♠': Suit.SPADES, '♥': Suit.HEARTS,
         '♦': Suit.DIAMONDS, '♣': Suit.CLUBS}

if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'databaseURL': DB})


# ── Firebase helpers ────────────────────────────────────────────────────────

def _card(cid):
    if not cid or not isinstance(cid, str):
        return None
    suit_ch = cid[-1]
    if suit_ch not in _SUIT:
        return None
    return Card(cid[:-1], _SUIT[suit_ch])


def _cards(lst):
    out = []
    for x in (lst or []):
        c = _card(x)
        if c is not None:
            out.append(c)
    return out


def _get(path):
    """Read a node via Admin SDK (bypasses App Check)."""
    try:
        return _db.reference(path).get()
    except Exception as e:
        print(f"  _get({path}) failed: {e}")
        return None


def _fetch_bids_cutthroat(user: Optional[str]) -> List[dict]:
    """Pull all bidLogCutthroat entries. If user is None, fetch all users.
    Annotates each record with `_user` and `_game`.
    """
    recs = []
    if user:
        d = _get(f'bidLogCutthroat/{user}')
        if isinstance(d, dict):
            for game_id, game in d.items():
                if isinstance(game, dict):
                    for r in game.values():
                        if isinstance(r, dict):
                            r['_user'] = user
                            r['_game'] = game_id
                            recs.append(r)
    else:
        users = _get('bidLogCutthroat')
        if isinstance(users, dict):
            for uname, games in users.items():
                if not isinstance(games, dict):
                    continue
                for game_id, game in games.items():
                    if isinstance(game, dict):
                        for r in game.values():
                            if isinstance(r, dict):
                                r['_user'] = uname
                                r['_game'] = game_id
                                recs.append(r)
    return recs


# ── Round-outcome inference from bidLog scores ──────────────────────────────

def _infer_round_outcomes(game_recs: List[dict]) -> List[dict]:
    """Given all logged bid entries for ONE game (any seat, any version),
    sort by timestamp, group into rounds, and infer the auction winner and
    whether they MADE or were SET.

    In cutthroat, `scores` is a list of 4 per-player scores (pre-bid for
    that round). The 4 entries within ONE round all share the same
    pre-bid `scores` snapshot. The NEXT round's `scores` snapshot is the
    delta-source: for each seat, delta = scores_next[seat] - scores_now[seat].
    The seat that won the auction (max chosenBid > 0, or dealer at autobag)
    determines whose delta we look at.

    Returns one dict per inferred round with fields:
      seat: winner seat (0..3)
      bid_amount: winning bid amount
      trump: trump suit string (♠♥♦♣)
      hand: pre-bid hand of the WINNER (5 Card objs)
      made: True / False / None (None if we cannot determine, e.g. last round)
      delta: int (delta seen)
      logger_seat: which seat (logger) we found the winner's record from
      scores_before: snapshot
      scores_after: snapshot or None
    """
    if not game_recs:
        return []

    # Sort by ts (fall back to insertion order if no ts)
    game_recs = sorted(game_recs, key=lambda r: r.get('ts') or 0)

    # Group into rounds. Round boundary = scores snapshot changes vs the
    # previous record (or the bidsSoFar resets). Simplest reliable rule:
    # group consecutive records that share the same `scores` snapshot.
    rounds = []
    cur = []
    cur_score_key = None
    for r in game_recs:
        sc = r.get('scores')
        key = json.dumps(sc, sort_keys=True) if sc is not None else None
        if cur_score_key is None:
            cur_score_key = key
        if key != cur_score_key:
            rounds.append(cur)
            cur = []
            cur_score_key = key
        cur.append(r)
    if cur:
        rounds.append(cur)

    out = []
    for ri, round_recs in enumerate(rounds):
        # Find the winning seat. Prefer the bidWinner field if it's set
        # (>= 0). Otherwise infer from chosenBid (max non-zero across the
        # round).
        # Note: each record stores the *logger's* perspective, so multiple
        # records in one round may agree (or disagree) on bidWinner depending
        # on whether the logger saw the final auction state.
        winner_seat = None
        winner_bid = 0
        winner_trump = None
        winner_hand_rec = None  # the record whose seat == winner_seat
        bw_votes = defaultdict(int)
        for r in round_recs:
            bw = r.get('bidWinner')
            if isinstance(bw, int) and bw >= 0:
                bw_votes[bw] += 1
        if bw_votes:
            winner_seat = max(bw_votes.items(), key=lambda x: x[1])[0]
        # If we still don't have a winner, fall back to highest chosenBid.
        if winner_seat is None:
            best_b = 0
            for r in round_recs:
                cb = int(r.get('chosenBid') or 0)
                if cb > best_b:
                    best_b = cb
                    winner_seat = int(r.get('seat'))
            winner_bid = best_b

        if winner_seat is None:
            continue

        # Find the winning bid amount: maximum chosenBid by anybody who
        # claims to be the winner, OR by the winner_seat record, OR the
        # highBid from records that came AFTER the winner bid.
        for r in round_recs:
            seat = r.get('seat')
            cb = int(r.get('chosenBid') or 0)
            if seat == winner_seat and cb > winner_bid:
                winner_bid = cb
            # highBid field reflects what the auction had reached when
            # this logger was about to act. So a record showing
            # highBid=20 means somebody (earlier in seat order) bid 20.
            hb = int(r.get('highBid') or 0)
            if hb > winner_bid:
                winner_bid = hb
        # autobag dealer at 15 if all passed: catch this — every bid was 0
        if winner_bid == 0:
            # search for an isAutoBag=true entry
            for r in round_recs:
                if r.get('isAutoBag'):
                    winner_bid = 15
                    break

        # The hand we want: the WINNER seat's own pre-bid record. If we
        # have a record where seat==winner_seat, use that hand. Otherwise
        # we cannot classify this round.
        for r in round_recs:
            if int(r.get('seat', -1)) == int(winner_seat):
                winner_hand_rec = r
                break
        # If no logger sat in the winner seat, we still want trump from any
        # record (later logger sees the trump after winner picks); but
        # bidLogCutthroat does NOT capture trump suit AFAIK. We may be
        # forced to skip.
        # Look at the actual record to see if there's a `trumpSuit` field.

        # Trump suit: bidLog records have a `chosenSuit` field? check
        trump = None
        for r in round_recs:
            for k in ('chosenSuit', 'trump', 'trumpSuit', 'suit'):
                if k in r and r[k]:
                    trump = r[k]
                    break
            if trump:
                break

        # Determine made/set from score delta
        sc_before = round_recs[0].get('scores')
        sc_after = None
        if ri + 1 < len(rounds):
            sc_after = rounds[ri + 1][0].get('scores')

        delta = None
        made = None
        if isinstance(sc_before, list) and isinstance(sc_after, list) \
                and 0 <= winner_seat < min(len(sc_before), len(sc_after)):
            delta = sc_after[winner_seat] - sc_before[winner_seat]
            # In cutthroat, MADE = bidder gains >= bid (positive). SET =
            # bidder loses bid (negative). Other seats gain trick points.
            if delta < 0:
                made = False
            elif delta >= winner_bid:
                made = True
            elif delta == 0:
                # Edge case: 0 delta could be SET-on-30-floored-to-0 or
                # made-then-bidder-took-zero-tricks-after-bagging. The
                # cutthroat scoring is "you lose your bid if you don't make
                # it"; 0 delta is unusual. Mark as inferred-fail (SET) for
                # the conservative interpretation.
                made = False
            else:
                # 0 < delta < bid_amount: bidder gained SOME points but
                # less than bid → SET (in 45s you lose the bid amount,
                # but legacy cutthroat scoring may credit raw tricks).
                # Conservative: SET.
                made = False

        out.append({
            'seat': winner_seat,
            'bid_amount': winner_bid,
            'trump': trump,
            'hand_rec': winner_hand_rec,
            'made': made,
            'delta': delta,
            'scores_before': sc_before,
            'scores_after': sc_after,
        })
    return out


# ── Rig prediction load (optional file with rig output) ─────────────────────

def _try_load_rig_baseline() -> Dict[Tuple[int, str], float]:
    """Try to load a previously-saved rig output for delta comparison.
    Returns {(bid_level, pattern): make_rate_pct}.

    If not present, returns empty dict and tool prints `(rig: n/a)`.
    Format: JSON file at `cutthroat_rig_makerate.json` next to this script.
    Schema:
      {"15": {"5J+T2": 0.83, ...}, "20": {...}, ...}
    """
    here = os.path.dirname(__file__)
    path = os.path.join(here, 'cutthroat_rig_makerate.json')
    out = {}
    if not os.path.exists(path):
        return out
    try:
        with open(path) as f:
            data = json.load(f)
        for lvl_str, pats in data.items():
            lvl = int(lvl_str)
            for pat, rate in pats.items():
                out[(lvl, pat)] = float(rate)
    except Exception as e:
        print(f"  (rig baseline load failed: {e})")
    return out


# ── Aggregation + report ────────────────────────────────────────────────────

def aggregate(round_outcomes: List[dict]) -> Dict[int, Dict[str, list]]:
    """outcomes → {bid_level: {pattern: [n, made]}}. Skips outcomes where
    we lack hand or made info."""
    out = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for ro in round_outcomes:
        hr = ro.get('hand_rec')
        if not hr:
            continue
        hand = _cards(hr.get('hand'))
        if not hand or len(hand) != 5:
            continue
        trump_str = ro.get('trump')
        # If the bid stage gave us a trump pick, use it. Otherwise pick
        # the winner's best trump from their hand (best estimate).
        if trump_str and trump_str in _SUIT:
            trump = _SUIT[trump_str]
        else:
            from bidding_simulator_v2.bidding import find_best_trump_suit
            trump = find_best_trump_suit(hand)['suit']
        bid_level = int(ro.get('bid_amount') or 0)
        if bid_level == 0:
            continue
        if ro.get('made') is None:
            continue
        pat = classify_hand(hand, trump)
        slot = out[bid_level][pat]
        slot[0] += 1
        if ro['made']:
            slot[1] += 1
    return out


def _print_header(title, w=82):
    print('\n' + '=' * w)
    print(f'  {title}')
    print('=' * w)


def print_report(agg, rig_baseline, total_bids, min_n=5):
    have_rig = bool(rig_baseline)

    if total_bids < 50:
        _print_header('!!!  INSUFFICIENT DATA — directional only  !!!')
        print(f'  Total real-play cutthroat bids: {total_bids}')
        print('  Pattern make-rates below are NOT statistically reliable.')
        print('  Decisions should NOT be made on these numbers alone.')

    for lvl in (15, 20, 25, 30):
        if lvl not in agg:
            continue
        rows = []
        other_n = other_m = 0
        for pat, (n, m) in agg[lvl].items():
            if n < min_n:
                other_n += n
                other_m += m
                continue
            real_rate = (m / n) if n else 0.0
            rig_rate = rig_baseline.get((lvl, pat))
            rows.append((pat, n, m, real_rate, rig_rate))
        if other_n > 0:
            rows.append((f'OTHER (n<{min_n} combined)', other_n, other_m,
                         (other_m / other_n) if other_n else 0.0, None))
        # sort: real make-rate desc, then n desc
        rows.sort(key=lambda r: (-r[3], -r[1]))

        tot_n = sum(r[1] for r in rows)
        tot_m = sum(r[2] for r in rows)
        tot_r = (tot_m / tot_n) if tot_n else 0.0
        _print_header(
            f'BIDS OF {lvl} — real-play vs rig '
            f'(cutthroat alpha, n_real_total={tot_n})')
        if have_rig:
            print(f'  {"pattern":<22}  {"n":>4}  {"made":>4}  '
                  f'{"real":>6}  {"rig":>6}  {"Δ":>7}')
        else:
            print(f'  {"pattern":<22}  {"n":>4}  {"made":>4}  '
                  f'{"real":>6}   (rig: n/a — no baseline file)')
        print('-' * 82)
        for (pat, n, m, real_r, rig_r) in rows:
            real_pct = f'{real_r*100:>5.1f}%'
            if rig_r is not None and have_rig:
                rig_pct = f'{rig_r*100:>5.1f}%'
                delta = (real_r - rig_r) * 100
                delta_s = f'{delta:>+6.1f}'
                print(f'  {pat:<22}  {n:>4}  {m:>4}  '
                      f'{real_pct}  {rig_pct}  {delta_s}')
            else:
                rig_pct = '   --' if have_rig else ''
                print(f'  {pat:<22}  {n:>4}  {m:>4}  {real_pct}  {rig_pct}')
        print(f'  {"TOTAL":<22}  {tot_n:>4}  {tot_m:>4}  '
              f'{tot_r*100:>5.1f}%')


def print_interpretation(agg, rig_baseline, total_bids):
    if not rig_baseline:
        _print_header('INTERPRETATION  (skipped — no rig baseline file)')
        print('  Drop a `cutthroat_rig_makerate.json` next to this script')
        print('  to enable side-by-side deltas. Format:')
        print('    {"15": {"5J+T2": 0.83, ...}, "20": {...}, ...}')
        print('  Generate by running cutthroat_pattern_makerate.py and')
        print('  saving its output rates to that JSON file.')
        return

    _print_header('INTERPRETATION')
    if total_bids < 50:
        print(f'  WARN: n_total={total_bids} — pattern-level deltas are')
        print('  directional. Do not surgically re-tune off this.')
        print()

    over_bidder = []  # real < rig (bidder overconfident — harder than rig)
    over_rig = []     # real > rig (rig too pessimistic — easier than rig)
    for lvl in (15, 20, 25, 30):
        if lvl not in agg:
            continue
        for pat, (n, m) in agg[lvl].items():
            if n < 5:
                continue
            real_r = m / n
            rig_r = rig_baseline.get((lvl, pat))
            if rig_r is None:
                continue
            d = (real_r - rig_r) * 100
            row = (lvl, pat, n, real_r*100, rig_r*100, d)
            if d <= -10:
                over_bidder.append(row)
            elif d >= +10:
                over_rig.append(row)

    over_bidder.sort(key=lambda x: x[5])  # most-negative first
    over_rig.sort(key=lambda x: -x[5])

    print('  Top 5 patterns where REAL-MAKE < RIG-MAKE by >=10pt')
    print('  (real game harder than rig predicted → AI overbidding):')
    if not over_bidder:
        print('    none at n>=5.')
    for lvl, pat, n, rl, rg, d in over_bidder[:5]:
        print(f'    bid {lvl}  {pat:<22}  n={n:<4}  real={rl:5.1f}%  '
              f'rig={rg:5.1f}%  Δ={d:+5.1f}')

    print()
    print('  Top 5 patterns where REAL-MAKE > RIG-MAKE by >=10pt')
    print('  (rig defenders too strong vs humans → rig overconfident in')
    print('   defense for these patterns):')
    if not over_rig:
        print('    none at n>=5.')
    for lvl, pat, n, rl, rg, d in over_rig[:5]:
        print(f'    bid {lvl}  {pat:<22}  n={n:<4}  real={rl:5.1f}%  '
              f'rig={rg:5.1f}%  Δ={d:+5.1f}')

    print()
    print('  RECOMMENDATION:')
    if over_bidder and total_bids >= 50:
        print('    The AI is bidding patterns it cannot consistently make')
        print('    in real play. Candidate surgical pass: lower the')
        print('    bidding threshold for the top-Δ patterns above. Run')
        print('    a tightening challenger in the rig and ship only on a')
        print('    z>2 win-rate improvement.')
    elif over_rig and total_bids >= 50:
        print('    The rig defenders are stronger than human cutthroat')
        print('    play. The verdict "bidding mostly fine" may be too')
        print('    pessimistic — consider loosening for the top-Δ buckets')
        print('    above.')
    else:
        print('    Either no signal at this n, or n is too low to act.')
        print('    Keep accumulating cutthroat games and re-run.')


def main():
    ap = argparse.ArgumentParser(
        description='Real-play (Firebase bidLogCutthroat) pattern '
                    'make-rate analyzer for cutthroat 45s.'
    )
    ap.add_argument('--user', default=None,
                    help='Filter to a single username (default: all users)')
    ap.add_argument('--min-n', type=int, default=5,
                    help='Collapse buckets with fewer than this into OTHER')
    args = ap.parse_args()

    _print_header(
        f'CUTTHROAT REAL-PLAY PATTERN MAKE-RATE'
        + (f'  (user: {args.user})' if args.user else '  (all users)'))

    recs = _fetch_bids_cutthroat(args.user)
    n_total_logged = len(recs)
    print(f'  bidLogCutthroat records fetched: {n_total_logged}')

    if n_total_logged == 0:
        print()
        print('  NO LOGGED CUTTHROAT BIDS IN FIREBASE.')
        print('  Possible reasons:')
        print('    1. No cutthroat games have been played by logged-in users.')
        print('    2. The bidLogCutthroat fork (index*.html v2.31.70) has')
        print('       not yet shipped to production OR has not yet captured')
        print('       a cutthroat session.')
        print('    3. Cutthroat games were played but the bidLog write')
        print('       silently failed (App Check / permissions).')
        print()
        print('  Next steps to validate:')
        print('    - Play a cutthroat game on index-test.html as a logged')
        print('      user, then re-run this tool.')
        print('    - Check Firebase Console for the bidLogCutthroat node.')
        print('    - Confirm the gameOptions.cutthroat flag is set in the')
        print('      live game (the toggle on the lobby screen).')
        print()
        return

    # Group by (user, game) and infer per-round outcomes
    by_game = defaultdict(list)
    for r in recs:
        key = (r.get('_user'), r.get('_game'))
        by_game[key].append(r)

    print(f'  distinct (user, game) pairs: {len(by_game)}')

    all_outcomes = []
    for (uname, gid), game_recs in by_game.items():
        outs = _infer_round_outcomes(game_recs)
        for o in outs:
            o['_user'] = uname
            o['_game'] = gid
        all_outcomes.extend(outs)

    print(f'  inferred rounds (all outcomes):  {len(all_outcomes)}')
    n_classifiable = sum(
        1 for o in all_outcomes
        if o.get('hand_rec') and o.get('made') is not None
        and (o.get('bid_amount') or 0) > 0
    )
    print(f'  classifiable rounds (hand+made known): {n_classifiable}')

    rig_baseline = _try_load_rig_baseline()
    if rig_baseline:
        print(f'  rig baseline loaded: {len(rig_baseline)} (lvl, pattern) cells')
    else:
        print('  rig baseline: (none — drop cutthroat_rig_makerate.json '
              'next to this script to enable Δ)')

    agg = aggregate(all_outcomes)
    print_report(agg, rig_baseline, n_classifiable, min_n=args.min_n)
    print_interpretation(agg, rig_baseline, n_classifiable)
    print()


if __name__ == '__main__':
    main()
