"""
challengers.py — registry of AI policies for the head-to-head evaluator.

'champion' is the faithful v2.31.23 baseline (its self-test must read ~50%).
The 'no-*' policies ablate a hand-coded bidding rule so the evaluator can
measure whether that made-up rule actually helps, is neutral, or hurts.
"""

from typing import List, Tuple, Optional
from game_engine import Card, Suit
from bidding_simulator_v2.policy import Policy
from bidding_simulator_v2 import bidding


class NoDesperation(Policy):
    name = "no-desperation"
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  enable_desperation=False, enable_cruise=True)


class NoCruise(Policy):
    name = "no-cruise"
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  enable_desperation=True, enable_cruise=False)


class NoDespNoCruise(Policy):
    name = "no-desp-no-cruise"
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  enable_desperation=False, enable_cruise=False)


# Every discrete situational CARD-PLAY rule that has an ablation flag in
# improved_ai.py. Audit turns each OFF (one at a time) vs champion.
CARD_RULES = [
    "bidder_boss_partner_save",
    "bidder_boss_weak_partner_save",
    "following_partner_boss_save",
    "following_all_remaining_void",
    "following_2nd_man_offsuit_boss_save",
    "following_2nd_man_low_trump_renege",
    "bidder_after_void_lead",
    "bidder_endgame_trump_timing",
    # bidder_trump_save_lead REMOVED v2.31.34 — ablation proved net-negative
    # (held-out +0.38pt z=2.62 to delete); rule no longer exists in code.
    "defender_partner_trump_load",
    "signal_3rd_man_high",
    "partner_low_trump_signal_response",
    "minwin_after_void",   # SHIPPED v2.31.27, champion default-ON (strict);
                           # off: ablation reverts to pre-2.31.27 max-trump.
    "holdup_2nd_def",      # SHIPPED v2.31.28 (hd:hi98), champion default-ON;
                           # off: ablation reverts to pre-2.31.28 over-ruff.
    "endgame_lead_boss",   # SHIPPED v2.31.30 (el:strict), champion default-ON;
                           # off: ablation reverts to pre-2.31.30 boss-save.
    "partner_save_boss5",  # FIX v2.31.39, champion default-ON: never burn
                           # the 5 of trump (rank 102, unbeatable) to
                           # respond to a partner-winning low-trump signal —
                           # it is a guaranteed future trick. off: reverts.
    "defender_cash_boss_ah",  # FIX v2.31.43, champion default-ON: a
                           # defender FOLLOWING who can win the current
                           # trick with A♥ while the bidding side is
                           # winning it cashes A♥ now when it is PROVABLY
                           # unbeatable for this trick (5/J-trump gone or
                           # all later seats known trump-void) — instead of
                           # dribbling it to the dead last trick because
                           # is_card_boss can't prove boss while J-trump is
                           # in the kitty (user-reported v2.31.42). off:
                           # reverts to the kitty-blind is_card_boss path.
    "partner_signal_overtake_guard",  # SHIPPED v2.31.51, champion
                           # default-ON (rig +0.08/+0.09, comeback
                           # +0.10/+0.12, n.s.). Don't overtake a partner
                           # already winning with trump when a not-void
                           # later opp could hold a higher trump (futile).
                           # off: reverts to always-respond-to-signal.
    "def_ruff_be_eg",          # SHIPPED v2.31.46, champion default-ON
                           # (rig-NEUTRAL): defender cheap-ruffs the bidder's
                           # endgame offsuit Ace instead of strict 2nd-man-
                           # low sluff. off: reverts to strict 2nd-man-low.
    "partner_off_boss_save",   # SHIPPED v2.31.46, champion default-ON
                           # (rig-NEUTRAL): don't ruff partner's winning
                           # offsuit card when it is the led-suit boss AND
                           # all remaining opps provably trump-void. off:
                           # reverts to always-ruff-to-secure.
    "defender_cash_ah_jlate",  # SHIPPED v2.31.45, champion default-ON
                           # (rig-NEUTRAL: 50.04% primary / 50.03% held-out,
                           # z<0.35, comeback ~0). Looser defender A♥ cash:
                           # 5-trump gone + trick>=4 ⇒ treat J as dead even
                           # if unseen (would have been played by trick 4).
                           # Shipped for intuitive play / AI-logic trust at
                           # zero win-rate cost (v2.31.30 precedent). off:
                           # reverts to the strict 5-AND-J-provably-gone gate.
    "safe_pad4",               # FIX v2.31.55, champion default-ON: the
                           # _pad4 helper pads partial tricks for trick_winner
                           # probes (canBeat / cheapest-winner / 3rd-man-high).
                           # Legacy dummy was hardcoded 2♣ — which IS trump
                           # in clubs-trump games and ranks 87, above the real
                           # 3-10 of clubs. canBeat therefore misreported
                           # "can't beat" for low-trump candidates in clubs
                           # trump, and the AI dumped offsuit instead of
                           # over-trumping (user-reported, round T4 north
                           # held 4♣ vs 8♣). Fix: dummy is 2 of a non-trump
                           # suit. Primary 20k +0.39pt z=1.56 / held-out 30k
                           # +0.38pt z=1.85 (replicated, comeback +0.18/+0.22
                           # n.s.). off: reverts to the buggy 2♣ dummy.
    "bidder_lowtrump_dump",    # SHIPPED v2.31.62, champion default-ON.
                           # User-reported round: bidder N held only 2♥ as
                           # last trump on trick 3 of a 20-bid round, opps
                           # had A♥ available; leading 2♥ guaranteed-lost
                           # the trick and the bid. Rule (NARROW): if I'm
                           # bidder leading, have EXACTLY 1 trump left, and
                           # it is rank ≤ 87 (low-number trump, not Q/K/A/J/5),
                           # AND there's an unaccounted-for higher trump,
                           # lead my highest OFFSUIT instead. Rig: primary
                           # 20k +0.50pt z=+2.00 / held-out 30k +0.38pt
                           # z=+1.85 (replicated, comeback +0.65/+0.10).
                           # Earlier broad variant (any my_max_trump <
                           # highest_remaining) was -2.54pt z=-10.16 — gate
                           # MUST stay narrow.
    "off2_beat_off_bidlead",   # SHIPPED v2.31.66, champion default-ON
                           # (rig-NEUTRAL: +0.01pt z=+0.05 primary 20k,
                           # comeback -0.01 z=-0.03 — v2.31.30 trust-fix
                           # precedent). The "2nd-man-low" mantra is a
                           # TRUMP heuristic; on OFFSUIT, 2nd-man defender
                           # following a BIDDER offsuit lead should beat
                           # with the cheapest higher led-suit card.
                           # Forces 3rd-man (bidder's partner) to over-
                           # beat with higher offsuit, commit trump, or
                           # concede — and saves 4th-man (my partner)
                           # from having to ruff in. User-derived from a
                           # screenshot where the AI played strict-low.
                           # off: reverts to strict 2nd-man-low.
    "take_t4_2nd",             # SHIPPED v2.31.57, champion default-ON.
                           # On trick 4+, 2nd-man plays the CHEAPEST card
                           # that wins the partial-trick state — regardless
                           # of trump vs offsuit, renege capability, or
                           # role. The general principle: at trick 4 the
                           # winner of this trick leads the final trick
                           # with all other players holding only ONE card
                           # each — positional advantage worth taking
                           # higher cards for. Strict 2nd-man-low used to
                           # "save" for later but at trick 4 there is
                           # nothing later to save for. User-derived
                           # 2026-05-21 from a round-T4 screenshot where
                           # West reneged J♥ on the bidder's 2♥ lead,
                           # bid made; broader rule generalizes to all
                           # roles ("take trick 4 by any means"). Rig:
                           # primary 20k +0.60pt z=2.42, held-out 30k
                           # +0.70pt z=3.41 (replicated, comeback +0.54
                           # directional). off: reverts to strict 2nd-
                           # man-low at trick 4+.
    "partner_winning_renege_prune",  # FIX v2.31.39, champion default-ON:
                           # partner-winning block treats a reneging opp as
                           # trump-void if every possibly-reneged trump is
                           # PROVABLY GONE (my hand OR already played), not
                           # just "all in my hand". Stops the boss 5/J/AH
                           # being dumped on an already-won trick (user-
                           # reported T3). off: reverts to hand-only check.
    # following_2nd_man_after_void / ruff_cheap (v2.31.25) and trick3_exception
    # (v2.31.26) removed — audit net-negative, no longer in code.
]


def _card_off(rule):
    p = Policy()
    p.name = f"off:{rule}"
    p.ai_flags = {rule: False}
    return p


REGISTRY = {
    "champion":           Policy(),            # baseline self-test → ~50%
    "no-desperation":     NoDesperation(),
    "no-cruise":          NoCruise(),
    "no-desp-no-cruise":  NoDespNoCruise(),
    # CUTTHROAT baseline. Bidding side gated for FFA (no partner concept —
    # partner_bid forced to 0, spoiler off). Card-play coalition rules
    # C1 (take_from_bidder) and C2 (don't_overtake — pass-2 gated on
    # _bidder_has_played) default-ON since v2 (this commit). The pre-coalition
    # baseline (both flags False) is preserved as opt-in 'cutthroat-stripped'
    # below for ablation. Self-test = 4 of these against each other should
    # still win ~25% each (all seats run the same policy, symmetric).
    "champion-cutthroat": Policy(cutthroat=True,
                                 ai_flags={'cutthroat_c1_take_from_bidder': True,
                                           'cutthroat_c2_dont_overtake': True}),
}
CHAMPION_CUTTHROAT = REGISTRY["champion-cutthroat"]

# BASELINE-PARTNER-IN-CUTTHROAT (chunk B measurement policy): partner-mode
# champion (cutthroat=False — partner rules ON, partner_bid honored, spoiler
# default off) placed in 1 cutthroat seat vs 3x champion-cutthroat (stripped).
# This is THE delta measurement: does stripping the partner rules from the
# cutthroat AI help, hurt, or wash? Baseline win% < 25% → stripping is an
# improvement (the stripped version beats partner-AI in cutthroat).
# Baseline win% > 25% → stripping HURT and we need to investigate.
BASELINE_PARTNER_IN_CUTTHROAT = Policy(cutthroat=False)
BASELINE_PARTNER_IN_CUTTHROAT.name = "baseline-partner-in-cutthroat"
REGISTRY["baseline-partner-in-cutthroat"] = BASELINE_PARTNER_IN_CUTTHROAT

for _r in CARD_RULES:
    REGISTRY[f"off:{_r}"] = _card_off(_r)


# CUTTHROAT BIDDING PHASE 2A — three tightening variants on top of
# champion-cutthroat (Chunk A baseline). Each isolates one threshold class
# so the rig attributes win-rate delta to that single change.
#
#   cutthroat-tight-20: 20-bid requires >=4 trump (drops 5+J@2-3 trump,
#                       5+AH@3 trump). Partner-era patterns assumed partner
#                       could cover one trick; solo can't.
#   cutthroat-tight-25: 25-bid requires 5+J+AH OR 5+J+T3 (i.e. the J anchor
#                       AND either AH or 5-trump depth). Drops 5+AH+T3
#                       (no J → solo can't extract J safely) AND the
#                       opp_bid25→30 demotion routes through H3.
#   cutthroat-kill-30:  30-bid requires 5+J+AH+AT+T1 (=>5 trump incl. all
#                       four top anchors). Drops 5+J+AH@T4 (no AT) and
#                       5+J@T5 (no AH) — both 30-bid suicide solo.
#
# All three set cutthroat=True so the cutthroat normalization (partner_bid=0,
# spoiler off, partner-mode tightening flags FORCED off) fires correctly.
# Partner-mode bit-identity is preserved by the `else: cutthroat_tight_*=False`
# guard inside bidding.decide_bid.
class CutthroatTight20(Policy):
    name = "cutthroat-tight-20"
    def __init__(self):
        super().__init__(cutthroat=True)
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  cutthroat=True, cutthroat_tight_20=True)


class CutthroatTight25(Policy):
    name = "cutthroat-tight-25"
    def __init__(self):
        super().__init__(cutthroat=True)
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  cutthroat=True, cutthroat_tight_25=True)


class CutthroatKill30(Policy):
    name = "cutthroat-kill-30"
    def __init__(self):
        super().__init__(cutthroat=True)
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  cutthroat=True, cutthroat_kill_30=True)


REGISTRY["cutthroat-tight-20"] = CutthroatTight20()
REGISTRY["cutthroat-tight-25"] = CutthroatTight25()
REGISTRY["cutthroat-kill-30"]  = CutthroatKill30()


# SURGICAL TIGHT-20 — SHIPPED v2.31.77 (this commit) as champion-cutthroat
# default-on. Pattern-targeted demotion driven by the
# cutthroat_pattern_makerate.py output @ 2000 deals (commit 4b4858d).
# Symmetric A-vs-B set-rate (4 seats each config, deals=2000):
#   primary  seed-base=0       Δ=-1.24pt z=-3.05 SIGNIFICANT
#                              (15s -2.18 z=-4.61, 20s +0.66 z=+0.79)
#   held-out seed-base=5000000 Δ=-0.98pt z=-2.42 SIGNIFICANT (replicated)
#                              (15s -1.82 z=-3.87)
# Direction: NEGATIVE Δ set-rate = GOOD here (fewer overall sets — healthier
# bidding population). Demoted 20-bid hands fall through to 15-bid; their
# pattern-level make-rate jumps from ≤36% at 20 to 35-88% at 15.
#
# The coarse cutthroat_tight_20 above (trump_count<4) drops ALL T2/T3
# 20-bids including 5+J@T3 (analyzer make-rate ~57.6% = +EV); the surgical
# rule targets ONLY the make-rate≤36% patterns and lets 5J+T3 / 5+T4 keep
# bidding 20.
#
# AGGRESSIVE variant — surgical + ALSO demotes 5+T4 (n=232, make-rate
# 53.9%, borderline). Result @ 2000 deals: a STATISTICAL TIE vs surgical
# (Δ=-1.23/-0.99 primary/held-out vs surgical -1.24/-0.98). The extra
# 5+T4 demotion adds ~zero EV. Shipped: SURGICAL (minimum intervention).
# Aggressive kept as opt-in for forward reference.
#
# This variant is retained as a CHALLENGER name even though its behavior
# is now bit-identical to champion-cutthroat — useful for ablation (test
# champion-cutthroat WITHOUT the shipped surgical rule by registering a
# without-surgical variant, future work).
class CutthroatSurgicalTight20(Policy):
    name = "cutthroat-tight-20-surgical"
    def __init__(self):
        super().__init__(cutthroat=True)
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  cutthroat=True,
                                  cutthroat_surgical_tight_20=True)


class CutthroatAggressiveTight20(Policy):
    name = "cutthroat-tight-20-aggressive"
    def __init__(self):
        super().__init__(cutthroat=True)
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  cutthroat=True,
                                  cutthroat_aggressive_tight_20=True)


# ABLATION: champion-cutthroat WITHOUT the shipped surgical tight-20 rule
# (the meaningful regression test now that surgical is shipped default-ON).
# Use this as the BASELINE to measure whether the surgical rule keeps
# paying as the downstream coalition / L1-L3 rules evolve.
class NoSurgicalTight20(Policy):
    name = "no-surgical-tight-20"
    def __init__(self):
        super().__init__(cutthroat=True,
                         cutthroat_surgical_tight_20=False,
                         ai_flags={'cutthroat_c1_take_from_bidder': True,
                                   'cutthroat_c2_dont_overtake': True})


REGISTRY["cutthroat-tight-20-surgical"]   = CutthroatSurgicalTight20()
REGISTRY["cutthroat-tight-20-aggressive"] = CutthroatAggressiveTight20()
REGISTRY["no-surgical-tight-20"]          = NoSurgicalTight20()


# CUTTHROAT COALITION (opt-in challengers; champion-cutthroat default OFF).
# Two coordinated defender rules — see improved_ai.py for the gates:
#   C1 (cutthroat_c1_take_from_bidder): defender following, BIDDER currently
#       winning the trick, set/made not locked → play cheapest card that
#       beats the bidder. Captures every "take from the bidder" case across
#       all positions and tricks (broader than def_ruff_be_eg / take_t4_2nd
#       / off2_beat_off_bidlead, which all stay enabled as narrow specifics).
#   C2 (cutthroat_c2_dont_overtake): defender following, ANOTHER DEFENDER
#       currently winning, BIDDER HAS ALREADY PLAYED, set not locked →
#       play_lowest. Don't burn cards overtaking a teammate-of-convenience;
#       conserve for tricks the bidder might win.
# Together: when one defender wins the trick the others stay cheap; when
# the bidder wins, every defender who can take cheaply does.
#
# pass-1 history (commit 550ad35 / 61ebe61): the FIRST cut of C2 had no
# "bidder has played" gate. Symmetric A-vs-B set-rate test showed
# coalition made bidders 1.36pt MORE successful (z=-3.36), concentrated
# at 15-bids (-2.02pt). DIAGNOSIS: with C2 firing while the bidder was
# still downstream, the next defender played low and the bidder over-
# trumped cheaply — the coalition was handing the bidder free tricks.
# pass-2 (current): C2 now gated on _bidder_has_played; v1 inherits the
# fix (the buggy pre-2-pass form is preserved only in git history,
# commits 550ad35 + 61ebe61 — no behavior preservation in code).
#
# cutthroat-c1-only      = C1 alone (sanity check: is C1 net-positive
#                          without C2?). If C1 alone wins and v2 does
#                          not beat it, ship C1, drop C2.
# cutthroat-coalition-v2 = C1 + tightened C2 (pass-2 of the coalition).
# cutthroat-coalition-v1 = name retained; behavior identical to v2 now
#                          (the C2 tightening is in the rule body, both
#                          flag combos enable it). Kept as an alias so
#                          existing harness commands / commit refs still
#                          work; do not test it separately from v2.
CUTTHROAT_C1_ONLY = Policy(cutthroat=True,
                           ai_flags={'cutthroat_c1_take_from_bidder': True,
                                     'cutthroat_c2_dont_overtake': False})
CUTTHROAT_C1_ONLY.name = "cutthroat-c1-only"
REGISTRY["cutthroat-c1-only"] = CUTTHROAT_C1_ONLY

CUTTHROAT_COALITION_V1 = Policy(cutthroat=True,
                                ai_flags={'cutthroat_c1_take_from_bidder': True,
                                          'cutthroat_c2_dont_overtake': True})
CUTTHROAT_COALITION_V1.name = "cutthroat-coalition-v1"
REGISTRY["cutthroat-coalition-v1"] = CUTTHROAT_COALITION_V1

CUTTHROAT_COALITION_V2 = Policy(cutthroat=True,
                                ai_flags={'cutthroat_c1_take_from_bidder': True,
                                          'cutthroat_c2_dont_overtake': True})
CUTTHROAT_COALITION_V2.name = "cutthroat-coalition-v2"
REGISTRY["cutthroat-coalition-v2"] = CUTTHROAT_COALITION_V2

# SHIP: cutthroat-coalition-v2 promoted to champion-cutthroat default-ON
# (this commit). Symmetric A-vs-B set-rate (deals=2000):
#   primary  seed-base=0       Δ=+1.45pt z=+3.56 SIGNIFICANT
#   held-out seed-base=5000000 Δ=+1.08pt z=+2.65 SIGNIFICANT (replicated)
# Per-bid breakdown (primary): 15s +1.70 z=+3.54, 20s +1.12 z=+1.38,
# 25s +0.64 z=+0.51, 30s n=3. Damage concentrated at 15-bids — same
# regime that pass-1 BROKE (-2.02pt at 15s), now fixed and net-positive.
# Sanity: C1-ALONE without C2 is NEGATIVE (Δ=-1.02pt z=-2.50, 15s -1.22
# z=-2.56). C1 by itself hands defenders' beats to a non-tightened
# downstream that the bidder then exploits / mis-takes context. The
# combo (C1 + bidder_has_played-gated C2) is the win — both flags
# required for the +EV signal. Opt-in 'cutthroat-stripped' below preserves
# the pre-coalition baseline for ablation tests.
CUTTHROAT_STRIPPED = Policy(cutthroat=True,
                            ai_flags={'cutthroat_c1_take_from_bidder': False,
                                      'cutthroat_c2_dont_overtake': False})
CUTTHROAT_STRIPPED.name = "cutthroat-stripped"
REGISTRY["cutthroat-stripped"] = CUTTHROAT_STRIPPED


# ─────────────────────────────────────────────────────────────────────────
# CUTTHROAT L1 / L2 / L3 — SCORE-AWARE COALITION RULES
# ─────────────────────────────────────────────────────────────────────────
# Three score-aware rules layered on TOP of the C1/C2 coalition. All read
# state.pre_round_scores (4-vec of per-seat game totals at round start)
# threaded by cutthroat_runner. Cutthroat-only (no-op in partner mode);
# game-context-only (no-op in round-only harnesses — pre_round_scores=None).
#
# L3 (cutthroat_l3_bidder_winning_game) — bidder making this bid wins them
#     the game (pre_round_scores[bid_winner] + high_bid >= 120). Switch to
#     MAX-AGGRESSION: C2 don't-overtake suppression OFF; C1 takes regardless
#     of who currently winning; top-3 trump save disabled. NO THRESHOLD.
#
# L1 (cutthroat_l1_leader_self_nickel) — I'm the runaway leader-of-the-game-
#     so-far (my pre_round_score >= leader_min AND ahead of next-best by
#     >= leader_gap). Soften C1: when taking, refuse if cheapest winner is
#     a top-3 trump (conserve high cards; bank cheap tricks only).
#     Thresholds: (cutthroat_l1_min, cutthroat_l1_gap).
#
# L2 (cutthroat_l2_dont_help_leader) — ANOTHER defender is the runaway
#     leader. When that leader is currently winning the trick (cw ==
#     leader_seat), suppress C2's "don't overtake" so I TAKE from the leader.
#     Extends C1 to "take from the leader-defender" too.
#     Thresholds: (cutthroat_l2_min, cutthroat_l2_gap).
#
# Threshold sweep: register variants for each (min, gap) pair in the spec.

def _l_rule(name: str, flags: dict):
    p = Policy(cutthroat=True)
    p.name = name
    # Inherit C1+C2 coalition defaults from champion-cutthroat (default-on);
    # callers add cutthroat_l*_* flags + thresholds on top.
    base = {'cutthroat_c1_take_from_bidder': True,
            'cutthroat_c2_dont_overtake': True}
    base.update(flags)
    p.ai_flags = base
    return p


# L3 — no threshold; one variant.
REGISTRY["cutthroat-l3"] = _l_rule(
    "cutthroat-l3",
    {'cutthroat_l3_bidder_winning_game': True},
)


# L1 threshold sweep: (leader_min, leader_gap) pairs.
for (_lmin, _lgap) in ((100, 40), (95, 30), (90, 25)):
    _nm = f"cutthroat-l1-{_lmin}-{_lgap}"
    REGISTRY[_nm] = _l_rule(_nm, {
        'cutthroat_l1_leader_self_nickel': True,
        'cutthroat_l1_min': _lmin,
        'cutthroat_l1_gap': _lgap,
    })


# L2 threshold sweep: same (min, gap) pairs.
for (_lmin, _lgap) in ((100, 40), (95, 30), (90, 25)):
    _nm = f"cutthroat-l2-{_lmin}-{_lgap}"
    REGISTRY[_nm] = _l_rule(_nm, {
        'cutthroat_l2_dont_help_leader': True,
        'cutthroat_l2_min': _lmin,
        'cutthroat_l2_gap': _lgap,
    })


# L-ALL-BEST: L1+L2+L3 with TBD thresholds; pre-registered with the most
# conservative (100,40) for both. The sweep-driven "best" combo is created
# dynamically once the L1/L2 sweep winners are known (see below).
REGISTRY["cutthroat-l-all-best"] = _l_rule("cutthroat-l-all-best", {
    'cutthroat_l3_bidder_winning_game': True,
    'cutthroat_l1_leader_self_nickel': True,
    'cutthroat_l2_dont_help_leader': True,
    'cutthroat_l1_min': 100, 'cutthroat_l1_gap': 40,
    'cutthroat_l2_min': 100, 'cutthroat_l2_gap': 40,
})


# CUTTHROAT N1 NICKEL-GRAB (opt-in challenger on TOP of coalition-v2).
# When set OR made is mathematically LOCKED, switch from coalition mode
# (which is about influencing whether the bid is made/set — moot now)
# to point-greedy mode: take the cheapest winning card, but NEVER burn
# a top-3 trump (rank >= 100 — 5 of trump, J of trump, A♥ when trump
# != hearts) to do so. N1 sits FIRST in the defender cutthroat block;
# its early-return preempts C1 and C2 in the locked regime. C1 and C2
# already gate on `not locked` so the not-locked regime is unchanged.
#
# Hypothesis: defenders banking cheap free tricks late in a decided
# round leaves them with more raw round points (+EV) without increasing
# the bidder's bid-quality (set-rate may be roughly flat — set is
# decided by the time N1 fires). Lesson from pass-1 C1 sanity (commit
# 3f26177): aggressive defender takes that burn top trump are
# net-negative — nickel-grab restricts the take to free tricks.
CUTTHROAT_NICKEL_GRAB = Policy(cutthroat=True,
                               ai_flags={'cutthroat_c1_take_from_bidder': True,
                                         'cutthroat_c2_dont_overtake': True,
                                         'cutthroat_n1_nickel_grab': True})
CUTTHROAT_NICKEL_GRAB.name = "cutthroat-nickel-grab"
REGISTRY["cutthroat-nickel-grab"] = CUTTHROAT_NICKEL_GRAB


# FORCE-EXTRACT challenger variants (opt-in rule, default absent in champion).
# Each enables the rule + one partner-trump-rich proxy; data picks the proxy.
def _fx(proxy: str):
    p = Policy()
    p.name = f"fx:{proxy}"
    p.ai_flags = {'following_3rd_man_force_extract': True,
                  f'fx_proxy_{proxy}': True}
    return p


for _p in ('shed', 'drew', 'led_trump', 'any'):
    REGISTRY[f"fx:{_p}"] = _fx(_p)


# HOLD-UP #30 variants (opt-in; champion default off). 2nd-man defender on
# an offsuit lead with no low trump to ruff cheap → hold up (follow/play
# non-trump) instead of wasting a high/boss trump on a junk trick.
def _hd(name: str, flags: dict):
    p = Policy()
    p.name = name
    p.ai_flags = dict(flags, holdup_2nd_def=True)
    return p


# hd:hi98 removed — it IS the champion now (SHIPPED v2.31.28, default-ON).
# The meaningful test is off:holdup_2nd_def (auto from CARD_RULES, ablates
# the shipped rule). hd:hi98_force / hd:hi97 kept as forward-variants:
# "would champion + forcer-gate / broader ≥Q threshold do better than the
# shipped ≥K?" (champion = baseline; these add one flag on top).
REGISTRY["hd:hi98_force"] = _hd("hd:hi98_force", {'holdup_force': True})
REGISTRY["hd:hi97"]       = _hd("hd:hi97", {'holdup_hi97': True})    # ≥Q (broader)


# ENDGAME LEAD-BOSS #32 (opt-in; champion default off). Defender on lead in
# the endgame (trick>=4) with the bidding team trump-void → lead the boss
# now (win + keep the lead) instead of saving it / leading offsuit.
#   el:strict — opponents KNOWN trump-void only (deduction-only)
#   el:est    — also estimatedTrumpRemaining==0 (broader; est can misfire)
def _el(name: str, flags: dict):
    p = Policy()
    p.name = name
    p.ai_flags = dict(flags, endgame_lead_boss=True)
    return p


# el:strict removed — it IS the champion now (SHIPPED v2.31.30, default-ON
# strict). Meaningful test = off:endgame_lead_boss (auto from CARD_RULES).
# el:est kept as a forward-variant (champion + estimate-based void too).
REGISTRY["el:est"]    = _el("el:est", {'endgame_lead_boss_est': True})


# safe:pad4 promoted to champion v2.31.55 (default-ON; rig +0.39pt z=1.56
# primary 20k / +0.38pt z=1.85 held-out 30k, replicated). The meaningful
# test now = off:safe_pad4 (auto from CARD_RULES, reverts to the buggy
# 2♣ dummy). The legacy dummy was logically wrong in clubs-trump games.


# follow_trump_floor canBeat refinement — tested 2026-05-20, rig-NEUTRAL
# (49.99% z=-0.02 unconditional, 0.00 comeback @ 20k). Backed out.
# The data layer (min_trump_rank tracking in round_runner._update_known_voids)
# is kept always-on as scaffolding for further iteration.


# BURN-FORCE 3RD #35b (opt-in; champion default off — TESTED rig-NEUTRAL).
# Defender 3rd-man with trump on a trick currently won by an opponent:
# play the LOWEST non-top-3 trump for which every remaining over-trump
# is a top-3 (5/J/A♥). Idea: either I win cheaply OR 4th-man burns a
# top-3 to win. RESULT 2026-05-20: 50.01% z=+0.02 / comeback +0.02 @ 20k
# — fires too rarely (late-round, requires K/Q/A_trump accounted-for)
# and when it does, picks the same card max-trump would pick anyway in
# most cases. Kept opt-in for future refinement; do NOT ship default-ON.
def _burnforce_3rd():
    p = Policy()
    p.name = "bf:3rd"
    p.ai_flags = {'burnforce_3rd': True}
    return p


REGISTRY["bf:3rd"] = _burnforce_3rd()


# BIDDER-PARTNER-FLOOR-LEAD #35c (opt-in; champion default off — TESTED
# rig-NEUTRAL). Bidder leading with ≥2 trumps, partner_floor ≥98, and all
# over-trumps for partner's floor card accounted for (mine or played).
# Lead lowest trump so partner cashes their high trump here, I save mine.
# RESULTS 2026-05-20 @ 20k: loose gate (floor ≥98, no safety) 49.75% z=-0.99
# (mildly negative — partner with K loses to opp's A♥). Tight gate (all
# over-trumps accounted-for) 49.98% z=-0.07 / comeback +0.06 z=+0.14 — dead
# neutral, fires too rarely. Three consecutive rig-neutrals on min_trump_rank
# heuristic rules (ftf:floor 49.99, bf:3rd 50.01, bf:partnerlead 49.98)
# suggest the floor data is sound but hard to leverage via simple
# position-based rules. Future work: monte-carlo rollouts that use the
# floor as a constraint, not a heuristic flag.
def _bidder_partner_floor_lead():
    p = Policy()
    p.name = "bf:partnerlead"
    p.ai_flags = {'bidder_partner_floor_lead': True}
    return p


REGISTRY["bf:partnerlead"] = _bidder_partner_floor_lead()


# UPBID15 promoted to champion v2.31.56 (default-ON; rig +5.42pt z=21.68
# primary 20k / +5.30pt z=25.96 held-out 30k, replicated, comeback n.s.).
# Jack2112-derived from the bidLog (5 of 13 logged divergences match the
# exact pattern). When auction stands at 15 and hand computes as a 15-bid
# (which the old champion would pass on), overbid to 20. Excludes dealer
# and partner-bid-15. The pre-2.18.1 5M-sim calibration that dropped this
# from the 20-bid threshold ran against a much weaker champion — current
# card-play (safe:pad4 + pso:guard + dca:jlate + pob:save + dre:bidace_eg)
# converts the borderline 15-strength hands well enough to make 20.
class NoUpBid15(Policy):
    name = "bid:no-upbid15"
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  enable_upbid15=False)


REGISTRY["bid:no-upbid15"] = NoUpBid15()


# ENDGAME_DENY (opt-in challenger; dormant rule already in improved_ai.py).
# Bidder side, opp at 110+ (one bid from winning):
#   Leading  → max trump (or max playable if no trump)
#   Following→ if opp currently winning AND I have a winning card,
#              play the MIN-sufficient winner. Else play_lowest
#              (preserve strength).
# Tested 2026-05-22 rig-NEUTRAL (50.04% z=0.18 primary 20k / 50.02%
# z=0.11 held-out 30k) — kept here for future re-test when more
# expert data accumulates, since the rule fires rarely.
def _endgame_deny():
    p = Policy()
    p.name = "egd:on"
    p.ai_flags = {'endgame_deny': True}
    return p


REGISTRY["egd:on"] = _endgame_deny()


# off2:beat_bidlead promoted to champion v2.31.66 (default-ON; rig-NEUTRAL
# +0.01pt z=+0.05 primary 20k, v2.31.30 trust-fix precedent). Meaningful
# test now = off:off2_beat_off_bidlead (auto from CARD_RULES, reverts to
# strict 2nd-man-low). The broader off2:beat_anyopp (any-opp lead, not just
# bidder) also tested rig-NEUTRAL (+0.01pt z=+0.03) and is kept as a
# forward-variant opt-in challenger.
def _off2_beat_anyopp():
    p = Policy()
    p.name = "off2:beat_anyopp"
    p.ai_flags = {'off2_beat_off_anyopp': True}
    return p


REGISTRY["off2:beat_anyopp"]  = _off2_beat_anyopp()


# BIDDER-LOWTRUMP-DUMP #38 (opt-in; champion default off). User-reported
# round: bidder N held only the lowest remaining trump (2♥) on trick 3
# of a 20-bid round, opps had A♥ available, leading 2♥ was a guaranteed
# loss. Rule: when bidder is leading and my best trump is BELOW the
# highest unplayed trump (= an opp could over-trump), lead my highest
# offsuit instead. Saves my dead trump for forced-follow later AND
# gives the offsuit a real chance to steal a trick.
# bidder_lowtrump_dump promoted to champion v2.31.62 (default-ON; rig
# +0.50pt z=+2.00 primary 20k / +0.38pt z=+1.85 held-out 30k). The
# meaningful test now = off:bidder_lowtrump_dump (auto from CARD_RULES).


# DEFENDER-TAKE-JAH-LATE #37 (opt-in; champion default off — TESTED
# rig-NEUTRAL 2026-05-21: 50.08% z=+0.33 unconditional, comeback
# +0.05 z=+0.13 @ 20k). Defender 2nd-man on a late trick (>=4) when
# the bidder led TRUMP at a rank a top-3 (5/J/A♥) can renege: TAKE
# the trick with the lowest top-3 trump instead of reneging. Idea
# was sound (user-derived from a real round-T4 screenshot where
# reneging J♥ cost a 40pt swing), but the conjunction of conditions
# is too narrow — fires rarely, and when it does, +EV and -EV cases
# roughly cancel (saving J♥ is +EV when 5♥ is in opp's hand, -EV when
# 5♥ is in kitty/already-played). Kept opt-in for forward reference;
# do NOT ship.
# take_t4_2nd promoted to champion v2.31.57 (default-ON). Meaningful
# test now = off:take_t4_2nd (auto from CARD_RULES, reverts to strict
# 2nd-man-low at trick 4+).


# pso:guard removed — it IS the champion now (SHIPPED v2.31.51, default-ON;
# rig consistently +0.08/+0.09 unconditional & +0.10/+0.12 comeback, both
# samples, z<1 n.s. — shipped as a non-negative trust fix per v2.31.30
# precedent). Meaningful test = off:partner_signal_overtake_guard (auto
# from CARD_RULES). user-reported: North played A♥ over partner's winning
# 8♥ though a possible East J♥ beats A♥ regardless.


# dre:bidace_eg / pob:save removed — both ARE the champion now (SHIPPED
# v2.31.46, default-ON; rig-NEUTRAL 50.00%/50.00% z≈0 both samples,
# shipped for intuitive play / AI-logic trust per v2.31.30 precedent +
# user-confirmed j_trump_dump_void deduction). Meaningful tests are the
# auto off:def_ruff_be_eg / off:partner_off_boss_save from CARD_RULES.
# NOTE: j_trump_dump_void (the sound "follower J-on-5-lead → trump-void"
# deduction) is baked into round_runner._update_known_voids (harness
# deduction layer, NOT an ai_flag) — it only ever adds PROVABLY-true
# voids, so it is not ablation-gated.


# dca:jlate removed — it IS the champion now (SHIPPED v2.31.45, default-ON;
# rig-neutral, shipped for intuitive play / AI-logic trust). The meaningful
# test is off:defender_cash_ah_jlate (auto from CARD_RULES, ablates back to
# the strict 5-AND-J-provably-gone gate of v2.31.43).


class BidTighten5JT4(Policy):
    """DATA-DRIVEN (5M v2.31.27 re-run): category 5_J_T4 (has5 ∧ hasJ ∧ 4
    trump ∧ no A♥ ∧ no A-trump) refreshed round-EV says open 20 (EV+19.50)
    not 25 (EV+18.91). decide_bid currently opens 25. Surgical: only when
    OPENER (chb==0, pb==0) and the hand is EXACTLY that category and base
    decide_bid returned 25 → return 20 instead. 5_J_T5 (5 trump) stays 25
    (its rec did NOT flip), hence count==4 not >=4. Everything else untouched."""
    name = "bid:5jt4_25to20"

    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        b, s = bidding.decide_bid(hand, chb, pi, dl, ts, os, pb)
        if (b == 25 and s is not None and chb == 0 and pb == 0
                and bidding.has_five(hand, s) and bidding.has_jack(hand, s)
                and not bidding.has_ace_hearts(hand)
                and not bidding.has_ace_trump(hand, s)
                and bidding.count_trumps(hand, s) == 4):
            return 20, s
        return b, s


REGISTRY["bid:5jt4_25to20"] = BidTighten5JT4()


# SPOILER (opt-in; champion default off). When an opponent holds a bid that
# — given how often bids overmake — likely carries them to 120, seize the
# contract with the minimum overbid even without a hand to justify it
# (drops the desperation we_need>30 gate; the 105-105 / near-game-point
# case). ONLY meaningful in a GAME-context harness (needs live scores).
class Spoiler(Policy):
    name = "spoiler"
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  enable_spoiler=True)


REGISTRY["spoiler"] = Spoiler()


# RANDOMIZED AUTO-15 PASS (opt-in; champion default prob 0.0 = current nd,
# bit-identical). The auto-15 on residual (5M-oracle-pass) hands is +EV
# but deterministic → predictable/exploitable and human-frustrating. These
# variants pass that residual open with probability p (mixed strategy).
# The rig measures the EV cost of each dial so the user can choose the
# setting with eyes open (cost is informational, NOT a ship gate — this
# is a deliberate enjoyment/unpredictability-over-stats choice).
class RndPass(Policy):
    def __init__(self, p):
        self.p = p
        self.name = f"rnd:p{int(p*100):02d}"
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  loose_open_pass_prob=self.p)


for _p in (0.25, 0.50, 0.75):
    _rp = RndPass(_p)
    REGISTRY[_rp.name] = _rp


# RANDOMIZED DESPERATION 25-SACRIFICE (opt-in; champion default 0.0 =
# bit-identical). The hand-blind overbid to 25 (deny opp's game-point 20)
# is exploitable + frustrating. These variants pass it with probability p
# ONLY when the hand is crap for 25 (cannot even make 20 → pure
# sacrifice); 20-overbids and real (can20_60) hands stay deterministic.
# Rig measures the EV cost of each dial (informational, not a gate —
# enjoyment/unpredictability-over-stats).
class RndDesp25(Policy):
    def __init__(self, p):
        self.p = p
        self.name = f"d25:p{int(p*100):02d}"
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  desp_overbid25_pass_prob=self.p)


for _p in (0.25, 0.50, 0.75):
    _rd = RndDesp25(_p)
    REGISTRY[_rd.name] = _rd


# NOTE: a desp:callbluff challenger (pass instead of the desperation
# sacrifice-overbid when holding "strong defensive trump") was built and
# REMOVED — fatally flawed: the bid is made BEFORE trump selection, so the
# AI cannot know its trump strength (the opponent picks the suit). The
# only always-trump card is A♥; everything else (5/J/high-trump in our own
# best suit) is irrelevant once the opponent chooses a different trump.
# Any real call-the-bluff must be SCORE/odds-driven (or A♥-only), not
# based on our hand's trump — and the all-AI rig cannot model a human who
# deliberately bluff-bids at game point. Parked pending user direction.


# ENDGAME POINT-BUDGET DENY (opt-in; champion default off). Bidder-side:
# when opponent is at game point (oppNeed<=10 to 120) a normal made bid
# still loses (defenders score), so play every trick must-win / never
# concede. ONLY meaningful in a GAME-context harness (needs team_scores);
# round-context evaluator passes team_scores=None → this is a no-op there.
_ed = Policy()
_ed.name = "endgame_deny"
_ed.ai_flags = {'endgame_deny': True}
REGISTRY["endgame_deny"] = _ed


# BIDDER LEAD LOW TRUMP (H-A; opt-in, champion default off). When the
# bidder is leading and the champion would lead a trump, lead the LOWEST
# trump instead of the highest (conserve boss-class high trump for
# later). Implemented at the TOP of the bidder-leading trump branch in
# improved_ai.py so it intercepts BOTH champion lead-high paths
# (len(trumps)>=3 return max, and >=1 return highest_trump). Reachable
# in all non-void / non-narrow-endgame bidder-leading cases (the
# bidder_after_void_lead site already leads low when opps are out).
# RESULT (2026-05-17): TESTED, NO-SHIP. Reachability proven (5153
# decision changes / 1500 games). Screen 30k deals: win 49.41%,
# z=-2.91 SIGNIFICANTLY NEGATIVE (no held-out run — direction wrong).
# The expert-divergence hypothesis does NOT replicate in simulation;
# leading lowest trump as bidder is net-negative. Champion correctly
# leads its highest trump. Do NOT re-test without a new mechanism.
_bllt = Policy()
_bllt.name = "bidder_lead_low_trump"
_bllt.ai_flags = {'bidder_lead_low_trump': True}
REGISTRY["bidder_lead_low_trump"] = _bllt


# BIDDER LOW-TRUMP OFFSUIT (opt-in; champion default off). Bidder leading
# with <=2 trump past trick 1: if cashing its (boss) top trump promotes a
# >=Q-class trump a defender is estimated to hold, lead offsuit instead
# (keep tempo, let partner ruff, deny the boss-up). Round-context rule.
# bidder_lowtrump_offsuit (B narrow + A broad) REMOVED — both proven
# structurally dead: the insertion site after bidder_trump_save_lead is
# never reached (0/1500 games) because bidder_after_void_lead returns
# first. The user's low-trump-lead idea must be tested by ablating/
# altering bidder_after_void_lead (already in CARD_RULES as
# off:bidder_after_void_lead), not via a new bolt-on rule.


# NOTE: the old mw:strict / mw:est opt-in challengers were removed — strict
# min-win is now SHIPPED (champion default-ON, v2.31.27). The meaningful
# test is now the ablation `off:minwin_after_void` (auto-created from
# CARD_RULES above), which reverts to pre-2.31.27 max-trump. The est
# variant was proven mildly negative and is not in the champion at all.


# LOOSER OPEN — SHIPPED v2.31.36 (champion default-ON via
# bidding.decide_bid enable_loose_open=True). Rig-confirmed +3.52pt
# held-out (z=17.2, 120k disjoint, replicated); data-derived from expert
# aggression (bid-wins/game 2.45 vs robr 1.39 at the SAME ~23% set rate).
# The old opt-in open:t3/t4/ah/at/loose challengers are GONE — open:loose
# IS the champion now, and t3/t4/ah/at are strict subsets of it (adding
# them on top of loose-champion is a no-op). The meaningful regression
# test is the ablation `no-loose-open` below (reverts to pre-2.31.36).
class NoLooseOpen(Policy):
    name = "no-loose-open"
    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        return bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  enable_loose_open=False)


REGISTRY["no-loose-open"] = NoLooseOpen()


# SEAT-AWARE OPEN (opt-in; champion default off). Forward-variant ON TOP
# of the shipped loose-champion. Question (user): does bid-order position
# matter? loose fires identically regardless of seat. This adds EXTRA
# late-position aggression: when loose-champion STILL passes a clean open
# (hand failed loose: <3 trump, no A♥, no A-trump) and the player is LATE
# in bid order (>=2 earlier players already passed → strong evidence
# partner+opps are weak, so the forced-bagged dealer likely holds junk),
# open 15 anyway on a residual weak hand.
#   open:seat2  late & >=2 trump
#   open:seat1  late & >=1 trump (very aggressive)
# bid-order position of p = (p - dealer - 1) mod 4 (0 = first to act,
# dealer never reaches here — it is force-bagged at 15).
class SeatOpen(Policy):
    def __init__(self, min_trump):
        self.min_trump = min_trump
        self.name = f"open:seat{min_trump}"

    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        b, s = bidding.decide_bid(hand, chb, pi, dl, ts, os, pb)
        if b != 0:
            return b, s                  # champion (incl. loose) bids
        if chb != 0 or pb > 0:
            return b, s                  # not a clean open spot
        we_need = 120 - ts
        if we_need <= 15 and os <= 85:   # cruise / ahead-protection
            return b, s
        bidorder = (pi - dl - 1) % 4
        if bidorder < 2:                 # early position — status quo (loose)
            return b, s
        fb = bidding.find_best_trump_suit(hand)
        suit, tc = fb['suit'], fb['trumpCount']
        return (15, suit) if tc >= self.min_trump else (b, s)


for _mt in (1, 2):
    REGISTRY[f"open:seat{_mt}"] = SeatOpen(_mt)


# EARLY-POSITION OPEN (opt-in; champion default off). User insight: the
# real value of an aggressive open is largely a DENIAL effect — a P1 15
# sets the floor BEFORE opponents act, so they can only bid 20+ (riskier,
# more sets) or pass (concede the contract). That blocking value is
# HIGHEST from early position (mirror-opposite of open:seat). When
# loose-champion STILL passes a clean open (hand failed loose) and the
# player is EARLY in bid order (bidorder < 2 — first or second to act,
# i.e. P1/P2), open 15 anyway on a residual weak hand to deny opponents
# the cheap 15. open:early2 = early & >=2 trump; open:early1 = early &
# >=1 trump. Tests whether the extra-open edge concentrates early
# (denial-driven) vs late (open:seat, info-driven) vs neither.
class EarlyOpen(Policy):
    def __init__(self, min_trump):
        self.min_trump = min_trump
        self.name = f"open:early{min_trump}"

    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        b, s = bidding.decide_bid(hand, chb, pi, dl, ts, os, pb)
        if b != 0:
            return b, s                  # champion (incl. loose) bids
        if chb != 0 or pb > 0:
            return b, s                  # not a clean open spot
        we_need = 120 - ts
        if we_need <= 15 and os <= 85:   # cruise / ahead-protection
            return b, s
        bidorder = (pi - dl - 1) % 4
        if bidorder >= 2:                # late position — status quo (loose)
            return b, s
        fb = bidding.find_best_trump_suit(hand)
        suit, tc = fb['suit'], fb['trumpCount']
        return (15, suit) if tc >= self.min_trump else (b, s)


for _mt in (1, 2):
    REGISTRY[f"open:early{_mt}"] = EarlyOpen(_mt)


# UNCONDITIONAL OPEN (opt-in; champion default off). The likely ENDPOINT:
# loose-champion + seat1 (late, confirmed +1.05) + early (untested) would
# union to "in a clean open outside cruise, ALWAYS bid 15" — drop the
# trump/honor condition entirely. This is the expert's LITERAL stated
# heuristic ("almost always bid at least 15"). Test the endpoint directly
# so we ship the final rule ONCE instead of loose→seat1→union in 3 hops.
class AlwaysOpen(Policy):
    name = "open:always"

    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        b, s = bidding.decide_bid(hand, chb, pi, dl, ts, os, pb)
        if b != 0:
            return b, s
        if chb != 0 or pb > 0:
            return b, s
        if (120 - ts) <= 15 and os <= 85:   # cruise / ahead-protection
            return b, s
        return 15, bidding.find_best_trump_suit(hand)['suit']


REGISTRY["open:always"] = AlwaysOpen()


# EARLY-GAME OPEN (opt-in; champion default off). THE EXPERT'S ACTUAL
# STATED RULE (jack2112, messaged 2026-05-17): "early in the game he will
# always bid 15; he evaluates more in later game as the score develops."
# So aggression is conditioned on GAME PHASE BY SCORE — NOT hand-quality
# (loose), NOT bid-order (seat/early — that is late-in-the-AUCTION, a
# different 'late'), NOT all-game-unconditional (open:always, which the
# expert explicitly is NOT). Rule: in a clean open outside the cruise
# regime, if the game is EARLY (neither team's score has developed past
# the threshold) → open 15 unconditionally; once scores develop → fall
# straight back to champion (loose + cruise + desperation + spoiler =
# the 'evaluate as the score develops' logic). Graduated thresholds on
# max(team,opp) score — the rig picks where early-aggression stops
# paying:  open:eg40 (<40), open:eg60 (<60), open:eg80 (<80).
class EarlyGameOpen(Policy):
    def __init__(self, thresh):
        self.thresh = thresh
        self.name = f"open:eg{thresh}"

    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        b, s = bidding.decide_bid(hand, chb, pi, dl, ts, os, pb)
        if b != 0:
            return b, s                  # champion (incl. loose) bids
        if chb != 0 or pb > 0:
            return b, s                  # not a clean open spot
        if (120 - ts) <= 15 and os <= 85:   # cruise / ahead-protection
            return b, s
        if max(ts, os) >= self.thresh:   # scores developed → champion judges
            return b, s
        return 15, bidding.find_best_trump_suit(hand)['suit']  # early → always 15


for _t in (40, 60, 80):
    REGISTRY[f"open:eg{_t}"] = EarlyGameOpen(_t)


# DESPERATION-GUARDED OPEN (opt-in; champion default off). User insight
# (2026-05-17), verified in code: the -2.11pt comeback drag of
# open:always is NOT an inherent cost of aggression — it is a LEAK. When
# desperation is active (they_need<=15 & we_need>0 == opp>=105 & we
# behind), the desperation block OWNS that regime: with opp_has_dealer it
# returns 20-fight / pass; but in the not-opp_has_dealer weak-hand case
# it FALLS THROUGH to the (baked) loose-open, which bids 15 on junk and
# deepens the loss. Fix = let desperation own that regime: gate the open
# with `not desperation`. Champion is called with loose OFF, then the
# open is re-applied here WITH the desperation guard (and the existing
# cruise guard), so the leak is removed at the source.
#   open:ndloose  minimal: shipped loose condition + desperation guard
#                 (pure leak-fix of the SHIPPED rule, hand cond kept)
#   open:nd       maximal: UNCONDITIONAL clean-open + desperation guard
#                 (= open:always with the comeback leak removed)
class DespGuardedOpen(Policy):
    def __init__(self, unconditional):
        self.unconditional = unconditional
        self.name = "open:nd" if unconditional else "open:ndloose"

    def decide_bid(self, hand, chb, pi, dl, ts, os, pb):
        # champion WITHOUT baked loose — so desperation/standard decide
        # first; loose's in-desperation leak cannot fire at the source.
        b, s = bidding.decide_bid(hand, chb, pi, dl, ts, os, pb,
                                  enable_loose_open=False)
        if b != 0:
            return b, s                       # champion (incl. desp) bids
        if chb != 0 or pb > 0:
            return b, s                       # not a clean open spot
        we_need, they_need = 120 - ts, 120 - os
        if we_need <= 15 and os <= 85:        # cruise / ahead-protection
            return b, s
        if they_need <= 15 and we_need > 0:   # DESPERATION owns this regime
            return b, s                       # → defer (no junk 15 leak)
        fb = bidding.find_best_trump_suit(hand)
        suit, tc = fb['suit'], fb['trumpCount']
        if self.unconditional:
            return 15, suit
        hasAH = bidding.has_ace_hearts(hand)
        hasAT = bidding.has_ace_trump(hand, suit)
        return (15, suit) if (tc >= 3 or hasAH or hasAT) else (b, s)


REGISTRY["open:ndloose"] = DespGuardedOpen(False)
REGISTRY["open:nd"]      = DespGuardedOpen(True)
