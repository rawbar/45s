"""
improved_ai.py — Faithful port of current index.html game AI.

Ported 2026-05-16 from index.html chooseCardToPlay / decideDiscard /
buildPlayerIntelligence / isCardBoss / getHighestRemainingTrump /
estimateOpponentTrump / isBidderSignaling (game version v2.31.23).

Goal: the simulator must play *exactly* like the shipped game so the
re-calibrated bidding thresholds reflect real in-game outcomes. Where the
JS has internal quirks (e.g. getTrumpRank vs getHighestRemainingTrump
disagree on low-trump order), those quirks are preserved deliberately.

Card identity strings use f"{rank}{suit.value}" (e.g. '5♠', 'A♥') to match
the JS `id` field exactly — knownVoids.possibleTrump entries are these ids.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import List, Tuple, Dict, Optional
from game_engine import (
    Card, Suit, GameState,
    get_trump_rank, get_offsuit_rank, is_trump, card_beats, get_playable_cards,
)

HEARTS = Suit.HEARTS


# ─────────────────────────────────────────────────────────────────────────────
# Card helpers
# ─────────────────────────────────────────────────────────────────────────────

def cid(card: Card) -> str:
    return f"{card.rank}{card.suit.value}"


def _tr(card: Card, trump: Suit) -> int:
    return get_trump_rank(card, trump)


def _is_trump(card: Card, trump: Suit) -> bool:
    return get_trump_rank(card, trump) >= 0


def trick_winner(cards: List[Card], trump: Suit, leader: int) -> int:
    """Port of determineTrickWinner: positional winner among `cards`, +leader."""
    if not cards:
        return leader
    led_suit = cards[0].suit
    win_idx = 0
    win_card = cards[0]
    for i in range(1, len(cards)):
        if card_beats(cards[i], win_card, trump, led_suit):
            win_idx = i
            win_card = cards[i]
    return (leader + win_idx) % 4


_BLACK_LOW_ORDER = ['10', '9', '8', '7', '6', '4', '3', '2']  # index 0-7 → ranks 80-87
_RED_LOW_ORDER   = ['2', '3', '4', '6', '7', '8', '9', '10']  # index 0-7 → ranks 80-87


def _card_at_rank(rank: int, trump: Suit) -> Optional[Card]:
    """Reverse get_trump_rank: a real Card whose trump rank == `rank`.
    Used by the worst-case pad to materialise an opponent's known
    minimum-rank trump for trick_winner probes."""
    if rank == 102: return Card('5', trump)
    if rank == 101: return Card('J', trump)
    if rank == 100: return Card('A', HEARTS)
    if rank == 99 and trump != HEARTS: return Card('A', trump)
    if rank == 98:  return Card('K', trump)
    if rank == 97:  return Card('Q', trump)
    if 80 <= rank <= 87:
        order = _RED_LOW_ORDER if trump in (HEARTS, Suit.DIAMONDS) else _BLACK_LOW_ORDER
        return Card(order[rank - 80], trump)
    return None


def _worst_case_pad(cards: List[Card],
                    trump: Suit,
                    leader: int,
                    known_voids: List[dict]) -> List[Card]:
    """Pad partial trick to 4 cards assuming each after-me opponent plays
    the worst (for me) card they could plausibly hold.

    Uses follow_trump_floor: if seat S has known min_trump_rank R and is
    not provably trump-void, pad seat S with a real trump card at rank R
    (so trick_winner sees them over-trumping us if our candidate is below
    their floor). Else falls back to the safe non-trump dummy.

    Caller decides when to apply (via the strategic flag).
    """
    out = list(cards)
    for pos in range(len(cards), 4):
        seat = (leader + pos) % 4
        ov = known_voids[seat] if seat < len(known_voids) else {}
        is_void = ov.get('trump') is True
        floor = ov.get('min_trump_rank', 0)
        if (not is_void) and floor > 0:
            c = _card_at_rank(floor, trump)
            if c is not None:
                out.append(c)
                continue
        out.append(Card('2', HEARTS if trump != HEARTS else Suit.CLUBS))
    return out


def _pad4(cards: List[Card], trump: Optional[Suit] = None) -> List[Card]:
    """Pad partial trick to 4 cards for trick_winner() probes.

    LEGACY (trump=None): dummy is 2♣, which is itself trump in clubs games
    and ranks 87 (above real 3-10 of clubs trump). That makes canBeat-style
    probes incorrectly report "can't beat" for any low-trump candidate when
    trump is clubs — the AI underplays trump in clubs-trump games as a
    result (user-reported, round T4).

    SAFE (trump=<suit>): dummy is 2 of a non-trump suit, so it never wins
    any probe and the candidate's true rank decides correctly.
    """
    out = list(cards)
    if trump is None:
        dummy = Card('2', Suit.CLUBS)  # legacy buggy default
    else:
        # 2 of a non-trump suit. 2♥ in non-hearts trump; 2♣ otherwise.
        dummy = Card('2', Suit.HEARTS if trump != Suit.HEARTS else Suit.CLUBS)
    while len(out) < 4:
        out.append(dummy)
    return out


def _completed_tricks(play_history: List[Tuple[int, Card]],
                      first_leader: int, trump: Suit):
    """Reconstruct completed 4-card tricks from flat play_history.
    play_history is in play order; trick 1 leader = bidder, each next
    leader = prior trick winner. Trailing partial (in-progress) trick
    is ignored. Returns list of (leader, [(pi,card),...], winner)."""
    out = []
    leader = first_leader
    s = 0
    while s + 4 <= len(play_history):
        chunk = play_history[s:s + 4]
        cards = [c for (_, c) in chunk]
        w = trick_winner(cards, trump, leader)
        out.append((leader, chunk, w))
        leader = w
        s += 4
    return out


def _partner_shed_high_trump(play_history: List[Tuple[int, Card]],
                             partner_idx: int, first_leader: int,
                             trump: Suit) -> bool:
    """Deductive trump-floor proxy: on a completed trick partner did NOT
    win, partner played a trump >= K (rank 98). Under an unbeatable lead
    you shed your lowest, so a >=K shed ⟹ partner's remaining trump are
    high (>= Q after the adjacent-pair-bluff slack)."""
    for leader, chunk, winner in _completed_tricks(play_history, first_leader,
                                                   trump):
        if winner == partner_idx:
            continue
        for pi, c in chunk:
            if pi == partner_idx and get_trump_rank(c, trump) >= 98:
                return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# getHighestRemainingTrump  (JS-faithful, including its internal low-card order)
# ─────────────────────────────────────────────────────────────────────────────

def get_highest_remaining_trump(cards_played: List[Card], trump: Suit) -> int:
    played = {cid(c) for c in cards_played}
    tv = trump.value
    if f"5{tv}" not in played:
        return 102
    if f"J{tv}" not in played:
        return 101
    if "A♥" not in played:
        return 100
    if trump != HEARTS and f"A{tv}" not in played:
        return 99
    if f"K{tv}" not in played:
        return 98
    if f"Q{tv}" not in played:
        return 97
    lower = (['10', '9', '8', '7', '6', '4', '3', '2']
             if trump in (Suit.HEARTS, Suit.DIAMONDS)
             else ['2', '3', '4', '6', '7', '8', '9', '10'])
    for i in range(len(lower) - 1, -1, -1):
        if f"{lower[i]}{tv}" not in played:
            return 80 + i
    return -1


# ─────────────────────────────────────────────────────────────────────────────
# isCardBoss  (JS-faithful)
# ─────────────────────────────────────────────────────────────────────────────

def is_card_boss(card: Card, cards_played: List[Card], trump: Suit) -> bool:
    if not _is_trump(card, trump):
        return False
    card_rank = _tr(card, trump)
    played = {cid(c) for c in cards_played}
    tv = trump.value
    higher: List[Card] = []

    top = [Card('5', trump), Card('J', trump), Card('A', HEARTS)]
    if trump != HEARTS:
        top.append(Card('A', trump))
    for tc in top:
        if cid(tc) != cid(card) and _tr(tc, trump) > card_rank:
            higher.append(tc)

    if trump in (Suit.HEARTS, Suit.DIAMONDS):
        ranks_to_check = ['K', 'Q', '10', '9', '8', '7', '6', '5', '4', '3', '2', 'A', 'J']
    else:
        ranks_to_check = ['K', 'Q', 'J', 'A', '2', '3', '4', '5', '6', '7', '8', '9', '10']
    for r in ranks_to_check:
        if r != '5' and r != 'J' and not (r == 'A' and trump == HEARTS):
            tc = Card(r, trump)
            if _tr(tc, trump) > card_rank:
                higher.append(tc)

    relevant = [c for c in higher if cid(c) != cid(card)]
    return all(cid(c) in played for c in relevant)


# ─────────────────────────────────────────────────────────────────────────────
# estimateOpponentTrump  (JS-faithful)
# ─────────────────────────────────────────────────────────────────────────────

def estimate_opponent_trump(draw_count: int, trump_played_count: int) -> int:
    if draw_count >= 4:
        start = 2
    elif draw_count == 3:
        start = 2
    else:  # <= 2
        start = 3
    return max(0, start - trump_played_count)


# ─────────────────────────────────────────────────────────────────────────────
# isBidderSignaling  (JS-faithful)
# ─────────────────────────────────────────────────────────────────────────────

ALL_SUITS = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
ALL_RANKS_SIG = ['5', 'J', 'A', 'K', 'Q', '10', '9', '8', '7', '6', '4', '3', '2']


def is_bidder_signaling(led_card: Card, trump: Suit,
                        cards_played: List[Card], trick_num: int) -> bool:
    led_is_trump = _is_trump(led_card, trump)
    if not led_is_trump:
        return True
    if led_is_trump and trick_num <= 2:
        led_rank = _tr(led_card, trump)
        played = {cid(c) for c in cards_played}
        all_trump = []
        for s in ALL_SUITS:
            for r in ALL_RANKS_SIG:
                tc = Card(r, s)
                if _is_trump(tc, trump):
                    all_trump.append(tc)
        unplayed_higher = [c for c in all_trump
                           if cid(c) not in played and _tr(c, trump) > led_rank]
        return len(unplayed_higher) >= 5
    return False


# ─────────────────────────────────────────────────────────────────────────────
# buildPlayerIntelligence  (JS-faithful)
# ─────────────────────────────────────────────────────────────────────────────

def build_player_intelligence(play_history: List[Tuple[int, Card]],
                               cards_played: List[Card],
                               known_voids: List[dict],
                               drawn: List[int],
                               trump: Suit) -> Dict:
    players = []
    for p in range(4):
        p_cards = [c for (pi, c) in play_history if pi == p]
        trump_cards = [c for c in p_cards if _tr(c, trump) >= 0]
        offsuit_cards = [c for c in p_cards if _tr(c, trump) < 0]
        vi = (known_voids[p] if known_voids and p < len(known_voids) and known_voids[p]
              else {})
        trump_status = 'unknown'
        if vi.get('trump') is True:
            trump_status = 'void'
        elif vi.get('trump') == 'reneging':
            trump_status = 'reneging-only'
        void_suits = [k for k, v in vi.items()
                      if k not in ('trump', 'possibleTrump', 'noLowTrump') and v is True]
        players.append({
            'cardsDrawn': drawn[p],
            'cardsPlayed': p_cards,
            'cardsRemaining': 5 - len(p_cards),
            'trumpPlayed': trump_cards,
            'trumpPlayedCount': len(trump_cards),
            'estimatedTrumpRemaining': estimate_opponent_trump(drawn[p], len(trump_cards)),
            'trumpStatus': trump_status,
            'possibleTrump': vi.get('possibleTrump', []) or [],
            'noLowTrump': bool(vi.get('noLowTrump')),
            'voidSuits': void_suits,
            'offsuitPlayed': offsuit_cards,
        })
    return {
        'players': players,
        'highestRemainingTrumpRank': get_highest_remaining_trump(cards_played, trump),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Cutthroat helpers — bidder mid-round point accounting + lock detection
# ─────────────────────────────────────────────────────────────────────────────

def _ct_bidder_round_pts(bid_winner: int,
                          player_tricks_so_far: List[int],
                          high_trump_player_so_far: int) -> int:
    """Bidder's round pts so far (5 per trick won + 5 bonus iff bidder
    currently owns the high-trump trick). `high_trump_player_so_far == -1`
    means no trump has been played yet → no bonus assigned."""
    if not player_tricks_so_far:
        return 0
    pts = player_tricks_so_far[bid_winner] * 5
    if high_trump_player_so_far == bid_winner:
        pts += 5
    return pts


def _ct_set_locked(high_bid: int,
                    bid_winner: int,
                    player_tricks_so_far: List[int],
                    high_trump_player_so_far: int,
                    current_trick_num: int) -> bool:
    """True iff the bidder mathematically cannot reach the bid even if they
    win every remaining trick. `current_trick_num` is the trick now in
    progress (1..5); tricks 1..current_trick_num-1 are complete.

    Remaining-bonus accounting: if some trump has already been played
    (high_trump_player_so_far != -1), the +5 bonus is already locked to a
    seat — the bidder gets it only if THEY own that seat (already in the
    base pts). If no trump has been played yet, a future trick could carry
    the bonus → assume the bidder could win it (max upper bound)."""
    if player_tricks_so_far is None:
        return False
    pts = _ct_bidder_round_pts(bid_winner, player_tricks_so_far,
                                high_trump_player_so_far)
    tricks_remaining = 5 - (current_trick_num - 1)  # incl. current trick
    # If bonus is already with someone other than bidder, bidder CANNOT
    # get it (it's locked to that seat). If still unassigned (no trump
    # played yet), assume the bidder could win it (upper bound).
    if high_trump_player_so_far == -1:
        bonus_max = 5
    else:
        bonus_max = 0   # already counted in pts (or locked elsewhere)
    max_remaining = tricks_remaining * 5 + bonus_max
    return (pts + max_remaining) < high_bid


def _ct_made_locked(high_bid: int,
                     bid_winner: int,
                     player_tricks_so_far: List[int],
                     high_trump_player_so_far: int) -> bool:
    """True iff the bidder has ALREADY scored enough to make the bid."""
    if player_tricks_so_far is None:
        return False
    return _ct_bidder_round_pts(bid_winner, player_tricks_so_far,
                                 high_trump_player_so_far) >= high_bid


# ─────────────────────────────────────────────────────────────────────────────
# ImprovedAI
# ─────────────────────────────────────────────────────────────────────────────

class ImprovedAI:
    def __init__(self, player_idx: int, flags: dict = None):
        self.player_idx = player_idx
        # flags: ablation toggles. Unset key => True => champion behaviour
        # (bit-identical to the validated faithful port). Set a key False to
        # disable that one situational rule for the ablation audit.
        self.flags = flags or {}

    # ── Discard (port of decideDiscard incl. v2.31.22 fiveCardDraw) ───────────
    def choose_discards(self, hand: List[Card], trump: Suit,
                        is_bid_winner: bool, bid_amount: int,
                        five_card_draw: bool = False) -> List[Card]:
        trumps = [c for c in hand if is_trump(c, trump)]
        offsuit = [c for c in hand if not is_trump(c, trump)]
        keep = list(trumps)

        if is_bid_winner and bid_amount >= 25:
            if len(trumps) >= 5 and offsuit:
                kings = [c for c in offsuit if c.rank == 'K']
                if kings:
                    keep.append(kings[0])
        elif is_bid_winner and offsuit:
            by_suit: Dict[Suit, List[Card]] = {}
            for c in offsuit:
                by_suit.setdefault(c.suit, []).append(c)
            best_per_suit = []
            for cards in by_suit.values():
                cards.sort(key=get_offsuit_rank, reverse=True)
                best_per_suit.append(cards[0])
            strong = [c for c in best_per_suit if c.rank == 'K']
            if strong and len(trumps) >= 4:
                keep.append(strong[0])

        if not keep and hand:
            # v2.31.22: non-bid-winner with zero trump + 5-card-draw rule → full redraw
            if five_card_draw and not is_bid_winner:
                return list(hand)

            def _val(c):
                return _tr(c, trump) + 100 if is_trump(c, trump) else get_offsuit_rank(c)
            keep = [max(hand, key=_val)]

        if len(keep) > 5:
            def _val2(c):
                return _tr(c, trump) if is_trump(c, trump) else get_offsuit_rank(c)
            keep.sort(key=_val2, reverse=True)
            keep = keep[:5]

        keep_ids = [id(k) for k in keep]
        return [c for c in hand if id(c) not in keep_ids]

    # ── Card play (port of chooseCardToPlay) ─────────────────────────────────
    def choose_card(self, state: GameState,
                    play_history: List[Tuple[int, Card]]) -> Card:
        player = self.player_idx
        trump = state.trump_suit
        hand = state.hands[player]
        ctrick = state.current_trick                 # List[(player, card)]
        trick = [c for (_, c) in ctrick]             # cards only (JS `trick`)
        leader = state.trick_leader
        trick_num = state.trick_num
        cards_played = state.cards_played
        bid_winner = state.bid_winner
        cards_drawn = state.cards_drawn
        known_oot = state.known_out_of_trump
        known_voids = state.known_voids or [{}, {}, {}, {}]

        led = trick[0] if trick else None
        playable = get_playable_cards(hand, trump, led)
        if len(playable) <= 1:
            return playable[0] if playable else hand[0]

        intel = build_player_intelligence(play_history, cards_played,
                                          known_voids, cards_drawn, trump)
        iplayers = intel['players']

        F = lambda k: self.flags.get(k, True)   # rule enabled unless set False
        Fon = lambda k: self.flags.get(k, False)  # OPT-IN rule: absent in champion

        def est(i):
            return iplayers[i]['estimatedTrumpRemaining'] or 0

        def play_lowest(cards):
            return min(cards, key=lambda c: (_tr(c, trump) + 200) if _is_trump(c, trump)
                       else get_offsuit_rank(c))

        is_leading = len(trick) == 0

        # ── Endgame point-budget DENY mode ───────────────────────────────
        # OPT-IN ('endgame_deny', default off → champion bit-identical).
        # Bidder-side: when the opponent is so close that any trick they win
        # ends the game (a normal made bid still loses because defenders
        # always score their tricks), abandon bid-efficiency and treat every
        # trick as must-win: take contestable tricks with the MINIMAL
        # sufficient card, never voluntarily concede, and when leading keep
        # control with the top trump so opponents cannot snatch a late trick.
        if Fon('endgame_deny') and state.team_scores is not None:
            _myt = player % 2
            if (bid_winner % 2) == _myt:                 # bidder side only
                _oppneed = state.winning_total - state.team_scores[1 - _myt]
                if _oppneed <= 10:                       # opp at 110+ (to 120)
                    if is_leading:
                        _tp = [c for c in playable if _is_trump(c, trump)]
                        _pool = _tp if _tp else playable
                        return max(_pool, key=lambda c: (_tr(c, trump) + 200)
                                   if _is_trump(c, trump)
                                   else get_offsuit_rank(c))
                    _ls = trick[0].suit
                    _best = trick[0]
                    for _c in trick[1:]:
                        if card_beats(_c, _best, trump, _ls):
                            _best = _c
                    _w = trick_winner(trick, trump, leader)   # player idx
                    _opp_winning = (_w % 2) != _myt
                    _wins = [c for c in playable
                             if card_beats(c, _best, trump, _ls)]
                    if _opp_winning and _wins:
                        return play_lowest(_wins)            # min sufficient
                    return play_lowest(playable)             # preserve strength

        # partner currently winning?
        partner_winning_now = False
        if not is_leading:
            cw = leader
            wc = trick[0]
            for i in range(1, len(trick)):
                if card_beats(trick[i], wc, trump, trick[0].suit):
                    wc = trick[i]
                    cw = (leader + i) % 4
            partner_winning_now = (cw % 2) == (player % 2)
            if self.flags.get('cutthroat'):
                partner_winning_now = False  # no partner concept

        # ── DEFENDER CASH PROVABLY-BOSS A♥ (FIX v2.31.43) ────────────────────
        # is_card_boss only proves boss when EVERY higher trump is in
        # cards_played. A♥ (rank 100) is beaten only by 5-of-trump (102) and
        # J-of-trump (101). When the J-of-trump is in the KITTY / a discard
        # it is never in cards_played, so is_card_boss(A♥) is forever False
        # and a defender who holds A♥ against a bidder leading trump every
        # trick dribbles it onto the dead last trick (user-reported v2.31.42,
        # round-summary screenshot). Here a DEFENDER who is FOLLOWING and can
        # WIN the current trick with A♥ — while the BIDDING SIDE is currently
        # winning it (real steal value) — cashes A♥ now, but ONLY when it is
        # PROVABLY unbeatable for THIS trick: 5-trump gone AND J-trump gone
        # ("gone" = in cards_played OR in my own hand), OR every seat that
        # acts after me is KNOWN trump-void (cannot over-trump regardless).
        # Airtight: A♥ definitely wins the trick in every triggering case;
        # the only change is cashing it EARLY (tempo + a real shot at a
        # second defensive trick via the lead) instead of wasting it T5.
        # Flag-gated, default-ON; off:defender_cash_boss_ah reverts.
        _is_defender_now = ((player != bid_winner) if self.flags.get('cutthroat')
                            else (player % 2) != (bid_winner % 2))
        if (F('defender_cash_boss_ah') and not is_leading
                and not partner_winning_now
                and _is_defender_now):
            _ah = next((c for c in playable
                        if c.rank == 'A' and c.suit == HEARTS), None)
            if _ah is not None and trick_winner(
                    _pad4(trick + [_ah], trump if F('safe_pad4') else None), trump, leader) == player:
                _tv = trump.value
                _played_ids = {cid(c) for c in cards_played}
                _hand_ids = {cid(c) for c in hand}
                _gone = lambda _id: _id in _played_ids or _id in _hand_ids
                _five_gone = _gone(f"5{_tv}")
                _jack_gone = _gone(f"J{_tv}")
                _after = [(leader + pos) % 4
                          for pos in range(len(trick) + 1, 4)]
                # No one acts after me → A♥ winning the test trick IS the
                # full proof. Otherwise every later seat must be unable to
                # over-trump: known trump-void, OR both cards that beat A♥
                # (5/J of trump) are provably gone (played or in my hand).
                #
                # OPT-IN looser trigger (defender_cash_ah_jlate): by trick 4
                # a live J-of-trump (2nd-highest trump) would almost always
                # have been played; if 5-trump is gone and it is trick 4+,
                # treat J as effectively dead even though unseen, so A♥ is
                # cashed now (win + take the lead → shot at a 2nd defensive
                # trick) instead of dribbling it to the dead trick 5. A♥
                # already beats every card on the table (trick_winner check
                # above); the only residual risk is a later-seat J over-
                # trump, which this bets against. Absent in champion (Fon →
                # bit-identical); the rig measures whether the bet is +EV.
                _jlate_ok = (F('defender_cash_ah_jlate')
                             and _five_gone and trick_num >= 4)
                _provably_boss = (not _after) or all(
                    (known_voids[idx].get('trump') is True)
                    or (_five_gone and _jack_gone)
                    or _jlate_ok
                    for idx in _after)
                if _provably_boss:
                    return _ah

        # CUTTHROAT_SAVE_5_LEAD (opt-in, user-derived 2026-05-29). MUST be
        # placed BEFORE the BOSS CARD priority loop below — otherwise the
        # 5 of trump (always boss, rank 102) triggers the boss-leading path
        # and returns before this rule can fire. Four variants test the
        # user's principle: bidder holding the 5 of trump + >=1 other trump
        # + >=1 offsuit should NOT lead the 5 trick 1. Lead an offsuit
        # instead; reserve the 5 for late-position bonus capture or to take
        # a defender's boss. Champion bit-identical (all four default-off
        # via Fon).
        if (self.flags.get('cutthroat') and is_leading
                and player == bid_winner):
            _ct_trumps = [c for c in playable if _is_trump(c, trump)]
            _ct_nt = [c for c in playable if not _is_trump(c, trump)]
            if (_ct_trumps and _ct_nt and len(_ct_trumps) >= 2
                    and any(_tr(c, trump) == 102 for c in _ct_trumps)):
                if Fon('cutthroat_save_5_t1lo') and trick_num == 1:
                    return min(_ct_nt, key=get_offsuit_rank)
                if Fon('cutthroat_save_5_t1hi') and trick_num == 1:
                    return max(_ct_nt, key=get_offsuit_rank)
                if Fon('cutthroat_save_5_t12lo') and trick_num <= 2:
                    return min(_ct_nt, key=get_offsuit_rank)
                if Fon('cutthroat_save_5_t12hi') and trick_num <= 2:
                    return max(_ct_nt, key=get_offsuit_rank)

        # ── CT-SETLOCKED-SAVE-LAST-TRUMP ──────────────────────────────────────
        # SET-LOCKED bidder last-trump preservation (cutthroat). When ALL hold:
        #   - cutthroat mode
        #   - I am the bidder
        #   - I am set-locked this round (bid mathematically unreachable)
        #   - I have EXACTLY one trump card remaining
        #   - Current trick was led with non-trump
        #   - Current trick is being won by a non-self defender with non-trump
        #   - I have at least one legal non-trump play
        # → play lowest non-trump and PRESERVE the last trump. Rationale: the
        # bidder is mathematically set; winning this trick adds 5 to the
        # set-locked column (worth 0 toward bid). Saving the trump to over-
        # trump the defenders' expected ruff next trick denies 5 pts to a
        # defender (typically the game leader). +5 denial > +5 vanity trick.
        # MUST sit BEFORE the BOSS CARD priority loop below — otherwise a
        # last-trump that is the 5/J of trump (boss) returns from the loop
        # and the rule never fires.
        if (Fon('ct_setlocked_save_last_trump')
                and self.flags.get('cutthroat')
                and player == bid_winner
                and not is_leading
                and trick):
            _pt = state.player_tricks
            _hp = state.high_trump_player
            _hb = state.high_bid
            _set_lk = _ct_set_locked(_hb, bid_winner, _pt, _hp, trick_num)
            if _set_lk:
                _my_trumps = [c for c in playable if _is_trump(c, trump)]
                _my_nt    = [c for c in playable if not _is_trump(c, trump)]
                _led_nt = not _is_trump(trick[0], trump)
                if (len(_my_trumps) == 1 and _my_nt and _led_nt):
                    # current winner seat + their card (must be non-self,
                    # non-trump winner — i.e. a defender holding the trick
                    # with offsuit). Compute mirroring later block.
                    _cw = leader
                    _wc = trick[0]
                    for _i in range(1, len(trick)):
                        if card_beats(trick[_i], _wc, trump, trick[0].suit):
                            _wc = trick[_i]
                            _cw = (leader + _i) % 4
                    _winner_non_trump = not _is_trump(_wc, trump)
                    if _cw != player and _winner_non_trump:
                        return min(_my_nt, key=get_offsuit_rank)

        # ── STRATEGIC PRIORITY #1: BOSS CARD ─────────────────────────────────
        if not partner_winning_now:
            for card in playable:
                if not is_card_boss(card, cards_played, trump):
                    continue
                if is_leading:
                    # ENDGAME LEAD-BOSS (opt-in #32, default off → champion
                    # unchanged). A defender normally saves a boss & leads
                    # offsuit to drain bidder trump. But in the endgame when
                    # the BIDDING TEAM is already trump-void, draining is
                    # moot — lead the boss to win now AND keep the lead for
                    # the next trick (shot at +1 trick via lead control).
                    _eg_is_def = ((player != bid_winner)
                                  if self.flags.get('cutthroat')
                                  else (player % 2) != (bid_winner % 2))
                    if (F('endgame_lead_boss')   # SHIPPED v2.31.30 (strict): default-ON
                            and _eg_is_def
                            and trick_num >= 4):
                        if self.flags.get('cutthroat'):
                            _opps = [s for s in range(4) if s != player]
                        else:
                            _bteam = bid_winner % 2
                            _opps = [s for s in range(4) if s % 2 == _bteam]
                        # champion = STRICT (deduction-only); est is opt-in variant
                        _strict = not self.flags.get('endgame_lead_boss_est', False)
                        def _elv(s):
                            if known_voids[s].get('trump') is True:
                                return True
                            return (not _strict) and est(s) == 0
                        if all(_elv(s) for s in _opps):
                            return card   # lead the boss now (endgame)
                    # defender → don't lead boss, fall to defender-leading
                    if _eg_is_def:
                        break
                    # partner-of-bidder boss-save (bidder has trump, opps out)
                    p_opp1 = (bid_winner + 1) % 4
                    p_opp2 = (bid_winner + 3) % 4
                    is_partner_of_bidder = player != bid_winner
                    bidder_trump_est = est(bid_winner)
                    bidder_void = known_voids[bid_winner].get('trump') is True
                    opps_out = est(p_opp1) == 0 and est(p_opp2) == 0
                    offs = [c for c in playable if _tr(c, trump) < 0]
                    if (not self.flags.get('cutthroat')
                            and F('bidder_boss_partner_save')
                            and is_partner_of_bidder and not bidder_void
                            and bidder_trump_est > 0 and opps_out and offs):
                        return min(offs, key=get_offsuit_rank)
                    # partner weak (drew 4) + enemies stronger (drew ≤3)
                    partner_idx = (bid_winner + 2) % 4
                    opp1 = (bid_winner + 1) % 4
                    opp2 = (bid_winner + 3) % 4
                    my_tc = len([c for c in playable if _tr(c, trump) >= 0])
                    if (not self.flags.get('cutthroat')
                            and F('bidder_boss_weak_partner_save')
                            and cards_drawn and my_tc <= 2 and cards_drawn[partner_idx] >= 4
                            and cards_drawn[opp1] <= 3 and cards_drawn[opp2] <= 3):
                        offs2 = [c for c in playable if _tr(c, trump) < 0]
                        if offs2:
                            return min(offs2, key=get_offsuit_rank)
                    return card
                else:
                    test = _pad4(trick + [card], trump if F('safe_pad4') else None)
                    if trick_winner(test, trump, leader) == player:
                        # PARTNER BOSS-SAVE (bidder's partner, enemy trump low)
                        is_partner = player == (bid_winner + 2) % 4
                        if (not self.flags.get('cutthroat')
                                and F('following_partner_boss_save')
                                and is_partner and trick_num < 5):
                            o1 = (bid_winner + 1) % 4
                            o2 = (bid_winner + 3) % 4
                            if est(o1) + est(o2) <= 1:
                                break
                        # all remaining players void → min-win, save boss
                        remaining_after = [(leader + pos) % 4
                                           for pos in range(len(trick) + 1, 4)]
                        all_void = (len(remaining_after) == 0 or all(
                            (known_voids[idx].get('trump') is True) or est(idx) == 0
                            for idx in remaining_after))
                        if F('following_all_remaining_void') and all_void:
                            break
                        # 2nd-man boss-save on offsuit lead (any role)
                        led_offsuit = _tr(trick[0], trump) < 0
                        my_tc2 = len([c for c in playable if _tr(c, trump) >= 0])
                        if (F('following_2nd_man_offsuit_boss_save')
                                and len(trick) == 1 and led_offsuit and my_tc2 >= 2):
                            break
                        # HOLD-UP (opt-in #30): 2nd-man DEFENDER, offsuit
                        # led, NO low trump to ruff cheap (all trumps high) +
                        # a non-trump to hold up with → don't waste a high/
                        # boss trump on a junk trick; hold up so declarer's
                        # side must overspend trump to take it (or the
                        # offsuit follow wins anyway). Extends the ≥2-trump
                        # offsuit-boss-save to the only/all-high-trump case.
                        _hd_is_def = ((player != bid_winner)
                                      if self.flags.get('cutthroat')
                                      else (player % 2) != (bid_winner % 2))
                        if (F('holdup_2nd_def')   # SHIPPED v2.31.28 (hd:hi98): default-ON
                                and len(trick) == 1 and led_offsuit
                                and _hd_is_def):
                            _hd = self.flags.get
                            _trk = [_tr(c, trump) for c in playable
                                    if _tr(c, trump) >= 0]
                            _nt = any(_tr(c, trump) < 0 for c in playable)
                            _thr = 97 if _hd('holdup_hi97') else 98
                            _allhi = bool(_trk) and min(_trk) >= _thr
                            _force = True
                            if _hd('holdup_force'):
                                _aft = [(leader + p) % 4
                                        for p in range(len(trick) + 1, 4)]
                                if self.flags.get('cutthroat'):
                                    _force = any(s == bid_winner and est(s) > 0
                                                 for s in _aft)
                                else:
                                    _force = any((s % 2) == (bid_winner % 2)
                                                 and est(s) > 0 for s in _aft)
                            if _nt and _allhi and _force:
                                break
                        # 2nd-man boss renege on low trump lead
                        led_rank_chk = _tr(trick[0], trump)
                        if (not self.flags.get('cutthroat')
                                and F('following_2nd_man_low_trump_renege')
                                and len(trick) == 1 and 0 <= led_rank_chk < 90):
                            third_idx = (leader + 2) % 4
                            partner_idx = (player + 2) % 4
                            third_void = (known_voids[third_idx].get('trump') is True
                                          or est(third_idx) == 0)
                            if third_void and est(partner_idx) >= 1:
                                break
                        return card
                    # boss can't beat current trick → keep scanning
                    continue

        # ── BIDDER LEADING ───────────────────────────────────────────────────
        is_bidder = player == bid_winner
        if is_bidder and is_leading:
            trumps = [c for c in playable if _is_trump(c, trump)]
            non_trumps = [c for c in playable if not _is_trump(c, trump)]
            opp1 = (player + 1) % 4
            opp2 = (player + 3) % 4
            opps_est_out = est(opp1) == 0 and est(opp2) == 0
            all_known_out = (known_oot is not None and
                             all(known_oot[i] for i in range(4) if i != player))
            if F('bidder_after_void_lead') and trumps and (all_known_out or opps_est_out):
                return min(trumps, key=lambda c: _tr(c, trump))
            # BIDDER_PARTNER_FLOOR_LEAD (opt-in): bidder leading with
            # multiple trumps, partner's known min_trump_rank floor is
            # high enough that partner's floor card is GUARANTEED to win
            # the trick (every higher trump is accounted for — mine or
            # already played). Lead my LOWEST trump instead of my
            # highest so partner cashes their known high trump here
            # while I conserve mine for a future lead. User-derived
            # expert play 2026-05-20: I led 5, partner played Q →
            # floor ≥98. With J in my hand AND 5 played, partner's K is
            # still beatable by A♥ (might be in opp), but partner's
            # A♥-floor with J+5 accounted for IS unbeatable. So gate on
            # "all over-trumps for partner_floor are accounted for".
            partner_idx = (player + 2) % 4
            partner_floor = known_voids[partner_idx].get('min_trump_rank', 0)
            if (not self.flags.get('cutthroat')
                    and Fon('bidder_partner_floor_lead')
                    and trumps and len(trumps) >= 2
                    and partner_floor >= 98):
                my_ids = {cid(c) for c in hand}
                played_ids = {cid(c) for c in cards_played}
                tv = trump.value
                # Cards that could over-trump partner's floor card.
                over_cards = []
                if partner_floor < 102: over_cards.append(f"5{tv}")
                if partner_floor < 101: over_cards.append(f"J{tv}")
                if partner_floor < 100: over_cards.append("A♥")
                if partner_floor < 99 and trump != HEARTS:
                    over_cards.append(f"A{tv}")
                if partner_floor < 98: over_cards.append(f"K{tv}")
                floor_safe = all(c in my_ids or c in played_ids for c in over_cards)
                if floor_safe:
                    return min(trumps, key=lambda c: _tr(c, trump))
            # BIDDER_LOWTRUMP_DUMP (opt-in; user-derived 2026-05-22). NARROW:
            # I have EXACTLY 1 trump left AND it is a low-number trump
            # (rank ≤ 87 — anything in the 2-10 band, not Q/K/A/J/5)
            # AND there's at least one unaccounted-for higher trump.
            # Leading this trump is a near-guaranteed loss; lead my
            # highest offsuit instead to try to steal a trick.
            if (F('bidder_lowtrump_dump') and len(trumps) == 1 and non_trumps):
                my_trump_rank = _tr(trumps[0], trump)
                if my_trump_rank <= 87:
                    highest_remaining = get_highest_remaining_trump(cards_played, trump)
                    if my_trump_rank < highest_remaining:
                        return max(non_trumps, key=get_offsuit_rank)
            if (F('bidder_endgame_trump_timing')
                    and trick_num >= 4 and len(trumps) == 1 and len(non_trumps) == 1):
                if self.flags.get('cutthroat'):
                    opp_idx = [i for i in range(4) if i != player]
                else:
                    opp_idx = [i for i in range(4)
                               if i != player and i != (player + 2) % 4]
                opp_likely = False
                for oi in opp_idx:
                    oi_trump_played = len([c for (pi, c) in play_history
                                           if pi == oi and _tr(c, trump) >= 0])
                    if estimate_opponent_trump(cards_drawn[oi], oi_trump_played) >= 1:
                        opp_likely = True
                        break
                if opp_likely and trick_num == 4:
                    return non_trumps[0]
                return trumps[0]
            # H-A (opt-in bidder_lead_low_trump): when the bidder is
            # leading and the champion would lead a trump, lead the
            # LOWEST trump instead (conserve boss-class high trump for
            # later). Covers BOTH champion lead-high paths below
            # (>=3 → return max, and >=1 → return highest_trump).
            # TESTED 2026-05-17, NO-SHIP: reachable (5153 changes/1500
            # games) but screen 30k deals win 49.41% z=-2.91 SIGNIF
            # NEGATIVE. Kept opt-in/default-off (champion bit-identical)
            # purely as a documented dead-end; champion leads HIGH.
            if Fon('bidder_lead_low_trump') and trumps:
                return min(trumps, key=lambda c: _tr(c, trump))
            if len(trumps) >= 3:
                return max(trumps, key=lambda c: _tr(c, trump))
            elif len(trumps) >= 1:
                highest_trump = max(trumps, key=lambda c: _tr(c, trump))
                if non_trumps:
                    # bidder_trump_save_lead REMOVED (v2.31.34) — ablation
                    # held-out +0.38pt z=+2.62 (replicated) proved the
                    # "lead offsuit when top trump not boss" rule
                    # net-negative. Champion now leads its trump.
                    # NOTE: a bidder_lowtrump_offsuit rule was tested here
                    # (narrow B + broad A) but proved STRUCTURALLY DEAD —
                    # bidder_after_void_lead (line ~507) returns first in
                    # every reachable case, so this site is never hit
                    # (0/1500 games instrumented). Testing the user's
                    # low-trump-lead idea requires ablating/altering
                    # bidder_after_void_lead, not a new rule here.
                    return highest_trump
                return highest_trump
            # bidder leading w/ no trump → JS goes Monte Carlo; approximate:
            if non_trumps:
                return min(non_trumps, key=get_offsuit_rank)
            return play_lowest(playable)

        # ── DEFENDER LEADING ─────────────────────────────────────────────────
        is_defender = not is_bidder
        if is_defender and is_leading:
            trumps = [c for c in playable if _is_trump(c, trump)]
            non_trumps = [c for c in playable if not _is_trump(c, trump)]
            partner_idx = (player + 2) % 4
            opp1 = (player + 1) % 4
            opp2 = (player + 3) % 4
            partner_trump_est = est(partner_idx)
            opps_have_trump = est(opp1) > 0 or est(opp2) > 0
            if (not self.flags.get('cutthroat')
                    and F('defender_partner_trump_load')
                    and partner_trump_est >= 3 and trumps and non_trumps and opps_have_trump):
                return min(trumps, key=lambda c: _tr(c, trump))
            if non_trumps:
                return min(non_trumps, key=get_offsuit_rank)
            if trumps:
                return min(trumps, key=lambda c: _tr(c, trump))

        # ── ENHANCED FOLLOWING ───────────────────────────────────────────────
        if len(trick) > 0:
            led_card = trick[0]
            my_position = len(trick)
            my_trumps = [c for c in playable if _is_trump(c, trump)]
            my_offsuit = [c for c in playable if not _is_trump(c, trump)]

            cw = leader
            wc = trick[0]
            for i in range(1, len(trick)):
                if card_beats(trick[i], wc, trump, trick[0].suit):
                    wc = trick[i]
                    cw = (leader + i) % 4
            winning_card = wc
            my_team = player % 2
            partner_winning = (cw % 2) == my_team
            if self.flags.get('cutthroat'):
                partner_winning = False  # no partner concept; fall through to opp-winning branch

            bidder_led = leader == bid_winner
            signal = (bidder_led and
                      is_bidder_signaling(led_card, trump, cards_played, trick_num))
            if (not self.flags.get('cutthroat')
                    and F('signal_3rd_man_high')
                    and signal and my_position == 2 and my_trumps):
                high_trump = max(my_trumps, key=lambda c: _tr(c, trump))
                if trick_winner(_pad4(trick + [high_trump], trump if F('safe_pad4') else None), trump, leader) == player:
                    return high_trump

            if partner_winning:
                voids = known_voids
                opp_after = False
                all_opps_void_trump = True
                all_opps_no_threat = True
                led_suit = trick[0].suit
                for pos in range(my_position + 1, 4):
                    pidx = (leader + pos) % 4
                    if (pidx % 2) != my_team:
                        opp_after = True
                        ov = voids[pidx] if pidx < len(voids) and voids[pidx] else {}
                        # A reneging opp is effectively trump-void iff every
                        # trump they could still hold is PROVABLY GONE. Old
                        # code only checked "all in MY hand" — so a renege
                        # whose only possible trump was already PLAYED was
                        # still treated as a live threat and the boss 5/J/AH
                        # got dumped on an already-won trick (user-reported,
                        # round-summary T3). Fix: also count played cards as
                        # gone. Logically safe — only treats them as void
                        # when they provably cannot beat our winner.
                        _rt = ov.get('trump') == 'reneging'
                        _pt = ov.get('possibleTrump', [])
                        if F('partner_winning_renege_prune'):
                            renege_all_mine = _rt and all(
                                any(cid(c) == pid for c in hand)
                                or any(cid(c) == pid for c in cards_played)
                                for pid in _pt)
                        else:
                            renege_all_mine = _rt and all(
                                any(cid(c) == pid for c in hand)
                                for pid in _pt)
                        eff_void = ov.get('trump') is True or renege_all_mine
                        if not eff_void:
                            all_opps_void_trump = False
                        void_led = bool(ov.get(led_suit.value))
                        if not void_led or not eff_void:
                            all_opps_no_threat = False
                if not opp_after:
                    return play_lowest(playable)
                if _is_trump(winning_card, trump):
                    wtr = _tr(winning_card, trump)
                    if wtr >= 97:
                        return play_lowest(playable)
                    if all_opps_void_trump:
                        return play_lowest(playable)
                    if F('partner_low_trump_signal_response') and my_trumps:
                        ht = max(my_trumps, key=lambda c: _tr(c, trump))
                        # Never burn the 5 of trump (rank 102, absolute
                        # boss — unbeatable) to respond to a signal when
                        # partner already leads the trick: the 5 is a
                        # guaranteed FUTURE trick, so spending it to
                        # over-secure a trick partner already holds is
                        # strictly dominated. (user-reported T3)
                        if F('partner_save_boss5') and _tr(ht, trump) >= 102:
                            return play_lowest(playable)
                        # partner_signal_overtake_guard (opt-in; flag-absent
                        # → unchanged, bit-identical). Overtaking a partner
                        # who is ALREADY winning with trump only helps if our
                        # high trump can actually SECURE the trick against
                        # every later opponent. If a not-provably-void later
                        # opponent could still hold a trump ABOVE ours, then:
                        # they over-trump us anyway (we lose either way), OR
                        # they cannot (partner already had it won) — in both
                        # cases burning our boss here is strictly dominated by
                        # reneging it for a future trick. (user-reported:
                        # North played A♥ over partner's winning 8♥ while a
                        # possible East J♥ beats A♥ regardless.)
                        if F('partner_signal_overtake_guard') and not all_opps_void_trump:
                            _tv = trump.value
                            if trump in (Suit.HEARTS, Suit.DIAMONDS):
                                _rk = ['5', 'J', 'A', 'K', 'Q', '10', '9',
                                       '8', '7', '6', '4', '3', '2']
                            else:
                                _rk = ['5', 'J', 'A', 'K', 'Q', '2', '3',
                                       '4', '6', '7', '8', '9', '10']
                            _seen = ({cid(c) for c in cards_played}
                                     | {cid(c) for c in hand}
                                     | {cid(c) for c in trick})
                            _all_t = [Card(r, trump) for r in _rk]
                            if trump != Suit.HEARTS:
                                _all_t.append(Card('A', Suit.HEARTS))
                            _best_unseen = max(
                                (_tr(c, trump) for c in _all_t
                                 if cid(c) not in _seen), default=-1)
                            if _best_unseen > _tr(ht, trump):
                                return play_lowest(playable)
                        if trick_winner(_pad4(trick + [ht], trump if F('safe_pad4') else None), trump, leader) == player:
                            return ht
                    return play_lowest(playable)
                else:
                    if all_opps_no_threat:
                        return play_lowest(playable)
                    # partner_off_boss_save (opt-in; flag-absent → unchanged,
                    # bit-identical). Do NOT ruff partner's winning OFFSUIT
                    # card when it is the BOSS of the led suit (every higher
                    # led-suit card is played or in my hand) AND every
                    # remaining opp is PROVABLY trump-void (cannot over-ruff).
                    # In 45s you may always trump instead of following, so
                    # the ONLY airtight safety is provable trump-void — not
                    # "forced to follow". Partner's trick is then guaranteed;
                    # ruffing only burns a trump and steals partner's trick
                    # (user-reported v2.31.45: bidder led boss K♦, partner
                    # ruffed 7♠ though East was deducibly trump-void). The
                    # j_trump_dump_void inference makes this fire on that
                    # case (East showed only J-trump on the 5-trump lead).
                    if (F('partner_off_boss_save') and all_opps_void_trump):
                        _ls = trick[0].suit
                        _wr = get_offsuit_rank(winning_card)
                        _hi_out = False
                        for _r in ('2', '3', '4', '5', '6', '7', '8', '9',
                                   '10', 'J', 'Q', 'K', 'A'):
                            _c = Card(_r, _ls)
                            if _is_trump(_c, trump):
                                continue
                            if (get_offsuit_rank(_c) > _wr
                                    and cid(_c) != cid(winning_card)
                                    and not any(cid(x) == cid(_c)
                                                for x in cards_played)
                                    and not any(cid(x) == cid(_c)
                                                for x in hand)):
                                _hi_out = True
                                break
                        if not _hi_out:
                            return play_lowest(playable)
                    if my_trumps:
                        return min(my_trumps, key=lambda c: _tr(c, trump))
                    return play_lowest(playable)

            can_beat = any(
                trick_winner(_pad4(trick + [c], trump if F('safe_pad4') else None), trump, leader) == player
                for c in playable)
            if not can_beat:
                return play_lowest(playable)

            # MIN-WIN WHEN ALL-AFTER HARD-VOID (SHIPPED v2.31.27 = champion
            # default; ablatable via off:minwin_after_void). STRICT /
            # deduction-only: only knownVoids[idx].trump===true counts (the
            # estimate-based variant tested mildly negative and is NOT in the
            # champion). If every seat after me is KNOWN trump-void no one can
            # overtrump — bank the trick with the CHEAPEST winner, conserve
            # high trump for a later trick / the +5 high-trump bonus.
            if F('minwin_after_void'):
                after = [(leader + pos) % 4
                         for pos in range(my_position + 1, 4)]
                if after and all(known_voids[idx].get('trump') is True
                                 for idx in after):
                    winners = [c for c in playable
                               if trick_winner(_pad4(trick + [c], trump if F('safe_pad4') else None), trump,
                                               leader) == player]
                    if winners:
                        return min(winners,
                                   key=lambda c: _tr(c, trump)
                                   if _is_trump(c, trump)
                                   else get_offsuit_rank(c))

            # ── CUTTHROAT COALITION + NICKEL-GRAB ────────────────────────
            # Gated on flags.cutthroat (no-op in partner mode). Each rule
            # opts in via its OWN flag — default OFF so the stripped
            # champion-cutthroat baseline (Chunk A) is bit-identical and
            # the cutthroat-coalition-* / cutthroat-nickel-grab challengers
            # are measurable deltas.
            #
            #   N1 (n1_nickel_grab): set/made is LOCKED (bidder can no
            #       longer be set or has already made) → switch from
            #       coalition mode to point-greedy. Take the cheapest
            #       winning card; if the cheapest winner is a top-3 trump
            #       (rank >= 100: 5 of trump, J of trump, A♥ when trump
            #       != hearts), SAVE it and play_lowest instead. Lesson
            #       from pass-1 C1 sanity (commit 3f26177): aggressive
            #       defender takes that burn top trump are net-negative;
            #       nickel-grab restricts the "take" to free tricks.
            #       When N1 fires (locked), C1 and C2's set-the-bidder
            #       purpose is moot, so C1/C2 are gated `and not _locked`
            #       and N1 sits FIRST so its early-return preempts them
            #       in the locked regime.
            #
            #   C2 (dont_overtake): another DEFENDER currently leads the
            #       trick AND the BIDDER HAS ALREADY PLAYED → don't burn
            #       cards to overtake the teammate-of-convenience; cheap-
            #       low and let them have it. Conserve high cards for
            #       tricks the BIDDER might win.
            #       PASS-1 BUG (v1, commit 550ad35): C2 fired even when the
            #       bidder hadn't played yet — so the next defender played
            #       low, and the bidder then over-trumped cheaply, having
            #       been handed a card that could have beaten them. The
            #       symmetric A-vs-B test (commit 61ebe61) showed bidders
            #       MORE successful (-1.36pt set-rate, z=-3.36; -2.02pt
            #       at 15-bids specifically). PASS-2 FIX: require the
            #       bidder to have already committed a card before C2's
            #       conservative low-play applies.
            #   C1 (take_from_bidder): the BIDDER currently leads the
            #       trick → play the CHEAPEST card that beats the current
            #       winner. Both rules skip if set/made is mathematically
            #       LOCKED (no upside left in the round) — N1 owns locked.
            # Order: N1 first (point-greedy when locked), then C2
            # (conservative default), then C1 (affirmative take).
            if (self.flags.get('cutthroat') and not is_leading
                    and player != bid_winner):
                _pt = state.player_tricks
                _hp = state.high_trump_player
                _hb = state.high_bid
                _bw = bid_winner
                _set_lk = _ct_set_locked(_hb, _bw, _pt, _hp, trick_num)
                _made_lk = _ct_made_locked(_hb, _bw, _pt, _hp)
                _locked = _set_lk or _made_lk
                # trick[i] is the card played by seat (leader + i) % 4 —
                # so the bidder has played iff _bw appears in that span.
                _bidder_has_played = _bw in [(leader + i) % 4
                                             for i in range(len(trick))]

                # ── L1 / L2 / L3 score-aware triggers ──────────────────────
                # Read pre_round_scores (4-vec of game totals at round start)
                # set by cutthroat_runner / game_runner. None in round-only
                # harnesses → all three L-rules become no-ops (safe default).
                _prs = state.pre_round_scores
                # L3 — bidder making this bid wins them the game (>=120):
                # switch to max-aggression. _locked overrides L3 (if the
                # bid is already set or made, max-aggression is moot —
                # N1 already governs the post-decided regime).
                _l3 = False
                if (Fon('cutthroat_l3_bidder_winning_game')
                        and _prs is not None and not _locked):
                    _l3 = (_prs[_bw] + _hb) >= state.winning_total
                # L1 — I am the runaway LEADER (game-so-far) by threshold:
                # soften C1 — take only if cheapest winner is NOT top-3.
                # Configurable thresholds: cutthroat_l1_min (my min score) and
                # cutthroat_l1_gap (gap above 2nd-best). Both must hold.
                _l1 = False
                if (Fon('cutthroat_l1_leader_self_nickel')
                        and _prs is not None and not _locked):
                    _min = self.flags.get('cutthroat_l1_min', 100)
                    _gap = self.flags.get('cutthroat_l1_gap', 40)
                    _others = max(_prs[s] for s in range(4) if s != player)
                    _l1 = (_prs[player] >= _min
                           and (_prs[player] - _others) >= _gap)
                # L2 — ANOTHER DEFENDER (not me, not bidder) is the runaway
                # leader by threshold. Effect: when CW is that leader (a
                # fellow defender), still TAKE (relax C2) to deny them. Also
                # extends C1's reach to "take from leader-defender" too.
                _l2 = False
                _l2_leader_seat = -1
                if (Fon('cutthroat_l2_dont_help_leader')
                        and _prs is not None and not _locked):
                    _min = self.flags.get('cutthroat_l2_min', 100)
                    _gap = self.flags.get('cutthroat_l2_gap', 40)
                    # find the highest-scoring DEFENDER (excluding me & bidder)
                    _def_others = [s for s in range(4)
                                   if s != player and s != _bw]
                    if _def_others:
                        _lead_def = max(_def_others, key=lambda s: _prs[s])
                        # next-highest-scoring of EVERYONE else (the gap basis)
                        _rest = [_prs[s] for s in range(4) if s != _lead_def]
                        _2nd = max(_rest)
                        if (_prs[_lead_def] >= _min
                                and (_prs[_lead_def] - _2nd) >= _gap):
                            _l2 = True
                            _l2_leader_seat = _lead_def

                # N1 — nickel-grab when set/made is mathematically LOCKED.
                # Coalition (C1+C2) is moot here: the bidder's contract is
                # decided. Switch to point-greedy: take cheap free tricks,
                # but NEVER burn a top-3 trump (rank >= 100) to do so.
                # _tr(c, trump) handles the A♥-when-trump=hearts case
                # correctly (it becomes A-of-trump at rank 99 < 100).
                if Fon('cutthroat_n1_nickel_grab') and _locked:
                    _winners = [c for c in playable
                                if trick_winner(
                                    _pad4(trick + [c],
                                          trump if F('safe_pad4') else None),
                                    trump, leader) == player]
                    if not _winners:
                        return play_lowest(playable)
                    _lo_win = min(_winners,
                                  key=lambda c: _tr(c, trump)
                                  if _is_trump(c, trump)
                                  else get_offsuit_rank(c))
                    if _is_trump(_lo_win, trump) and _tr(_lo_win, trump) >= 100:
                        # cheapest winner is a top-3 trump — save it.
                        return play_lowest(playable)
                    return _lo_win
                # D1 — defender ruffs a fellow-defender's offsuit lead BEFORE
                # the bidder plays (opt-in). Covers the pre-bidder-play window
                # that C1 (bidder currently winning) and C2 (bidder already
                # played) leave uncovered: a defender leads offsuit, no one
                # has ruffed yet, and unless I ruff, the bidder over-trumps
                # and steals the trick. User observation: "when West leads
                # offsuit in cutthroat, nobody throws trump at all, giving me
                # a free trick." Action: cheapest winning trump (same pattern
                # as C1). LATE variant additionally gates on trick_num >= 2.
                # Skip if set is locked (N1 owns the locked regime).
                if (Fon('cutthroat_d1_ruff_defender_offsuit_lead')
                        and not _set_lk
                        and not _is_trump(trick[0], trump)
                        and leader != _bw
                        and not _bidder_has_played
                        and any(_is_trump(c, trump) for c in playable)):
                    _d1_late_ok = (
                        not Fon('cutthroat_d1_late_only')
                        or trick_num >= 2)
                    if _d1_late_ok:
                        _d1_trumps = [c for c in playable
                                      if _is_trump(c, trump)]
                        _d1_winners = [c for c in _d1_trumps
                                       if trick_winner(
                                           _pad4(trick + [c],
                                                 trump if F('safe_pad4')
                                                 else None),
                                           trump, leader) == player]
                        if _d1_winners:
                            return min(_d1_winners,
                                       key=lambda c: _tr(c, trump))
                # CT-B3-TAKE-OVER-FELLOW (challenger; opt-in flag, default
                # OFF in champion). Replays the ORIGINAL v2.31.100 JS
                # behavior where B+3 (defender clockwise-before bidder,
                # plays 4th) UNCONDITIONALLY takes the trick with the
                # cheapest winner on a bidder offsuit lead, EVEN when a
                # fellow defender is already winning. v2.31.104 JS adds
                # a "!_ctFellowDefenderWinning" gate (which in Python is
                # already the natural behavior — C2 below fires when a
                # fellow defender is winning and bidder has played, so
                # B+3 just plays_lowest). To MEASURE the cost of the OLD
                # over-trumping behavior we add this rule as opt-in: when
                # the flag is ON, B+3 takes-over-fellow; when OFF (champion)
                # the existing C2/C1 flow handles it correctly. A neutral
                # rig result confirms the JS gate is zero-cost (trust-fix
                # ship); a negative rig (B3-OVER-FELLOW worse than champion)
                # confirms the JS gate is a real improvement.
                if (Fon('cutthroat_b3_take_over_fellow')
                        and my_position == 3
                        and leader == _bw
                        and not _is_trump(trick[0], trump)
                        and cw != player
                        and not _set_lk):
                    _b3_winners = [c for c in playable
                                   if trick_winner(
                                       _pad4(trick + [c],
                                             trump if F('safe_pad4') else None),
                                       trump, leader) == player]
                    if _b3_winners:
                        return min(_b3_winners,
                                   key=lambda c: _tr(c, trump)
                                   if _is_trump(c, trump)
                                   else get_offsuit_rank(c))
                # C2 — don't overtake a fellow defender (opt-in).
                # PASS-2 GATE: only fires if the bidder has already played
                # in this trick. Otherwise the bidder is downstream and
                # an unchallenged defender-winner just hands the bidder a
                # cheap over-trump. (N1 already early-returns when locked.)
                # L2 OVERRIDE: if the current winner IS the runaway-leader
                # defender, DON'T suppress with C2 — fall through to C1's
                # cheapest-winner take so we deny the leader the trick.
                # L3 OVERRIDE: bidder is one bid away from winning the game.
                # C2's "save for bidder-tricks" is irrelevant — every trick
                # the bidder doesn't take helps us. Fall through to C1's
                # cheapest-winner take regardless of who's currently winning.
                _c2_suppress_l2 = (_l2 and cw == _l2_leader_seat)
                _c2_suppress_l3 = _l3
                if (Fon('cutthroat_c2_dont_overtake')
                        and cw != _bw and cw != player
                        and _bidder_has_played
                        and not _set_lk
                        and not _c2_suppress_l2
                        and not _c2_suppress_l3):
                    return play_lowest(playable)
                # C1 — take from the bidder with the cheapest winner
                # (opt-in). (N1 already early-returns when locked.)
                # L1 SOFTENING: if I'm the runaway leader, take only when
                # cheapest winner is NOT a top-3 trump (conserve high cards).
                # L2 EXTENSION: also take from the runaway-leader defender
                # (not just bidder) when they're currently winning the trick.
                # L3 EXTENSION: max-aggression — take whenever I can, with
                # NO top-3 save; the bidder winning the game costs us more
                # than burning a high card.
                _c1_target_is_leader = (_l2 and cw == _l2_leader_seat)
                _c1_take = (cw == _bw) or _c1_target_is_leader or _l3
                if (Fon('cutthroat_c1_take_from_bidder')
                        and _c1_take
                        and not _set_lk and not _made_lk):
                    _winners = [c for c in playable
                                if trick_winner(
                                    _pad4(trick + [c],
                                          trump if F('safe_pad4') else None),
                                    trump, leader) == player]
                    if _winners:
                        _lo_win = min(_winners,
                                      key=lambda c: _tr(c, trump)
                                      if _is_trump(c, trump)
                                      else get_offsuit_rank(c))
                        # L1: don't burn a top-3 trump (rank >= 100) to take.
                        # L3 overrides L1 — bidder-wins-game is more urgent.
                        if (_l1 and not _l3
                                and _is_trump(_lo_win, trump)
                                and _tr(_lo_win, trump) >= 100):
                            return play_lowest(playable)
                        return _lo_win

            if my_position == 3:
                winners = [c for c in playable
                           if trick_winner(_pad4(trick + [c], trump if F('safe_pad4') else None), trump, leader) == player]
                if winners:
                    return min(winners, key=lambda c: _tr(c, trump) if _is_trump(c, trump)
                               else get_offsuit_rank(c))

            if my_position == 2:
                # BURNFORCE_3RD (opt-in challenger; champion: flag absent →
                # falls through to the unconditional max-trump rule below).
                # Defender 3rd-man with trump on a trick currently won by an
                # opponent: instead of burning my own max-trump (which is
                # often a top-3 — 5/J/A♥), play the LOWEST non-top-3 trump
                # for which every remaining unplayed over-trump is a top-3.
                # Result: 4th-man either has no over-trump (I win the trick
                # cheaply) OR is forced to burn a top-3 to win — net team
                # economy improves because their top-3 is gone and mine is
                # preserved. The min_trump_rank floor data layer is what
                # makes the safety check on "any over-trumps remaining are
                # in 4th-man's hand-band" sound.
                is_defender = ((player != bid_winner) if self.flags.get('cutthroat')
                               else (player % 2) != (bid_winner % 2))
                if Fon('burnforce_3rd') and is_defender and my_trumps:
                    fourth_seat = (leader + 3) % 4
                    fourth_void = (known_voids[fourth_seat].get('trump') is True)
                    if not fourth_void:
                        played_ids = {cid(c) for c in cards_played}
                        my_ids = {cid(c) for c in hand}
                        tv = trump.value
                        # Build full universe of trump cards (rank, id).
                        ranked = [(102, f"5{tv}"), (101, f"J{tv}"),
                                  (100, "A♥")]
                        if trump != HEARTS:
                            ranked.append((99, f"A{tv}"))
                        ranked.append((98, f"K{tv}"))
                        ranked.append((97, f"Q{tv}"))
                        low_order = (['2', '3', '4', '6', '7', '8', '9', '10']
                                     if trump in (HEARTS, Suit.DIAMONDS)
                                     else ['10', '9', '8', '7', '6', '4', '3', '2'])
                        for i, r in enumerate(low_order):
                            ranked.append((80 + i, f"{r}{tv}"))
                        # Ranks of trump cards that are still in play AND
                        # not in my hand — i.e. could be in some opponent's
                        # hand (and specifically might be in 4th-man's).
                        in_play_ranks = {r for (r, cid_) in ranked
                                         if cid_ not in played_ids
                                         and cid_ not in my_ids}
                        burn_candidates = []
                        for t in my_trumps:
                            t_rank = _tr(t, trump)
                            if t_rank >= 100:
                                continue  # don't burn my own top-3
                            over = {r for r in in_play_ranks if r > t_rank}
                            # No over-trumps remain → my T wins outright;
                            # AND every remaining over-trump is a top-3 →
                            # 4th-man either can't over-trump or must burn
                            # a top-3 to do so. Both are wins for our team.
                            if not over or all(r >= 100 for r in over):
                                burn_candidates.append((t, t_rank))
                        if burn_candidates:
                            return min(burn_candidates, key=lambda x: x[1])[0]
                # FORCE-EXTRACT (opt-in challenger; champion: flag absent →
                # falls straight through to the unconditional 3rd-man-high
                # below, i.e. unchanged). Hypothesis: the existing
                # unconditional 3rd-hand-high trump is a LEAK when the bidder
                # is 4th and partner can't capitalize — you feed a high trump
                # into the bidder's guaranteed overtrump for no payoff. Only
                # sacrifice when partner is trump-rich; else play low.
                if (not self.flags.get('cutthroat')
                        and Fon('following_3rd_man_force_extract') and my_trumps):
                    fourth_seat = (leader + 3) % 4
                    if (fourth_seat == bid_winner
                            and (player % 2) != (bid_winner % 2)):
                        bidder_top = (
                            state.high_bid >= 20 and
                            get_highest_remaining_trump(cards_played, trump) >= 99)
                        partner_idx = (player + 2) % 4
                        gf = self.flags.get
                        rich = False
                        if gf('fx_proxy_shed') or gf('fx_proxy_any'):
                            if _partner_shed_high_trump(play_history, partner_idx,
                                                        bid_winner, trump):
                                rich = True
                        if gf('fx_proxy_drew') or gf('fx_proxy_any'):
                            if cards_drawn and cards_drawn[partner_idx] <= 1:
                                rich = True
                        if gf('fx_proxy_led_trump') or gf('fx_proxy_any'):
                            if leader == partner_idx and _is_trump(trick[0], trump):
                                rich = True
                        if bidder_top and rich:
                            return max(my_trumps, key=lambda c: _tr(c, trump))
                        return play_lowest(playable)
                if my_trumps:
                    return max(my_trumps, key=lambda c: _tr(c, trump))
                if my_offsuit:
                    return max(my_offsuit, key=get_offsuit_rank)

            if my_position == 1:
                # def_ruff_be_eg (opt-in; champion: flag-absent → unchanged,
                # bit-identical). NARROW endgame variant of the REMOVED
                # v2.31.25 ruff-cheap: fire ONLY when I am a DEFENDER, it is
                # the endgame (trick>=4), the BIDDER led a high offsuit (an
                # Ace — a guaranteed winner unless trumped), and I am void
                # with trump in hand → cheap-ruff to deny the bidder a free
                # trick and take the lead. Far tighter than v2.31.25 (which
                # fired on ANY 2nd-man void, ANY trick, ANY led card → net-
                # negative because early low-offsuit leads want 2nd-man-low).
                _drbe_is_def = ((player != bid_winner)
                                if self.flags.get('cutthroat')
                                else (player % 2) != (bid_winner % 2))
                if (F('def_ruff_be_eg') and my_trumps
                        and leader == bid_winner
                        and _drbe_is_def
                        and trick_num >= 4
                        and not _is_trump(trick[0], trump)
                        and trick[0].rank == 'A'):
                    return min(my_trumps, key=lambda c: _tr(c, trump))
                # off2_beat_off_bidlead (opt-in challenger; user-derived
                # 2026-05-23). The "2nd-man low" mantra is TRUMP-specific.
                # On offsuit: 2nd-man defender following an OFFSUIT lead
                # BY THE BIDDER should beat the lead with the LOWEST
                # higher led-suit card instead of dribbling low. This
                # forces 3rd-man (bidder's partner) to either over-beat
                # with higher offsuit, commit trump, or concede — and
                # saves 4th-man (my partner) from having to ruff in to
                # win the trick. User-derived from a real-game screenshot
                # where N (defender bidder?) led 5♠ offsuit and E (2nd,
                # defender) played low spade instead of beating it.
                _ob_is_def = ((player != bid_winner)
                              if self.flags.get('cutthroat')
                              else (player % 2) != (bid_winner % 2))
                if (F('off2_beat_off_bidlead')
                        and my_position == 1
                        and trick
                        and not _is_trump(trick[0], trump)
                        and _ob_is_def
                        and leader == bid_winner):
                    _ls = trick[0].suit
                    _wr = get_offsuit_rank(trick[0])
                    _beaters = [c for c in playable
                                if c.suit == _ls
                                and not _is_trump(c, trump)
                                and get_offsuit_rank(c) > _wr]
                    if _beaters:
                        return min(_beaters, key=get_offsuit_rank)
                # off2_beat_off_anyopp (opt-in; broader variant — fires
                # whenever ANY opponent leads offsuit, not just the
                # bidder. Risks wasting a high offsuit when the leader
                # is bidder's partner (3rd is then the bidder who will
                # over-beat / cash). Memory rule: try broader formulation
                # before declaring no signal.
                _oba_is_def = ((player != bid_winner)
                               if self.flags.get('cutthroat')
                               else (player % 2) != (bid_winner % 2))
                if (Fon('off2_beat_off_anyopp')
                        and my_position == 1
                        and trick
                        and not _is_trump(trick[0], trump)
                        and _oba_is_def):
                    _ls = trick[0].suit
                    _wr = get_offsuit_rank(trick[0])
                    _beaters = [c for c in playable
                                if c.suit == _ls
                                and not _is_trump(c, trump)
                                and get_offsuit_rank(c) > _wr]
                    if _beaters:
                        return min(_beaters, key=get_offsuit_rank)
                # take_t4_2nd (opt-in; user-derived 2026-05-21). On trick
                # 4 or 5, 2nd-man plays the cheapest CARD that wins the
                # current partial-trick state — regardless of trump vs
                # offsuit, renege capability, or role. The general
                # principle: at trick 4 the winner of this trick leads
                # the final trick with all other players holding only
                # ONE card each (positional advantage). Strict 2nd-man-
                # low conserves cards for "later" but at trick 4 there
                # IS no later worth conserving for. Over-trump risk from
                # 3rd/4th men remains — rig measures whether the bet
                # pays out on average.
                if (F('take_t4_2nd') and trick_num >= 4 and trick):
                    winners = [c for c in playable
                               if trick_winner(
                                   _pad4(trick + [c],
                                         trump if F('safe_pad4') else None),
                                   trump, leader) == player]
                    if winners:
                        return min(winners,
                                   key=lambda c: _tr(c, trump)
                                   if _is_trump(c, trump)
                                   else get_offsuit_rank(c))
                # v2.31.25/26: AFTER-VOID + RUFF-CHEAP + trick-3 partner-shed
                # exception all removed (audit proved each net-negative).
                # 2nd man = pure strict 2nd-man-low.
                return play_lowest(playable)

        # fall-through safety (mirrors JS Monte-Carlo path approximately)
        return play_lowest(playable)
