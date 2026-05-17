"""
divergence_miner.py — replay logged HUMAN card-play decisions through the
champion ImprovedAI and surface SYSTEMATIC disagreements.

The per-player logger (index-test.html v2.31.31+, decisionLog/{user}/{game})
captures the exact pre-play GameState a human faced + the card they chose.
Here we rebuild that GameState, ask the champion what IT would play, and
where they differ we cluster by situation. Frequent, lopsided clusters are
hypotheses a strong human plays a spot better than the AI — far better than
chasing one screenshot at a time.

NOT a ship tool: it only proposes evaluator hypotheses. Nothing here changes
the champion. Read-only Firebase pull (open rules) via the REST endpoint.

Run:  python -m bidding_simulator_v2.divergence_miner --user robr
      python -m bidding_simulator_v2.divergence_miner --user robr --min 15
"""

import sys, os, io, json, argparse, subprocess, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                                  errors='replace')

from game_engine import Card, Suit, get_trump_rank, GameState
from bidding_simulator_v2.improved_ai import ImprovedAI

DB = "https://fir-nbpt-default-rtdb.firebaseio.com"
_SUIT = {'♠': Suit.SPADES, '♥': Suit.HEARTS,
         '♦': Suit.DIAMONDS, '♣': Suit.CLUBS}


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


def _fetch(user):
    out = subprocess.run(
        ['curl', '-s', '--max-time', '40',
         f'{DB}/decisionLog/{user}.json'], capture_output=True).stdout
    d = json.loads(out) if out.strip() else None
    recs = []
    if isinstance(d, dict):
        for game_id, game in d.items():
            if isinstance(game, dict):
                for r in game.values():
                    if isinstance(r, dict):
                        r['_game'] = game_id
                        recs.append(r)
    return recs


def _rebuild(r):
    """Logged record → (seat, GameState, play_history) or None if unusable."""
    try:
        trump = _SUIT[r['trump']]
        seat = r['seat']
        leader = r['leader']
        hand = _cards(r['hand'])
        faced = _cards(r.get('trick'))                    # cards pre-play
        ctrick = [((leader + i) % 4, c) for i, c in enumerate(faced)]
        cards_played = _cards(r.get('cardsPlayed'))
        ph = [(h['p'], _card(h['c']))
              for h in (r.get('playHistory') or [])
              if _card(h.get('c')) is not None]
        kv = r.get('knownVoids')
        kv = json.loads(kv) if isinstance(kv, str) else (kv or [{}]*4)
        # high trump played so far (rank + who) — log omits it; derive.
        htr, htp = -1, -1
        for p, c in ph:
            tr = get_trump_rank(c, trump)
            if tr > htr:
                htr, htp = tr, p
        hands = [[], [], [], []]
        hands[seat] = hand
        st = GameState(
            hands=hands, trump_suit=trump,
            bid_winner=r['bidWinner'], high_bid=r.get('highBid', 0),
            dealer=0, current_trick=ctrick, trick_leader=leader,
            tricks_won=list(r.get('tricksWon') or [0, 0]),
            trick_num=int(r.get('trickNum', 0)) + 1,      # JS 0-idx → Py 1-idx
            cards_drawn=list(r.get('cardsDrawn') or [3, 3, 3, 3]),
            cards_played=cards_played,
            known_out_of_trump=list(r.get('knownOutOfTrump')
                                    or [False]*4),
            bidder_lost_trick=bool(r.get('bidderLostTrick')),
            high_trump_rank=htr, high_trump_winner=htp,
            known_voids=[dict(v) for v in kv])
        return seat, st, ph
    except Exception:
        return None


def _role(seat, bidw):
    if bidw < 0:
        return '?'
    if seat == bidw:
        return 'bidder'
    if seat % 2 == bidw % 2:
        return 'bidder-partner'
    return 'defender'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', default='robr')
    ap.add_argument('--min', type=int, default=10,
                    help='min cluster size to report as a hypothesis')
    args = ap.parse_args()

    recs = _fetch(args.user)
    print(f"\n  decisionLog/{args.user}: {len(recs)} logged card plays")
    if not recs:
        print("  (nothing to mine)\n"); return

    total = diverged = skipped = 0
    clusters = collections.Counter()
    examples = {}
    for r in recs:
        rb = _rebuild(r)
        if rb is None:
            skipped += 1; continue
        seat, st, ph = rb
        chosen = _card(r.get('chosen'))
        legal = _cards(r.get('legal'))
        if chosen is None or len(legal) <= 1:
            continue                                  # forced / unusable
        total += 1
        try:
            ai = ImprovedAI(seat).choose_card(st, ph)
        except Exception:
            skipped += 1; continue
        if str(ai) == str(chosen):
            continue
        diverged += 1
        trump = st.trump_suit
        led = st.current_trick[0][1] if st.current_trick else None
        key = (
            _role(seat, st.bid_winner),
            'lead' if not st.current_trick else 'follow',
            f"T{st.trick_num}",
            'human:trump' if get_trump_rank(chosen, trump) >= 0
            else 'human:offsuit',
            'ai:trump' if get_trump_rank(ai, trump) >= 0
            else 'ai:offsuit',
        )
        clusters[key] += 1
        examples.setdefault(key, (str(chosen), str(ai),
                                  r.get('_game', '?')))

    print(f"  usable decisions : {total}")
    print(f"  AI agrees        : {total - diverged} "
          f"({100*(total-diverged)/total:.1f}%)" if total else "")
    print(f"  DIVERGED         : {diverged} "
          f"({100*diverged/total:.1f}%)" if total else "")
    print(f"  skipped (rebuild): {skipped}")
    big = [(k, n) for k, n in clusters.most_common() if n >= args.min]
    print(f"\n  SYSTEMATIC clusters (>= {args.min}); each is an evaluator "
          f"hypothesis:")
    if not big:
        print("    none yet — need more logged games for this user.")
    for k, n in big:
        hc, ac, g = examples[k]
        role, lf, tn, hh, aa = k
        print(f"    [{n:>3}x] {role:14} {lf:6} {tn:4} | human={hh:12} "
              f"ai={aa:12}  e.g. human {hc} vs ai {ac} (game {g})")
    print(f"\n  → feed the biggest lopsided clusters to the evaluator as "
          f"opt-in rule hypotheses (test, ship only if they win).\n")


if __name__ == '__main__':
    main()
