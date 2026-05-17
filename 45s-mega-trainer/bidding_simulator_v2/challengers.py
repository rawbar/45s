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
}
for _r in CARD_RULES:
    REGISTRY[f"off:{_r}"] = _card_off(_r)


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


# ENDGAME POINT-BUDGET DENY (opt-in; champion default off). Bidder-side:
# when opponent is at game point (oppNeed<=10 to 120) a normal made bid
# still loses (defenders score), so play every trick must-win / never
# concede. ONLY meaningful in a GAME-context harness (needs team_scores);
# round-context evaluator passes team_scores=None → this is a no-op there.
_ed = Policy()
_ed.name = "endgame_deny"
_ed.ai_flags = {'endgame_deny': True}
REGISTRY["endgame_deny"] = _ed


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
