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
                enable_upbid15: bool = True,
                enable_loose_open: bool = True,
                loose_open_pass_prob: float = 0.0,
                desp_overbid25_pass_prob: float = 0.0,
                cutthroat: bool = False,
                cutthroat_tight_20: bool = False,
                cutthroat_tight_25: bool = False,
                cutthroat_kill_30: bool = False,
                cutthroat_surgical_tight_20: bool = False,
                cutthroat_aggressive_tight_20: bool = False,
                cutthroat_surgical_tight_15: bool = False,
                cutthroat_allow_5ahat_25: bool = False,
                cutthroat_force_upbid15: bool = False,
                cutthroat_desp_tight_20: bool = False,
                cutthroat_force_loose_open: bool = False,
                cutthroat_opp_has_dealer_always: bool = False,
                cutthroat_desp_rule4_tight: bool = False) -> Tuple[int, Optional[Suit]]:
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
    # opp_has_dealer: partner-mode logic = "the dealer is on the opposing
    # team" via seat parity. In cutthroat there is no team — every non-self
    # seat including the dealer is an opp, so the semantic answer is True
    # iff I am not the dealer. Cutthroat now defaults to the semantic
    # version (cutthroat_opp_has_dealer_always=True, ship v2.31.87) which
    # tested symmetric Δ -1.30pt z=-10.16 primary / -1.21pt z=-11.6 held-
    # out (replicated, 25-bid count -44%). Setting the flag False on a
    # cutthroat policy is the ablation/regression baseline. Partner mode
    # always uses the parity check — bit-identical regardless of flag.
    if cutthroat and cutthroat_opp_has_dealer_always:
        opp_has_dealer = (dealer != player_index)
    else:
        opp_has_dealer = get_team(dealer) != my_team

    desperation = they_need <= desp_they_need and we_need > desp_we_need_floor
    they_can_win_15 = they_need <= 15
    they_can_win_20 = they_need <= 20

    # ── CUTTHROAT NORMALIZATION ──────────────────────────────────────────────
    # Cutthroat is every-man-for-himself: there is no partner concept. Any
    # partner-aware branch must be neutralized. We do this by zeroing out
    # partner_bid and disabling spoiler (spoiler is a partner-team-aware
    # sacrifice). Threshold values (15/20/25/30) remain identical to partner
    # mode for v1 — Phase 2 will tighten 20/25/30 since cutthroat needs every
    # trick yourself with no partner help.
    if cutthroat:
        partner_bid = 0
        enable_spoiler = False
        # UPBID15 (v2.31.56) and loose-open (v2.31.36-37) were calibrated
        # against the partner-mode evaluator and are aggressive overbids that
        # depend on partner-share-the-load economics. In cutthroat (no partner)
        # the default assumption is net-negative → force off. Two opt-in flags
        # let challengers override these gates to measure the actual delta:
        #   cutthroat_force_upbid15 — UPBID15 (v2.31.56) ON in cutthroat
        #   cutthroat_force_loose_open — OPEN-15 (v2.31.36-37) ON in cutthroat
        # Both rules are ported into this file (see post-bid blocks below)
        # so the rig can actually exercise the JS-side gap. As of 2026-05-29:
        # UPBID15 confirmed catastrophic in cutthroat (Δ +14.31pt z=+113.79
        # primary / +14.55pt z=+141.51 held-out), shipped JS gate v2.31.83.
        # Loose-open under test.
        enable_upbid15 = bool(cutthroat_force_upbid15)
        enable_loose_open = bool(cutthroat_force_loose_open)
    else:
        # Safety: the cutthroat_tight_* kwargs are CUTTHROAT-MODE tightening
        # only. Force off in partner mode so a misconfigured caller can never
        # mutate the validated partner-mode bidding. Partner-mode bit-identity
        # depends on this.
        cutthroat_tight_20 = False
        cutthroat_tight_25 = False
        cutthroat_kill_30 = False
        cutthroat_surgical_tight_20 = False
        cutthroat_aggressive_tight_20 = False
        cutthroat_surgical_tight_15 = False
        cutthroat_allow_5ahat_25 = False

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
            return 25, suit
        if opp_bid_25:
            return 0, None
        if opp_has_dealer and current_high_bid == 0:
            # RULE 4 — bag-the-dealer with hand-strength threshold for "can
            # we make X to survive?" Calibrated against partner-mode 1.1M
            # simulation. In cutthroat with C1+C2 coalition, make rates are
            # lower → thresholds want to be tighter. Opt-in challenger
            # `cutthroat_desp_rule4_tight` adds the J of trump (2nd-highest
            # trump in the game) to each canMake test that lacks it, so the
            # bid-20-vs-pass-to-bag exit gates on hands that actually carry
            # in cutthroat. canMake30 (5+J+AH+T5) is already maximally
            # strict.
            if cutthroat and cutthroat_desp_rule4_tight:
                if they_need <= 5:
                    if has5 and hasJ and hasAH and trump_count >= 5:
                        return 20, suit
                    return 0, None
                if they_need <= 10:
                    # Was: 5+J+T4. Tightened: add AH (3 top trump + 1).
                    if has5 and hasJ and hasAH and trump_count >= 4:
                        return 20, suit
                    return 0, None
                if they_need <= 15:
                    # Was: 5+T4. Tightened: add J (5+J = boss-plus-2nd-boss).
                    if has5 and hasJ and trump_count >= 4:
                        return 20, suit
                    return 0, None
                if they_need <= 20:
                    # Was: has5 OR (J+AH+T3). Tightened: 5+J or J+AH+T4.
                    if (has5 and hasJ) or (hasJ and hasAH and trump_count >= 4):
                        return 20, suit
                    return 0, None
            else:
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
            # RULE 6 — preemptive 20 to block opp's likely game-winning 15.
            # CUTTHROAT TIGHTENING (cutthroat_desp_tight_20, opt-in challenger):
            # the partner-mode can20_60 table includes AH_T4 (64.05%), J_T3
            # (63.5%), AT_T4 (61.47%), etc. — patterns that pay in partner
            # mode but get crushed by 3 coordinated defenders in cutthroat.
            # Two robr screenshots in a row hit this (AH_T4 + J_T3 leak
            # paths). Tightening requires has5 OR (hasJ AND hasAH) — both
            # patterns that justify a 20 even with cutthroat defenders.
            if cutthroat and cutthroat_desp_tight_20:
                if has5 or (hasJ and hasAH):
                    return 20, suit
            elif can20_60 or has5:
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
                                    desp_we_need_floor, enable_spoiler=False,
                                    enable_upbid15=enable_upbid15,
                                    enable_loose_open=enable_loose_open,
                                    loose_open_pass_prob=loose_open_pass_prob,
                                    desp_overbid25_pass_prob=desp_overbid25_pass_prob)
            if champ_b < spoil_to:          # champion can't take it legit
                return spoil_to, suit       # sacrifice to deny their win

    # ── GUARANTEED HAND ──────────────────────────────────────────────────────
    if is_guaranteed_hand(hand, suit):
        natural = 30 if (has5 and hasJ and hasAH and hasAT) else 25
        # H3 (cutthroat_kill_30): 30 requires 5+J+AH+AT+T1 — i.e. the four
        # top anchors AND >=5 trump. is_guaranteed_hand grants 30 whenever
        # all four anchors are present, even with exactly 4 trump. Knock
        # such hands back to 25 (still guaranteed, but no "free trick" left).
        if cutthroat_kill_30 and natural == 30 and trump_count < 5:
            natural = 25
        # H2 (cutthroat_tight_25): the OTHER guaranteed branch is
        # has5 ∧ hasJ ∧ hasAH ∧ trump_count>=4 (no AT) → natural=25. That
        # IS 5+J+AH which the tight-25 rule keeps. Nothing to demote here.
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
            # H3 (cutthroat_kill_30): 30 requires 5+J+AH+AT+T1 (=5+ trump
            # incl. the four top anchors). Knock partner-era 30s that miss
            # AT or AH back to 25 (still strong, but solo-realistic).
            if cutthroat_kill_30 and bid == 30 and not (
                    has5 and hasJ and hasAH and hasAT and trump_count >= 5):
                bid = 25
        if bid == 0:
            if has5 and hasJ and hasAH:
                bid = 25
            elif has5 and hasJ and trump_count >= 5:   # v2.31.29: 5_J_T5 only; 5_J_T4 → 20 below
                bid = 25
            elif has5 and hasAH and trump_count >= 5:
                bid = 25
            # H2 (cutthroat_tight_25): keep only 5+J+AH OR 5+J+T3 (the
            # latter = has5 ∧ hasJ ∧ trump_count>=5 in this codebase's
            # notation: 5,J + 3 lower trump = 5 trump total). Drop the
            # 5+AH+T3 branch (no J → solo can't extract the J safely).
            if cutthroat_tight_25 and bid == 25 and not (
                    (has5 and hasJ and hasAH)
                    or (has5 and hasJ and trump_count >= 5)):
                bid = 0
        if bid == 0:
            if has5 and hasJ:
                bid = 20
            elif has5 and hasAH and trump_count >= 3:
                bid = 20
            elif has5 and trump_count >= 4:
                bid = 20
            elif hasJ and hasAH and trump_count >= 5:
                bid = 20
            # H1 (cutthroat_tight_20): 20 requires >=4 trump. Drops the
            # has5∧hasJ-with-only-2/3-trump pattern and the has5∧hasAH-
            # with-only-3-trump pattern. Solo cannot extract 4 tricks
            # from 2-3 trump even with two top cards.
            if cutthroat_tight_20 and bid == 20 and trump_count < 4:
                bid = 0
            # SURGICAL TIGHT-20 (cutthroat_surgical_tight_20): pattern-targeted
            # demotion derived from cutthroat_pattern_makerate.py @ 2000 deals
            # against champion-cutthroat. Drops the six 20-bid patterns with
            # observed make-rate ≤ 36% (EV-negative at 20). Pattern definitions
            # use this codebase's trump_count semantics (count_trumps INCLUDES
            # the 5/J/AH/AT anchors). Hearts-trump caveat: hasAT is False when
            # trump==hearts (has_ace_trump gate), so the 5AH+T3 check matches
            # a hearts-trump 5+AH+T3 hand symmetrically with the non-hearts
            # 5+AT+T3 pattern under the SAME code path — desired behavior.
            #
            #   make-rate  pattern (n)         condition (= 3 lower + anchors)
            #   ----------  ------------------- --------------------------------
            #    2.6%  5+T2      (n=76)   has5, no JAH/AT, T==3
            #    8.2%  J+T3      (n=49)   hasJ, no 5/AH/AT, T==4
            #    8.1%  5J+T2     (n=135)  5+J, no AH/AT, T==4
            #   12.7%  5+T3      (n=134)  has5, no J/AH/AT, T==4
            #   19.2%  5AT+T3    (n=26)   5+AT, no J/AH, T==5
            #   36.2%  5AH+T3    (n=246)  5+AH, no J/AT, T==5
            if cutthroat_surgical_tight_20 and bid == 20:
                p_5_T2 = (has5 and not hasJ and not hasAH and not hasAT
                          and trump_count == 3)
                p_J_T3 = (hasJ and not has5 and not hasAH and not hasAT
                          and trump_count == 4)
                p_5J_T2 = (has5 and hasJ and not hasAH and not hasAT
                           and trump_count == 4)
                p_5_T3 = (has5 and not hasJ and not hasAH and not hasAT
                          and trump_count == 4)
                p_5AT_T3 = (has5 and hasAT and not hasJ and not hasAH
                            and trump_count == 5)
                p_5AH_T3 = (has5 and hasAH and not hasJ and not hasAT
                            and trump_count == 5)
                if (p_5_T2 or p_J_T3 or p_5J_T2 or p_5_T3
                        or p_5AT_T3 or p_5AH_T3):
                    bid = 0
            # AGGRESSIVE TIGHT-20 (cutthroat_aggressive_tight_20): surgical
            # + ALSO drops 5+T4 (n=232, make-rate 53.9%, borderline). If
            # both surgical and aggressive ship-positive, aggressive wins;
            # if aggressive hurts vs surgical, 5+T4 IS net-positive at 20.
            #   53.9%  5+T4      (n=232)  has5, no J/AH/AT, T==5
            if cutthroat_aggressive_tight_20 and bid == 20:
                p_5_T2 = (has5 and not hasJ and not hasAH and not hasAT
                          and trump_count == 3)
                p_J_T3 = (hasJ and not has5 and not hasAH and not hasAT
                          and trump_count == 4)
                p_5J_T2 = (has5 and hasJ and not hasAH and not hasAT
                           and trump_count == 4)
                p_5_T3 = (has5 and not hasJ and not hasAH and not hasAT
                          and trump_count == 4)
                p_5AT_T3 = (has5 and hasAT and not hasJ and not hasAH
                            and trump_count == 5)
                p_5AH_T3 = (has5 and hasAH and not hasJ and not hasAT
                            and trump_count == 5)
                p_5_T4 = (has5 and not hasJ and not hasAH and not hasAT
                          and trump_count == 5)
                if (p_5_T2 or p_J_T3 or p_5J_T2 or p_5_T3
                        or p_5AT_T3 or p_5AH_T3 or p_5_T4):
                    bid = 0
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
            # SURGICAL TIGHT-15 (cutthroat_surgical_tight_15): pattern-targeted
            # demotion of natural-15 bids derived from
            # cutthroat_pattern_makerate.py @ 3000 deals against
            # champion-cutthroat (post v2.31.77 surgical tight-20 ship).
            # Drops the two highest-volume EV-negative 15-bid patterns
            # where the bidder has a single anchor and only 1-2 trump total
            # (insufficient depth for solo cutthroat trick extraction).
            # Pattern definitions use this codebase's trump_count semantics
            # (count_trumps INCLUDES the 5/J/AH/AT anchors).
            #
            #   make-rate  pattern (n)         condition
            #   ---------- ------------------- --------------------------------
            #    0.0%  J+T1     (n=185)  hasJ only, T==1 (lonely J)
            #    3.5%  5+T1     (n=255)  has5 only, T==1 (lonely 5)
            #   16.2%  J+T2     (n=1,167) hasJ only, T==2 (J + 1 lower trump)
            #   32.9%  5+T2     (n=1,531) has5 only, T==2 (5 + 1 lower trump)
            # Pre-kitty buckets shift slightly under post-draw analyzer
            # naming (kitty adds trump) — the rule gates the pre-kitty
            # hand the bidder ACTUALLY sees, so it targets:
            #   hasJ AND no5/AH/AT AND tc<=2 (captures J+T1, J+T2 family)
            #   has5 AND noJ/AH/AT AND tc<=2 (captures 5+T1, 5+T2 family)
            if cutthroat_surgical_tight_15 and bid == 15:
                p_J_alone_T12 = (hasJ and not has5 and not hasAH
                                 and not hasAT and trump_count <= 2)
                p_5_alone_T12 = (has5 and not hasJ and not hasAH
                                 and not hasAT and trump_count <= 2)
                if p_J_alone_T12 or p_5_alone_T12:
                    bid = 0

    # CUTTHROAT ALLOW 5+AH+AT-no-J → 25 (opt-in challenger flag, cutthroat-
    # only). Derived from a robr bidLogCutthroat divergence: he bid 25 on a
    # 5+AH+AT+T1 hand (5 of trump + A♥ + A of trump + 1 lower trump, no J)
    # and made it. EV math: 5 + AH + AT + offsuit K = 4 likely tricks @ 5pt
    # each + 5pt high-trump bonus = 25pt. With 4 trump including 3 top
    # anchors (5/AH/AT) and only J of trump as the over-card threat (kitty
    # or extracted on a later trick), the bid is +EV at 25. Champion-
    # cutthroat currently passes (5+AH+AT+T1 → natural 20-bid against a 20
    # auction → pass). Rule overrides to 25 when the auction stands at 20.
    if (cutthroat and cutthroat_allow_5ahat_25
            and current_high_bid == 20 and bid < 25
            and has5 and hasAH and hasAT and not hasJ
            and trump_count >= 4):
        bid = 25

    # UPBID15 (v2.31.56, JS port from index.html). When the auction stands
    # at 15 AND our natural bid is 15 (which would otherwise pass since we
    # can't equal the high bid), overbid to 20. Excludes the dealer (separate
    # forced-15 path) and partner-bid-15 (don't overbid your own partner).
    # Partner-mode rig validated at +5.42pt z=21.68 primary 20k / +5.30pt
    # z=25.96 held-out 30k (jack2112-derived). In cutthroat this is gated
    # off by default (see cutthroat normalization above) — only fires when
    # `cutthroat_force_upbid15=True` is passed for opt-in measurement.
    if (enable_upbid15 and bid == 15 and current_high_bid == 15
            and player_index != dealer and partner_bid != 15):
        bid = 20

    # Dealer clamp (only bid the minimum needed)
    if bid > current_high_bid and player_index == dealer and current_high_bid > 0:
        bid = min(bid, current_high_bid + 5)

    if bid <= current_high_bid:
        # Dealer bagged: all passed → forced 15
        if player_index == dealer and current_high_bid == 0:
            return 15, suit
        # OPEN-15 (v2.31.36-37, JS port from index.html). Loose unconditional
        # 15 open: when no one has bid, partner has not bid, we are not
        # cruising (we_need<=15 with leader-not-yet-near-120), and not in
        # desperation (their score not near 120), open 15. Partner-mode rig
        # validated at +3.52pt (v2.31.36 looser open) / +1.19pt held-out
        # (v2.31.37 open:nd). Gated off in cutthroat by default (see cutthroat
        # normalization above) — only fires when `cutthroat_force_loose_open`
        # is True for opt-in measurement. partnerIsHuman is not modelled in
        # the sim (all-AI). AUTO15_PASS_PROB randomized pass is modelled via
        # loose_open_pass_prob (already wired through the spoiler recursion
        # path). NB: AUTO15_PASS_PROB=0.5 is the JS live value but the sim
        # has been calling decide_bid with default 0.0 (always-fire) so the
        # rig measures the worst-case (loosest) variant — appropriate for an
        # opt-in challenger.
        if (enable_loose_open and current_high_bid == 0
                and not (partner_bid > 0)
                and not (we_need <= 15 and opp_scores <= 85)
                and not (they_need <= 15 and we_need > 0)):
            if loose_open_pass_prob > 0.0:
                import random
                if random.random() < loose_open_pass_prob:
                    return 0, None
            return 15, suit
        return 0, None
    return bid, suit
