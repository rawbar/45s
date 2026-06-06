"""
policy.py — AI policy seam for the head-to-head evaluator.

A Policy bundles the three decisions an AI makes: bid, discard, card-play.
Policies are assigned PER TEAM (seats 0,2 vs 1,3) — never split within a team,
because signaling is a shared convention between partners.

ChampionPolicy = the current shipped AI (faithful v2.31.23 port).
Challenger variants subclass and override exactly one method, so a measured
win-rate delta is attributable to that one change.
"""

from typing import List, Tuple, Optional
from game_engine import Card, Suit, GameState
from bidding_simulator_v2.improved_ai import ImprovedAI
from bidding_simulator_v2 import bidding


class Policy:
    """Base = champion behaviour. Override one method to make a challenger.
    `ai_flags` (dict) ablates one card-play rule; unset keys stay enabled so
    the base Policy is bit-identical to the validated faithful port.

    `cutthroat` (bool, default False) switches the bidding side to
    every-man-for-himself mode (no partner concept). Card-play is NOT yet
    gated for cutthroat — that ships in chunk B. The flag is threaded into
    ai_flags so improved_ai.py can read it later without further plumbing.

    `cutthroat_surgical_tight_20` (bool, default True) — SHIPPED default-on
    for cutthroat policies. Demotes 6 EV-negative 20-bid patterns identified
    by cutthroat_pattern_makerate.py @ 2000 deals (make-rate ≤ 36%). See
    bidding.decide_bid for the pattern list and the symmetric set-rate test
    results in the registry commit message. Flag is a no-op in partner mode
    (forced off inside bidding.decide_bid's `else` branch). Champion-cutthroat
    self-test stays at 25.00% exact (4 seats run same policy, symmetric).
    Partner-mode regression stays at 50.00% exact."""
    name = "champion"
    ai_flags: dict = None
    cutthroat: bool = False
    cutthroat_surgical_tight_20: bool = True
    cutthroat_allow_5ahat_25: bool = True
    cutthroat_force_upbid15: bool = False
    cutthroat_force_upbid15_with_5: bool = False
    cutthroat_desp_tight_20: bool = False
    cutthroat_force_loose_open: bool = False
    cutthroat_opp_has_dealer_always: bool = True
    cutthroat_desp_rule4_tight: bool = False
    cutthroat_bag_threatening_dealer: bool = True
    # CT-SETLOCKED-SAVE-LAST-TRUMP (challenger; default False until rig
    # validates). Threaded into ai_flags so improved_ai.py reads via Fon().
    ct_setlocked_save_last_trump: bool = False
    # CT-B3-TAKE-OVER-FELLOW (challenger that REPLAYS the OLD pre-v2.31.104
    # JS behavior — B+3 takes the trick on bidder offsuit lead even when a
    # fellow defender has already won the trick). Champion default False
    # (matches v2.31.104+ JS: B+3 stands down when a fellow defender
    # already has it). When True the rule fires unconditionally per the
    # original v2.31.100 behavior. Used to MEASURE the cost of the OLD
    # over-trumping behavior — significant rig regression for True means
    # the new gate is an improvement; neutral means trust-fix territory.
    cutthroat_b3_take_over_fellow: bool = False

    def __init__(self, cutthroat: bool = False, ai_flags: dict = None,
                 name: str = None,
                 cutthroat_surgical_tight_20: bool = True,
                 cutthroat_allow_5ahat_25: bool = True,
                 cutthroat_force_upbid15: bool = False,
                 cutthroat_force_upbid15_with_5: bool = False,
                 cutthroat_desp_tight_20: bool = False,
                 cutthroat_force_loose_open: bool = False,
                 cutthroat_opp_has_dealer_always: bool = True,
                 cutthroat_desp_rule4_tight: bool = False,
                 cutthroat_bag_threatening_dealer: bool = True,
                 ct_setlocked_save_last_trump: bool = False,
                 cutthroat_b3_take_over_fellow: bool = False):
        # All args default-None/False so existing zero-arg `Policy()` callers
        # stay bit-identical. Subclasses that don't call super still work
        # because the class attrs above provide the defaults.
        # cutthroat_surgical_tight_20 defaults True to ship the surgical
        # tighten-20 rule by default; it is forced OFF in partner mode
        # inside bidding.decide_bid so partner-mode bit-identity is preserved.
        # cutthroat_allow_5ahat_25 defaults True to ship the 5+AH+AT-no-J →25
        # overbid rule (robr-derived divergence; symmetric Δ=-1.49pt z=-3.67
        # primary / -1.03pt z=-2.53 held-out; 1-vs-3 +1.54pt z=+3.18 /
        # +1.67pt z=+3.46 held-out — replicated). Forced OFF in partner mode.
        self.cutthroat = cutthroat
        self.cutthroat_surgical_tight_20 = cutthroat_surgical_tight_20
        self.cutthroat_allow_5ahat_25 = cutthroat_allow_5ahat_25
        self.cutthroat_force_upbid15 = cutthroat_force_upbid15
        self.cutthroat_force_upbid15_with_5 = cutthroat_force_upbid15_with_5
        self.cutthroat_desp_tight_20 = cutthroat_desp_tight_20
        self.cutthroat_force_loose_open = cutthroat_force_loose_open
        self.cutthroat_opp_has_dealer_always = cutthroat_opp_has_dealer_always
        self.cutthroat_desp_rule4_tight = cutthroat_desp_rule4_tight
        self.cutthroat_bag_threatening_dealer = cutthroat_bag_threatening_dealer
        self.ct_setlocked_save_last_trump = ct_setlocked_save_last_trump
        self.cutthroat_b3_take_over_fellow = cutthroat_b3_take_over_fellow
        if ai_flags is not None:
            self.ai_flags = dict(ai_flags)
        if name is not None:
            self.name = name

    def _effective_ai_flags(self) -> dict:
        """ai_flags merged with the cutthroat bit so improved_ai.py can
        branch on `flags.get('cutthroat')` once chunk B wires that up."""
        f = dict(self.ai_flags) if self.ai_flags else {}
        if self.cutthroat:
            f['cutthroat'] = True
        # CT-SETLOCKED-SAVE-LAST-TRUMP: thread Policy attr into ai_flags so
        # improved_ai.py reads via Fon('ct_setlocked_save_last_trump'). Only
        # set when True so champion bit-identity is preserved (Fon default
        # False).
        if self.ct_setlocked_save_last_trump:
            f['ct_setlocked_save_last_trump'] = True
        # CT-B3-TAKE-OVER-FELLOW: thread Policy attr into ai_flags so
        # improved_ai.py reads via Fon('cutthroat_b3_take_over_fellow').
        # Only set when True so champion (v2.31.104+ JS default) is bit-
        # identical to the no-flag baseline.
        if self.cutthroat_b3_take_over_fellow:
            f['cutthroat_b3_take_over_fellow'] = True
        return f or None

    def decide_bid(self, hand: List[Card], current_high_bid: int, player_index: int,
                    dealer: int, team_scores: int, opp_scores: int,
                    partner_bid: int, dealer_score: int = -1) -> Tuple[int, Optional[Suit]]:
        return bidding.decide_bid(hand, current_high_bid, player_index, dealer,
                                  team_scores, opp_scores, partner_bid,
                                  cutthroat=self.cutthroat,
                                  cutthroat_surgical_tight_20=
                                      self.cutthroat_surgical_tight_20,
                                  cutthroat_allow_5ahat_25=
                                      self.cutthroat_allow_5ahat_25,
                                  cutthroat_force_upbid15=
                                      self.cutthroat_force_upbid15,
                                  cutthroat_force_upbid15_with_5=
                                      self.cutthroat_force_upbid15_with_5,
                                  cutthroat_desp_tight_20=
                                      self.cutthroat_desp_tight_20,
                                  cutthroat_force_loose_open=
                                      self.cutthroat_force_loose_open,
                                  cutthroat_opp_has_dealer_always=
                                      self.cutthroat_opp_has_dealer_always,
                                  cutthroat_desp_rule4_tight=
                                      self.cutthroat_desp_rule4_tight,
                                  cutthroat_bag_threatening_dealer=
                                      self.cutthroat_bag_threatening_dealer,
                                  dealer_score=dealer_score)

    def choose_discards(self, hand: List[Card], trump: Suit, is_bid_winner: bool,
                        bid_amount: int) -> List[Card]:
        return ImprovedAI(0).choose_discards(hand, trump, is_bid_winner,
                                             bid_amount, False)

    def choose_card(self, seat: int, state: GameState,
                    play_history: List[Tuple[int, Card]]) -> Card:
        return ImprovedAI(seat, self._effective_ai_flags()).choose_card(state, play_history)


CHAMPION = Policy()
