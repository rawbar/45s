"""
bidding.py — Faithful port of index.html decideBid + bid helpers (v2.31.23).

Ported 2026-05-16. The full-game head-to-head evaluator needs a real bidding
phase (the 5M bidding sim deliberately skipped it). decideBid is score-aware:
it takes live team/opp scores and has DESPERATION + CRUISE-CONTROL branches —
so game_runner MUST pass the running scores and each player's partner bid.

decide_bid signature mirrors JS:
    decide_bid(hand, current_high_bid, player_index, dealer,
               team_scores, opp_scores, partner_bid) -> (bid:int, suit:Suit|None)
Returns (0, None) for a pass.

NOTE: situational endgame logic (e.g. symmetric 105-105 near-win) is NOT in
decideBid today — desperation requires theyNeed<=30 AND weNeed>30, which the
105-105 case fails. That gap is challenger #1 for the evaluator, intentionally
left out of this faithful port so the baseline matches the shipped game.
"""

import hashlib
from typing import List, Tuple, Optional
from game_engine import Card, Suit, get_trump_rank, is_trump

HEARTS = Suit.HEARTS
# index.html: const SUITS = ['♠','♥','♦','♣']
SUITS = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]


# ── bid helpers (port of the const helpers in index.html) ────────────────────

def has_card(hand: List[Card], rank: str, suit: Suit) -> bool:
    return any(c.rank == rank and c.suit == suit for c in hand)


def has_five(hand, trump):       return has_card(hand, '5', trump)
def has_jack(hand, trump):       return has_card(hand, 'J', trump)
def has_ace_hearts(hand):        return has_card(hand, 'A', HEARTS)
def has_ace_trump(hand, trump):  return trump != HEARTS and has_card(hand, 'A', trump)
def count_trumps(hand, trump):   return sum(1 for c in hand if is_trump(c, trump))
def count_high_trumps(hand, trump):
    return sum(1 for c in hand if get_trump_rank(c, trump) >= 97)


def is_guaranteed_hand(hand: List[Card], trump: Suit) -> bool:
    h5 = has_five(hand, trump)
    hj = has_jack(hand, trump)
    hah = has_ace_hearts(hand)
    hat = has_ace_trump(hand, trump)
    if h5 and hj and hah and hat:
        return True
    if h5 and hj and hah and count_trumps(hand, trump) >= 4:
        return True
    return False


def find_best_trump_suit(hand: List[Card]) -> dict:
    """JS-exact: score = 1000*has5 + 500*hasJ + 10*count, strict > , ♠♥♦♣ order."""
    best = Suit.SPADES
    best_count = 0
    best5 = False
    best_j = False
    for suit in SUITS:
        count = count_trumps(hand, suit)
        h5 = has_five(hand, suit)
        hj = has_jack(hand, suit)
        score = (1000 if h5 else 0) + (500 if hj else 0) + count * 10
        best_score = (1000 if best5 else 0) + (500 if best_j else 0) + best_count * 10
        if score > best_score:
            best, best_count, best5, best_j = suit, count, h5, hj
    return {'suit': best, 'trumpCount': best_count, 'has5': best5, 'hasJ': best_j}


def get_team(player: int) -> int:
    return player % 2


# ── decideBid (faithful port) ────────────────────────────────────────────────

def decide_bid(hand: List[Card],
                current_high_bid: int,
                player_index: int,
                dealer: int,
                team_scores: int,
                opp_scores: int,
                partner_bid: int,
                enable_desperation: bool = True,
                enable_cruise: bool = True,
                desp_they_need: int = 15,
                desp_we_need_floor: int = 0,
                enable_spoiler: bool = False,
                enable_loose_open: bool = True,
                loose_open_pass_prob: float = 0.0,
                desp_overbid25_pass_prob: float = 0.0,
                enable_upbid15: bool = True,
                enable_open_5_at_20: bool = True) -> Tuple[int, Optional[Suit]]:
    """Defaults reproduce LIVE index.html v2.31.24+ decideBid: desp_they_need
    =15, desp_we_need_floor=0 → `they_need<=15 and we_need>0`. This is the
    DATA-DERIVED, held-out-validated trigger (commit d19be47: 12k deals/cell
    sweep + 60k held-out, +0.95pt comeback equity z=4.38) that REPLACED the
    old hand-guessed 30/30 placeholder. (The port was made at v2.31.23 which
    still had 30/30; v2.31.24 changed only this one line — RULE 1-6 below
    unchanged.) The (T,W) params still allow the sweep to retune/ablate;
    they_can_win_15/20 are correct game logic, not placeholders."""
    fb = find_best_trump_suit(hand)
    suit = fb['suit']
    trump_count = fb['trumpCount']
    has5 = fb['has5']
    hasJ = fb['hasJ']
    hasAH = has_ace_hearts(hand)
    hasAT = has_ace_trump(hand, suit)
    highT = count_high_trumps(hand, suit)

    my_team = get_team(player_index)
    we_need = 120 - team_scores
    they_need = 120 - opp_scores
    opp_has_dealer = get_team(dealer) != my_team

    desperation = they_need <= desp_they_need and we_need > desp_we_need_floor
    they_can_win_15 = they_need <= 15
    they_can_win_20 = they_need <= 20

    opp_bid_15 = current_high_bid == 15 and partner_bid != 15
    opp_bid_20 = current_high_bid == 20 and partner_bid != 20
    opp_bid_25 = current_high_bid == 25 and partner_bid != 25

    can20_60 = (has5 or (hasJ and hasAH and trump_count >= 2)
                or (hasJ and hasAT and trump_count >= 2)
                or (hasJ and trump_count >= 3)
                or (hasAH and trump_count >= 4)
                or (hasAT and trump_count >= 4))

    # ── DESPERATION ──────────────────────────────────────────────────────────
    if desperation and enable_desperation:
        if opp_bid_15 and they_can_win_15:
            return 20, suit
        if opp_bid_20 and they_can_win_20 and player_index == dealer:
            # RANDOMIZED 25-SACRIFICE (v2.31.44): this hand-blind overbid to
            # 25 (deny their game-point 20) is exploitable — a human bids 20
            # on air knowing the AI always sacrifices into a doomed 25. The
            # 20-overbids stay always-on (cheap/makeable). Here, ONLY when
            # the hand is crap for 25 (cannot even make 20 → pure sacrifice)
            # pass with probability desp_overbid25_pass_prob (mixed strategy:
            # "you might be bluffing — try to make your 20"). Deterministic
            # per decision-state (stable md5, paired-deal-safe) in the rig;
            # shipped JS uses true Math.random(). prob 0.0 = champion
            # bit-identical. A real (can20_60) hand still always sacrifices.
            if desp_overbid25_pass_prob > 0.0 and not can20_60:
                _k = repr((tuple(sorted((c.rank, c.suit.value)
                                        for c in hand)),
                           current_high_bid, player_index, dealer,
                           team_scores, opp_scores, partner_bid, 'd25'))
                _hh = int(hashlib.md5(_k.encode()).hexdigest()[:8], 16)
                if (_hh % 100000) / 100000.0 < desp_overbid25_pass_prob:
                    return 0, None
            return 25, suit
        if opp_bid_25:
            return 0, None
        if opp_has_dealer and current_high_bid == 0:
            if they_need <= 5:
                if has5 and hasJ and hasAH and trump_count >= 5:
                    return 20, suit
                return 0, None
            if they_need <= 10:
                if has5 and hasJ and trump_count >= 4:
                    return 20, suit
                return 0, None
            if they_need <= 15:
                if has5 and trump_count >= 4:
                    return 20, suit
                return 0, None
            if they_need <= 20:
                if has5 or (hasJ and hasAH and trump_count >= 3):
                    return 20, suit
                return 0, None
        if not opp_has_dealer:
            if opp_bid_15 and they_can_win_15:
                if has5:
                    return 20, suit
                if trump_count < 2 and not hasJ and not hasAH:
                    return 0, None
                return 20, suit
        if they_can_win_15 and current_high_bid == 0:
            if can20_60 or has5:
                return 20, suit

    # ── SPOILER (opt-in: enable_spoiler, default False = champion-identical) ──
    # User hypothesis: bids OVERMAKE often (focus-sim 400k: a 15 bid scores
    # >=20 in 58.9%, >=25 in 34.8%, =30 in 15.1%; min -15). So when an
    # opponent holds a bid that, via overmake, likely carries them to 120,
    # passing is a 59-80%+ loss — seize the contract with the minimum
    # overbid even on a hand that does not justify it. The shipped
    # desperation rule already does exactly this but ONLY when we_need>30;
    # this drops that gate (the documented symmetric-endgame 105-105 gap).
    if enable_spoiler:
        opp_holds = ((opp_bid_15 and current_high_bid == 15)
                     or (opp_bid_20 and current_high_bid == 20)
                     or (opp_bid_25 and current_high_bid == 25))
        # data-grounded danger: P(opp round pts >= they_need | their bid)
        danger = ((current_high_bid == 15 and they_need <= 20)
                  or (current_high_bid == 20 and they_need <= 20)
                  or (current_high_bid == 25 and they_need <= 25))
        spoil_to = current_high_bid + 5
        if opp_holds and danger and spoil_to <= 30:
            champ_b, _ = decide_bid(hand, current_high_bid, player_index,
                                    dealer, team_scores, opp_scores,
                                    partner_bid, enable_desperation,
                                    enable_cruise, desp_they_need,
                                    desp_we_need_floor, enable_spoiler=False)
            if champ_b < spoil_to:          # champion can't take it legit
                return spoil_to, suit       # sacrifice to deny their win

    # ── GUARANTEED HAND ──────────────────────────────────────────────────────
    if is_guaranteed_hand(hand, suit):
        natural = 30 if (has5 and hasJ and hasAH and hasAT) else 25
        if player_index == dealer and current_high_bid > 0:
            natural = min(natural, current_high_bid + 5)
        return natural, suit

    # ── CRUISE CONTROL ───────────────────────────────────────────────────────
    their_score = opp_scores
    if enable_cruise:
        if we_need <= 5 and their_score <= 85:
            has90 = has5 or (hasJ and trump_count >= 5) or (hasJ and hasAH and trump_count >= 4)
            if not has90:
                return 0, None
        elif we_need <= 10 and their_score <= 80:
            has85 = (has5 or (hasJ and trump_count >= 4)
                     or (hasJ and hasAH and trump_count >= 3)
                     or (hasJ and hasAT and trump_count >= 4))
            if not has85:
                return 0, None
        elif we_need <= 15 and their_score <= 80:
            has80 = (has5 or (hasJ and trump_count >= 3)
                     or (hasJ and hasAH and trump_count >= 2)
                     or (hasAH and trump_count >= 4)
                     or (hasAT and trump_count >= 4))
            if not has80:
                return 0, None

    # Don't overbid partner's 20 unless overwhelming
    if partner_bid == 20 and current_high_bid == 20:
        dominated = ((has5 and hasJ and hasAH)
                     or (has5 and hasJ and trump_count >= 4 and highT >= 3))
        if not dominated:
            return 0, None

    # ── STANDARD BIDDING ─────────────────────────────────────────────────────
    bid = 0
    partner_has_bid = partner_bid > 0
    opp_bid25 = current_high_bid == 25 and partner_bid != 25

    if partner_has_bid:
        if partner_bid == 15:
            if has5 and hasJ and hasAH and hasAT and trump_count >= 5:
                bid = 30
            elif has5 and hasJ and hasAH and trump_count >= 4:
                bid = 25
            elif has5 and hasJ and trump_count >= 5:   # v2.31.29: 5_J_T5 only; 5_J_T4 → 20 below
                bid = 25
            elif has5 and hasJ:
                bid = 20
            elif has5 and hasAH:
                bid = 20
            elif has5 and trump_count >= 3:
                bid = 20
        elif partner_bid == 20:
            if has5 and hasJ and hasAH and hasAT and trump_count >= 5:
                bid = 30
            elif has5 and hasJ and hasAH and trump_count >= 4:
                bid = 25
            elif has5 and hasJ and trump_count >= 5:
                bid = 25
        elif partner_bid == 25:
            if has5 and hasJ and hasAH and hasAT and trump_count >= 5:
                bid = 30
    else:
        if opp_bid25:
            if has5 and hasJ and hasAH and trump_count >= 4:
                bid = 30
            elif has5 and hasJ and trump_count >= 5:
                bid = 30
        if bid == 0:
            if has5 and hasJ and hasAH:
                bid = 25
            elif has5 and hasJ and trump_count >= 5:   # v2.31.29: 5_J_T5 only; 5_J_T4 → 20 below
                bid = 25
            elif has5 and hasAH and trump_count >= 5:
                bid = 25
        if bid == 0:
            if has5 and hasJ:
                bid = 20
            elif has5 and hasAH and trump_count >= 3:
                bid = 20
            elif has5 and trump_count >= 4:
                bid = 20
            elif hasJ and hasAH and trump_count >= 5:
                bid = 20
        if bid == 0:
            hasKT = has_card(hand, 'K', suit)
            hasQT = has_card(hand, 'Q', suit)
            if has5:
                bid = 15
            elif hasJ:
                bid = 15
            elif hasAH and hasAT and trump_count >= 3:
                bid = 15
            elif hasAH and hasKT and trump_count >= 3:
                bid = 15
            elif hasAT and hasKT and hasQT:
                bid = 15

    # UPBID-15 (opt-in flag override; jack2112-derived 2026-05-20).
    # When the auction stands at 15 and the AI calculated this hand as a
    # 15-bid (which would otherwise pass since you can't equal the bid),
    # overbid to 20 instead. Jack2112 (expert, +7.1pt vs champion baseline)
    # did this on 5/13 of his logged divergences — every one of those
    # hands the AI would have bid 15 on but couldn't because the auction
    # was already at 15. Exclude the dealer (their bagged-15 path is
    # different) and any partner-bid-15 case (don't overbid your own
    # partner). Opt-in flag controlled by the rig harness.
    if (enable_upbid15 and bid == 15 and current_high_bid == 15
            and player_index != dealer and partner_bid != 15):
        bid = 20

    # OPEN_5_AT_20 (opt-in; jack2112-derived 2026-05-22). Twin of
    # upbid15 for the OPEN case: when no one has bid yet and the AI
    # would open 15 on a 5-of-trump-anchor hand (the `has5` path,
    # which is hit by 5+T2 / 5+T3 hands without J/A♥/A-of-trump
    # support), open at 20 instead. Jack's logged "open 20 where AI
    # opens 15" cluster (5x) is uniformly this pattern.
    if (enable_open_5_at_20 and bid == 15 and current_high_bid == 0
            and player_index != dealer and has5):
        bid = 20

    # Dealer clamp (only bid the minimum needed)
    if bid > current_high_bid and player_index == dealer and current_high_bid > 0:
        bid = min(bid, current_high_bid + 5)

    if bid <= current_high_bid:
        # Dealer bagged: all passed → forced 15
        if player_index == dealer and current_high_bid == 0:
            return 15, suit
        # OPEN 15 (SHIPPED v2.31.37 = open:nd, champion default-ON).
        # v2.31.36 looser open (+3.52pt held-out z=17.2) made UNCONDITIONAL
        # in a clean open, plus a desperation guard: when desperation is
        # active (they_need<=15 & we_need>0 == opp at game point & we
        # behind) the open DEFERS to the desperation/deny logic instead of
        # throwing a junk 15 (that fall-through was the -1.84pt comeback
        # leak; user-diagnosed). Held-out +1.19pt overall (z=5.85), drag
        # neutralized to -0.66 NS. Mutually exclusive with the spoiler
        # (spoiler needs chb!=0). Ablate whole rule via enable_loose_open=False.
        if (enable_loose_open and current_high_bid == 0 and partner_bid <= 0
                and not (we_need <= 15 and opp_scores <= 85)
                and not (they_need <= 15 and we_need > 0)):
            # RANDOMIZED PASS (v2.31.44): the auto-15 on these residual
            # (5M-oracle-pass) hands is +EV but DETERMINISTIC → predictable,
            # exploitable, and frustrating to humans. With probability
            # loose_open_pass_prob, pass instead — a less-readable mixed
            # strategy. Deterministic per decision-state here (stable md5,
            # so paired mirrored deals still cancel); the shipped JS uses
            # true Math.random(). prob 0.0 = champion bit-identical. Only
            # the residual is randomized; genuine bids returned earlier.
            if loose_open_pass_prob > 0.0:
                _key = repr((tuple(sorted((c.rank, c.suit.value)
                                          for c in hand)),
                             current_high_bid, player_index, dealer,
                             team_scores, opp_scores, partner_bid))
                _h = int(hashlib.md5(_key.encode()).hexdigest()[:8], 16)
                if (_h % 100000) / 100000.0 < loose_open_pass_prob:
                    return 0, None
            return 15, suit
        return 0, None
    return bid, suit
