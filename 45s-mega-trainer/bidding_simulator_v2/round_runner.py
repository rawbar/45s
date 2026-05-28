"""
round_runner.py — Simulate a single round with a forced bidder.

play_round() deals the discard/draw phase and plays all 5 tricks using
ImprovedAI for all four seats. Returns (made_bid, tricks_won, points_scored).

Player 0 is always the forced bidder. Trump suit and bid amount are passed in.

knownVoids / knownOutOfTrump are tracked exactly like index.html (renege
detection on trump leads, suit-void detection on offsuit leads) so the
AI's void-dependent exceptions fire the same way they do in the game.
The 5-card-draw house rule is OFF here (default game = what decideBid governs).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import List, Tuple
from game_engine import (
    Card, Suit, GameState,
    get_trump_rank, is_trump, get_playable_cards, evaluate_trick,
)
from bidding_simulator_v2.improved_ai import ImprovedAI, cid


def _update_known_voids(trick: List[Tuple[int, Card]],
                        trick_leader: int,
                        trump: Suit,
                        all_played_ids: set,
                        known_voids: List[dict],
                        known_oot: List[bool]) -> None:
    """Port of the index.html post-trick knownVoids/knownOutOfTrump update."""
    led_card = trick[0][1]
    tv = trump.value
    led_is_trump = get_trump_rank(led_card, trump) >= 0

    if led_is_trump:
        led_rank = get_trump_rank(led_card, trump)
        for (p, card) in trick:
            if get_trump_rank(card, trump) >= 0:
                # j_trump_dump_void (sound deduction for THIS engine): the AI
                # follows a trump lead with its LOWEST trump (it never
                # speculatively burns a high trump it cannot win with, and it
                # does not do the human "shed the J to promote A♥" play). So
                # a FOLLOWER who plays the J of trump (rank 101) onto the 5
                # of trump (rank 102, the only card that outranks it → the
                # trick is unwinnable) had J as its ONLY trump → fully
                # trump-void thereafter. (user-confirmed, v2.31.45 K♦ ruff.)
                if (p != trick_leader
                        and get_trump_rank(card, trump) == 101
                        and led_rank > 101):
                    known_voids[p]['trump'] = True
                    known_voids[p].pop('possibleTrump', None)
                    known_voids[p].pop('noLowTrump', None)
                    known_oot[p] = True
                # follow_trump_floor (sound deduction layer, always-on data):
                # a follower forced to follow trump plays its LOWEST trump.
                # So all their REMAINING trump must rank strictly above the
                # card they just played. Track the floor (min rank any
                # remaining trump could be) so the strategic layer can see
                # whether a not-yet-played opponent might over-trump us.
                # Safe vs this engine's AI; would be unsound vs a human who
                # sheds intermediate-rank trump to feint — that's why the
                # decision layer gates its USE of this floor on AI opponents.
                elif p != trick_leader and get_trump_rank(card, trump) >= 0:
                    played_rank = get_trump_rank(card, trump)
                    floor = played_rank + 1
                    existing = known_voids[p].get('min_trump_rank', 0)
                    if floor > existing:
                        known_voids[p]['min_trump_rank'] = floor
                continue  # played trump, no further info
            possible = []
            if f"5{tv}" not in all_played_ids and led_rank < 102:
                possible.append(f"5{tv}")
            if f"J{tv}" not in all_played_ids and led_rank < 101:
                possible.append(f"J{tv}")
            if "A♥" not in all_played_ids and led_rank < 100:
                possible.append("A♥")
            if not possible:
                known_voids[p]['trump'] = True
                known_oot[p] = True
            else:
                known_voids[p]['trump'] = 'reneging'
                known_voids[p]['possibleTrump'] = possible
                known_voids[p]['noLowTrump'] = True
                known_oot[p] = True
    else:
        led_suit = led_card.suit
        for (p, card) in trick:
            if p == trick_leader:
                continue
            played_is_trump = get_trump_rank(card, trump) >= 0
            followed = (not played_is_trump) and card.suit == led_suit
            if played_is_trump:
                continue  # trump on offsuit lead → can't infer led-suit void
            if not followed:
                known_voids[p][led_suit.value] = True
                known_voids[p]['trump'] = True
                known_oot[p] = True


def play_round(
    bid:            int,
    trump_suit:     Suit,
    hands:          List[List[Card]],
    kitty:          List[Card],
    remaining_deck: List[Card],
    ai_players:     List[ImprovedAI],
) -> Tuple[bool, int, int]:
    BIDDER = 0
    hands = [h[:] for h in hands]

    # ── 1. Bidder picks up kitty ─────────────────────────────────────────────
    hands[BIDDER].extend(kitty)

    # ── 2. Discard + draw (5-card-draw OFF: default game) ────────────────────
    deck_for_draw = remaining_deck[:]
    cards_drawn = [0, 0, 0, 0]
    for i in range(4):
        discards = ai_players[i].choose_discards(
            hands[i], trump_suit, i == BIDDER, bid, False
        )
        for card in discards:
            if card in hands[i]:
                hands[i].remove(card)
        num_draw = max(0, 5 - len(hands[i]))
        cards_drawn[i] = num_draw
        for _ in range(num_draw):
            if deck_for_draw:
                hands[i].append(deck_for_draw.pop())

    # ── 3. Play 5 tricks ─────────────────────────────────────────────────────
    tricks_won = [0, 0]
    player_tricks = [0, 0, 0, 0]
    trick_leader = BIDDER
    cards_played_all: List[Card] = []
    play_history: List[Tuple[int, Card]] = []
    high_trump_rank = -1
    high_trump_winner = -1
    known_out_of_trump = [False, False, False, False]
    known_voids: List[dict] = [{}, {}, {}, {}]
    bidder_lost_trick = False

    for trick_num in range(1, 6):
        trick: List[Tuple[int, Card]] = []
        current = trick_leader

        for _ in range(4):
            state = GameState(
                hands              = [h[:] for h in hands],
                trump_suit         = trump_suit,
                bid_winner         = BIDDER,
                high_bid           = bid,
                dealer             = 0,
                current_trick      = trick[:],
                trick_leader       = trick_leader,
                tricks_won         = tricks_won[:],
                trick_num          = trick_num,
                cards_drawn        = cards_drawn[:],
                cards_played       = cards_played_all[:],
                known_out_of_trump = known_out_of_trump[:],
                bidder_lost_trick  = bidder_lost_trick,
                high_trump_rank    = high_trump_rank,
                high_trump_winner  = high_trump_winner,
                known_voids        = [dict(v) for v in known_voids],
                player_tricks      = player_tricks[:],
                high_trump_player  = high_trump_winner,
                pre_round_scores   = None,   # round-only harness; no game ctx
            )

            card = ai_players[current].choose_card(state, play_history[:])

            led = trick[0][1] if trick else None
            legal = get_playable_cards(hands[current], trump_suit, led)
            if card not in legal:
                card = legal[0]

            hands[current].remove(card)
            trick.append((current, card))
            play_history.append((current, card))
            cards_played_all.append(card)

            tr = get_trump_rank(card, trump_suit)
            if tr > high_trump_rank:
                high_trump_rank = tr
                high_trump_winner = current

            current = (current + 1) % 4

        # Post-trick void/renege tracking (JS-faithful)
        all_played_ids = {cid(c) for c in cards_played_all}
        _update_known_voids(trick, trick_leader, trump_suit,
                            all_played_ids, known_voids, known_out_of_trump)

        winner = evaluate_trick(trick, trump_suit, trick_leader)
        tricks_won[winner % 2] += 1
        player_tricks[winner] += 1
        if winner % 2 != BIDDER % 2:
            bidder_lost_trick = True
        trick_leader = winner

    # ── 4. Score ─────────────────────────────────────────────────────────────
    bidder_team = BIDDER % 2
    team_tricks = tricks_won[bidder_team]
    points = team_tricks * 5
    if high_trump_winner >= 0 and high_trump_winner % 2 == bidder_team:
        points += 5
    made = points >= bid
    net = points if made else -bid
    return made, team_tricks, net
