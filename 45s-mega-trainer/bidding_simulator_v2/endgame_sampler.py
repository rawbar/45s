"""
endgame_sampler.py — determinization ("perfect-information Monte Carlo")
endgame play for the 45s rig (partner mode).

SamplingPolicy behaves exactly like the champion Policy until trick
`start_trick`. From then on, at each decision it:
  1. samples N plausible deals of the unseen cards to the other 3 seats,
     consistent with hand sizes, shown voids, and the lose-floor deduction,
     with trump placed in hands before offsuit (discards are ~all offsuit);
  2. for every legal card, plays out the rest of the round with the champion
     AI on all four seats (paired: same sampled worlds for every candidate);
  3. picks the card with the best mean (my team round net - opp team round net),
     but only deviates from the champion's own choice when it wins by `eps`.

Only information a real seat has is used (own hand, played cards, shown voids,
hand SIZES, draw counts are NOT used in this v1).
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import List, Tuple
from game_engine import (Card, Suit, GameState, Deck, get_trump_rank, is_trump,
                         get_playable_cards, evaluate_trick)
from bidding_simulator_v2.policy import Policy
from bidding_simulator_v2.improved_ai import ImprovedAI, cid
from bidding_simulator_v2.round_runner import _update_known_voids


def _allowed(card: Card, kv: dict, trump: Suit) -> bool:
    if get_trump_rank(card, trump) >= 0:
        if kv.get('trump') is True:
            return False
        if get_trump_rank(card, trump) < kv.get('lose_floor', 0):
            return False
        return True
    return kv.get(card.suit.value) is not True


def sample_world(rng, pool: List[Card], sizes: dict, known_voids, trump: Suit, quota=None):
    """sizes: {seat: n_cards}. Returns {seat: [cards]} or None."""
    for _attempt in range(30):
        cards = pool[:]
        rng.shuffle(cards)
        trumps = [c for c in cards if get_trump_rank(c, trump) >= 0]
        offs = [c for c in cards if get_trump_rank(c, trump) < 0]
        hands = {s: [] for s in sizes}
        ok = True
        tcount = {s_: 0 for s_ in sizes}
        for gi, group in enumerate((trumps, offs)):
            for c in group:
                seats = [s for s in sizes if len(hands[s]) < sizes[s]
                         and _allowed(c, known_voids[s], trump)
                         and (quota is None or (gi == 0 and tcount[s] < quota[s])
                              or (quota is not None and gi == 1 and len(hands[s]) - tcount[s] < sizes[s] - quota[s]))]
                if not seats:
                    continue            # goes to the discard pile
                # offsuit: only fill up to capacity; weight toward emptier seats
                ch = rng.choice(seats)
                hands[ch].append(c)
                if gi == 0:
                    tcount[ch] += 1
        if all(len(hands[s]) == sizes[s] for s in sizes):
            return hands
    return None


# Start-trump (post-draw) distribution by draw count (measured, calib.py).
_PRIOR = {False: {0: {5: 1.0}, 1: {4: .83, 5: .17}, 2: {3: .63, 4: .33, 5: .04},
                  3: {2: .47, 3: .41, 4: .11, 5: .01},
                  4: {0: .10, 1: .36, 2: .37, 3: .15, 4: .02}},
          True: {0: {4: .47, 5: .53}, 1: {4: .78, 5: .22}, 2: {3: .57, 4: .38, 5: .06},
                 3: {2: .39, 3: .44, 4: .15, 5: .01}, 4: {0: .10, 1: .36, 2: .37, 3: .15, 4: .02}}}


class SamplingPolicy(Policy):
    def __init__(self, n_worlds=16, start_trick=3, eps=0.0, seed=1, cheat=False, use_prior=True, oracle_counts=False, prior_quota=True, consistency=False, max_tries=40, **kw):
        super().__init__(**kw)
        self.n_worlds = n_worlds
        self.start_trick = start_trick
        self.eps = eps
        self.cheat = cheat
        self.use_prior = use_prior
        self.oracle_counts = oracle_counts
        self.prior_quota = prior_quota
        self.consistency = consistency
        self.max_tries = max_tries
        self._rng = random.Random(seed)
        self.stats = {'decisions': 0, 'deviations': 0}
        self._ai = None

    def _rollout_ais(self):
        if self._ai is None:
            flags = self._effective_ai_flags()
            self._ai = [ImprovedAI(s, flags) for s in range(4)]
        return self._ai

    def _sample_quota(self, sizes, kvs, state, played_tr, U):
        rng = self._rng
        for _ in range(300):
            q = {}
            tot = 0
            ok = True
            for o in sizes:
                dist = _PRIOR[o == state.bid_winner][min(4, max(0, state.cards_drawn[o]))]
                r = rng.random(); acc = 0.0; start = None
                for k, v in dist.items():
                    acc += v
                    if r <= acc:
                        start = k; break
                if start is None:
                    start = list(dist)[-1]
                rem = start - played_tr[o]
                if rem < 0 or rem > sizes[o] or (kvs[o].get('trump') is True and rem != 0):
                    ok = False; break
                q[o] = rem; tot += rem
            if ok and tot == U:
                return q
        return None

    def _consistent(self, seat, state, play_history, world) -> bool:
        """Would the champion AI, holding the sampled starting hands, have made
        every play the other seats actually made?"""
        ais = self._rollout_ais()
        trump = state.trump_suit
        bidder = state.bid_winner
        played_by = {o: [c for (p, c) in play_history if p == o] for o in range(4)}
        hands = [None] * 4
        for o in range(4):
            cur = state.hands[o] if o == seat else world[o]
            hands[o] = [c for c in cur] + played_by[o]
        trick_leader = bidder
        tricks_won = [0, 0]; player_tricks = [0, 0, 0, 0]
        cards_played = []; hist = []
        known_voids = [{}, {}, {}, {}]; known_oot = [False] * 4
        hi_rank = -1; hi_player = -1; bidder_lost = False
        n_full = len(play_history) // 4
        for t in range(n_full + (1 if len(play_history) % 4 else 0)):
            trick = []
            cur = trick_leader
            n_in = min(4, len(play_history) - 4 * t)
            for k in range(n_in):
                actual = play_history[4 * t + k]
                assert actual[0] == cur
                if cur != seat:
                    st = GameState(
                        hands=[[c for c in h] for h in hands], trump_suit=trump,
                        bid_winner=bidder, high_bid=state.high_bid, dealer=0,
                        current_trick=trick[:], trick_leader=trick_leader,
                        tricks_won=tricks_won[:], trick_num=t + 1,
                        cards_drawn=list(state.cards_drawn),
                        cards_played=cards_played[:],
                        known_out_of_trump=known_oot[:], bidder_lost_trick=bidder_lost,
                        high_trump_rank=hi_rank, high_trump_winner=hi_player,
                        known_voids=[dict(v) for v in known_voids],
                        team_scores=(state.team_scores[:] if state.team_scores else None),
                        player_tricks=player_tricks[:], high_trump_player=hi_player,
                        pre_round_scores=state.pre_round_scores)
                    led = trick[0][1] if trick else None
                    legal = get_playable_cards(hands[cur], trump, led)
                    if actual[1] not in legal:
                        return False
                    if ais[cur].choose_card(st, hist[:]) != actual[1]:
                        return False
                card = actual[1]
                hands[cur].remove(card)
                trick.append((cur, card)); hist.append((cur, card)); cards_played.append(card)
                tr = get_trump_rank(card, trump)
                if tr > hi_rank:
                    hi_rank = tr; hi_player = cur
                cur = (cur + 1) % 4
            if n_in < 4:
                break
            all_ids = {cid(c) for c in cards_played}
            _update_known_voids(trick, trick_leader, trump, all_ids, known_voids, known_oot)
            winner = evaluate_trick(trick, trump, trick_leader)
            tricks_won[winner % 2] += 1; player_tricks[winner] += 1
            if winner % 2 != bidder % 2:
                bidder_lost = True
            trick_leader = winner
        return True

    # ------------------------------------------------------------------
    def choose_card(self, seat, state, play_history):
        base = super().choose_card(seat, state, play_history)
        self._cur_history = list(play_history)
        if state.trick_num < self.start_trick:
            return base
        trump = state.trump_suit
        trick = state.current_trick
        led = trick[0][1] if trick else None
        hand = state.hands[seat]
        legal = get_playable_cards(hand, trump, led)
        if len(legal) <= 1:
            return base
        self.stats['decisions'] += 1

        played_ids = {cid(c) for c in state.cards_played}
        mine_ids = {cid(c) for c in hand}
        pool = [c for c in Deck().cards
                if cid(c) not in played_ids and cid(c) not in mine_ids]
        sizes = {o: len(state.hands[o]) for o in range(4) if o != seat}
        kvs = state.known_voids or [{}, {}, {}, {}]

        totals = {id(c): 0.0 for c in legal}
        n_ok = 0
        wsum = 0.0
        n_unseen_trump = sum(1 for c in pool if get_trump_rank(c, trump) >= 0)
        played_tr = {o: sum(1 for (p, c) in play_history if p == o
                            and get_trump_rank(c, trump) >= 0) for o in range(4)}
        for _ in range(self.n_worlds):
            quota = None
            if self.oracle_counts:
                quota = {o: sum(1 for c in state.hands[o] if get_trump_rank(c, trump) >= 0) for o in sizes}
            elif self.prior_quota and not self.cheat:
                quota = self._sample_quota(sizes, kvs, state, played_tr, n_unseen_trump)
            if self.cheat:
                w = {o: [c for c in state.hands[o]] for o in sizes}
            elif self.consistency:
                w = None
                for _t in range(self.max_tries):
                    if self.prior_quota:
                        quota = self._sample_quota(sizes, kvs, state, played_tr, n_unseen_trump)
                    cand = sample_world(self._rng, pool, sizes, kvs, trump, quota)
                    self.stats['cand'] = self.stats.get('cand', 0) + 1
                    if cand is not None and self._consistent(seat, state, play_history, cand):
                        w = cand
                        self.stats['acc'] = self.stats.get('acc', 0) + 1
                        break
            else:
                w = sample_world(self._rng, pool, sizes, kvs, trump, quota)
            if w is None:
                continue
            wt = 1.0
            wsum += wt
            n_ok += 1
            hands = [None] * 4
            hands[seat] = [c for c in hand]
            for o in sizes:
                hands[o] = w[o]
            for c in legal:
                totals[id(c)] += wt * self._rollout(seat, state, hands, c)
        if n_ok == 0:
            return base
        best = max(legal, key=lambda c: totals[id(c)])
        if base in legal and totals[id(best)] - totals[id(base)] <= self.eps * wsum:
            return base
        if best is not base:
            self.stats['deviations'] += 1
        return best

    # ------------------------------------------------------------------
    def _rollout(self, seat, state, hands0, first_card) -> float:
        """Play out the round after `seat` plays `first_card`; return
        (my team net) - (opp team net)."""
        ais = self._rollout_ais()
        trump = state.trump_suit
        bidder = state.bid_winner
        bid = state.high_bid
        hands = [[c for c in h] for h in hands0]
        trick = list(state.current_trick)
        trick_leader = state.trick_leader
        tricks_won = list(state.tricks_won)
        player_tricks = list(state.player_tricks) if state.player_tricks else [0, 0, 0, 0]
        cards_played = list(state.cards_played)
        history = []  # (seat, card) across the round; reconstruct from state
        # rebuild play_history from the caller's cards isn't available here;
        # the champion AI re-derives it from `play_history` -> we keep ours:
        history = list(self._cur_history)
        known_voids = [dict(v) for v in (state.known_voids or [{}, {}, {}, {}])]
        known_oot = list(state.known_out_of_trump)
        hi_rank = state.high_trump_rank
        hi_player = state.high_trump_player
        bidder_lost = state.bidder_lost_trick
        trick_num = state.trick_num

        cur = seat
        pending_first = first_card
        while True:
            # finish this trick
            while len(trick) < 4:
                if pending_first is not None and cur == seat:
                    card = pending_first
                    pending_first = None
                else:
                    st = GameState(
                        hands=[[c for c in h] for h in hands], trump_suit=trump,
                        bid_winner=bidder, high_bid=bid, dealer=0,
                        current_trick=trick[:], trick_leader=trick_leader,
                        tricks_won=tricks_won[:], trick_num=trick_num,
                        cards_drawn=list(state.cards_drawn),
                        cards_played=cards_played[:],
                        known_out_of_trump=known_oot[:],
                        bidder_lost_trick=bidder_lost,
                        high_trump_rank=hi_rank, high_trump_winner=hi_player,
                        known_voids=[dict(v) for v in known_voids],
                        team_scores=(state.team_scores[:] if state.team_scores else None),
                        player_tricks=player_tricks[:], high_trump_player=hi_player,
                        pre_round_scores=state.pre_round_scores)
                    card = ais[cur].choose_card(st, history[:])
                    led = trick[0][1] if trick else None
                    legal = get_playable_cards(hands[cur], trump, led)
                    if card not in legal:
                        card = legal[0]
                hands[cur].remove(card)
                trick.append((cur, card))
                history.append((cur, card))
                cards_played.append(card)
                tr = get_trump_rank(card, trump)
                if tr > hi_rank:
                    hi_rank = tr
                    hi_player = cur
                cur = (cur + 1) % 4
            all_ids = {cid(c) for c in cards_played}
            _update_known_voids(trick, trick_leader, trump, all_ids,
                                known_voids, known_oot)
            winner = evaluate_trick(trick, trump, trick_leader)
            tricks_won[winner % 2] += 1
            player_tricks[winner] += 1
            if winner % 2 != bidder % 2:
                bidder_lost = True
            trick_leader = winner
            cur = winner
            trick = []
            trick_num += 1
            if trick_num > 5:
                break

        pts = [tricks_won[0] * 5, tricks_won[1] * 5]
        if hi_player >= 0:
            pts[hi_player % 2] += 5
        bt = bidder % 2
        out = [0, 0]
        out[bt] = pts[bt] if pts[bt] >= bid else -bid
        out[1 - bt] = pts[1 - bt]
        me = seat % 2
        return out[me] - out[1 - me]
