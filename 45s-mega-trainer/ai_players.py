"""
AI Players for 45s
Different AI strategies for playing 45s
"""

from game_engine import *
from typing import List, Tuple, Optional
import random

class AIPlayer:
    """Base class for AI players"""
    
    def __init__(self, player_idx: int):
        self.player_idx = player_idx
    
    def choose_card(self, state: GameState) -> Card:
        """Choose which card to play"""
        raise NotImplementedError
    
    def decide_bid(self, hand: List[Card], current_high: int, dealer: int, 
                   team_score: int, opp_score: int) -> Tuple[int, Optional[Suit]]:
        """Decide what to bid. Returns (bid_amount, trump_suit) or (0, None) to pass"""
        raise NotImplementedError
    
    def choose_discards(self, hand: List[Card], trump_suit: Suit, 
                       is_bidder: bool, bid_amount: int) -> List[Card]:
        """Choose which cards to discard. Returns list of cards to discard."""
        raise NotImplementedError

def find_best_trump_suit(hand: List[Card]) -> Tuple[Suit, int, bool, bool]:
    """
    Find the best trump suit in a hand.
    Returns (suit, trump_count, has_5, has_J)
    """
    best_suit = None
    best_count = 0
    best_has_5 = False
    best_has_J = False
    
    for suit in Suit:
        trump_count = sum(1 for c in hand if is_trump(c, suit))
        has_5 = any(c.rank == '5' and c.suit == suit for c in hand)
        has_J = any(c.rank == 'J' and c.suit == suit for c in hand)
        
        # Prefer suits with 5 or J
        score = trump_count * 10
        if has_5:
            score += 20
        if has_J:
            score += 15
        
        if score > best_count * 10:
            best_suit = suit
            best_count = trump_count
            best_has_5 = has_5
            best_has_J = has_J
    
    return best_suit, best_count, best_has_5, best_has_J

class HeuristicAI(AIPlayer):
    """
    AI player using hand-coded heuristics.
    Based on the JavaScript implementation.
    """
    
    def decide_bid(self, hand: List[Card], current_high: int, dealer: int,
                   team_score: int, opp_score: int) -> Tuple[int, Optional[Suit]]:
        """Implement bidding strategy from simulations"""
        
        suit, trump_count, has_5, has_J = find_best_trump_suit(hand)
        has_AH = any(c.rank == 'A' and c.suit == Suit.HEARTS for c in hand)
        has_AT = any(c.rank == 'A' and c.suit == suit for c in hand)
        
        # Count high trumps (K, Q, A of trump, A♥)
        high_trumps = sum(1 for c in hand if is_trump(c, suit) and c.rank in ['K', 'Q', 'A'])
        if has_AH:
            high_trumps += 1
        
        # Game state analysis
        we_need = 120 - team_score
        they_need = 120 - opp_score
        desperation = they_need <= 20 and we_need > 15
        
        bid = 0
        
        # Guaranteed hands
        if has_5 and has_J and has_AH and trump_count >= 5:
            bid = 30
        elif has_5 and has_J and has_AH and trump_count >= 4:
            bid = 25
        elif has_5 and has_J and trump_count >= 4 and high_trumps >= 3:
            bid = 25
        
        # 20 bids
        elif has_5 and trump_count >= 3:
            bid = 20
        elif has_5 and trump_count >= 2 and high_trumps >= 2:
            bid = 20
        elif has_J and has_AH and trump_count >= 4:
            bid = 20
        
        # 15 bids
        elif has_5:
            bid = 15
        elif has_J and trump_count >= 3:
            bid = 15
        elif has_AH and trump_count >= 3:
            bid = 15
        elif trump_count >= 4 and high_trumps >= 2:
            bid = 15
        
        # Desperation bidding
        if desperation and bid < 20:
            if (has_5 and trump_count >= 2) or (has_J and trump_count >= 3):
                bid = max(bid, 20)
        
        # Dealer minimum bid
        if bid > current_high and self.player_idx == dealer and current_high > 0:
            bid = min(bid, current_high + 5)
        
        if bid <= current_high:
            if self.player_idx == dealer and current_high == 0:
                return (15, suit)
            return (0, None)
        
        return (bid, suit)
    
    def choose_discards(self, hand: List[Card], trump_suit: Suit,
                       is_bidder: bool, bid_amount: int) -> List[Card]:
        """Choose which cards to discard"""
        
        trumps = [c for c in hand if is_trump(c, trump_suit)]
        offsuits = [c for c in hand if not is_trump(c, trump_suit)]
        
        # Keep all trumps
        keep = trumps.copy()
        
        # For 25+ bids, only keep 1 strong offsuit if we have room
        if is_bidder and bid_amount >= 25:
            if len(trumps) >= 4 and offsuits:
                strong = [c for c in offsuits if c.rank in ['K', 'A']]
                if strong:
                    keep.append(strong[0])
        
        # For 15/20 bids, can keep some offsuit
        elif is_bidder and offsuits:
            # Keep best offsuit per suit
            by_suit = {}
            for c in offsuits:
                if c.suit not in by_suit:
                    by_suit[c.suit] = []
                by_suit[c.suit].append(c)
            
            best_per_suit = []
            for suit_cards in by_suit.values():
                suit_cards.sort(key=lambda c: get_offsuit_rank(c), reverse=True)
                best_per_suit.append(suit_cards[0])
            
            strong = [c for c in best_per_suit if c.rank in ['K', 'A']]
            if strong and len(trumps) >= 3:
                keep.append(strong[0])
        
        # If we have nothing, keep best card
        if not keep:
            keep = [max(hand, key=lambda c: get_trump_rank(c, trump_suit) 
                       if is_trump(c, trump_suit) else get_offsuit_rank(c))]
        
        return [c for c in hand if c not in keep]
    
    def choose_card(self, state: GameState) -> Card:
        """Choose card to play using heuristics"""
        
        hand = state.hands[self.player_idx]
        trump_suit = state.trump_suit
        
        # Get led card if any
        led_card = state.current_trick[0][1] if state.current_trick else None
        
        # Get playable cards
        playable = get_playable_cards(hand, trump_suit, led_card)
        
        if len(playable) == 1:
            return playable[0]
        
        # Team info
        my_team = state.get_team(self.player_idx)
        partner_idx = state.get_partner(self.player_idx)
        bidder_team = state.get_team(state.bid_winner)
        my_team_bid = (my_team == bidder_team)
        i_am_bidder = (self.player_idx == state.bid_winner)
        partner_is_bidder = (partner_idx == state.bid_winner)
        
        # Opponent weakness
        opp1_idx = (self.player_idx + 1) % 4
        opp2_idx = (self.player_idx + 3) % 4
        opp_weak = state.cards_drawn[opp1_idx] >= 4 and state.cards_drawn[opp2_idx] >= 4
        partner_weak = state.cards_drawn[partner_idx] >= 4
        
        # Leading
        if not led_card:
            trumps = [c for c in playable if is_trump(c, trump_suit)]
            non_trumps = [c for c in playable if not is_trump(c, trump_suit)]
            has_5 = any(c.rank == '5' and c.suit == trump_suit for c in trumps)
            
            # Bidder leading
            if i_am_bidder and trumps:
                # For 25 bids, lead strongest trump
                if state.high_bid >= 25 and not state.bidder_lost_trick:
                    return max(trumps, key=lambda c: get_trump_rank(c, trump_suit))
                
                # Lead the 5 aggressively
                if has_5:
                    return next(c for c in trumps if c.rank == '5' and c.suit == trump_suit)
                
                # Lead strongest trump
                return max(trumps, key=lambda c: get_trump_rank(c, trump_suit))
            
            # Teammate of bidder leading
            if my_team_bid and len(trumps) >= 2:
                if has_5 and opp_weak:
                    return next(c for c in trumps if c.rank == '5' and c.suit == trump_suit)
                return max(trumps, key=lambda c: get_trump_rank(c, trump_suit))
            
            # Partner is bidder - lead offsuit
            if partner_is_bidder and not partner_weak and non_trumps:
                return min(non_trumps, key=get_offsuit_rank)
            
            # Default - lead weakest card
            return min(playable, key=lambda c: get_trump_rank(c, trump_suit) 
                      if is_trump(c, trump_suit) else get_offsuit_rank(c) - 100)
        
        # Following
        led_suit = led_card.suit
        
        # Determine who's winning (if anyone has played yet)
        if len(state.current_trick) > 0:
            winner_idx = evaluate_trick(state.current_trick, trump_suit, state.trick_leader)
            # Safety check - winner_idx should be within bounds
            if winner_idx >= len(state.current_trick):
                # Fallback - assume led card is winning
                winner_idx = 0
            partner_winning = state.get_team((state.trick_leader + winner_idx) % 4) == my_team
            winner_card = state.current_trick[winner_idx][1]
        else:
            partner_winning = False
            winner_card = led_card
        
        # Partner winning - throw low
        if partner_winning:
            return min(playable, key=lambda c: get_trump_rank(c, trump_suit) + 200
                      if is_trump(c, trump_suit) else get_offsuit_rank(c))
        
        # Try to win
        led_suit_actual = led_card.suit if not is_trump(led_card, trump_suit) else trump_suit
        
        can_win = [c for c in playable if card_beats(c, winner_card, trump_suit, led_suit_actual)]
        if can_win:
            return min(can_win, key=lambda c: get_trump_rank(c, trump_suit)
                      if is_trump(c, trump_suit) else get_offsuit_rank(c))
        
        # Can't win - throw low
        non_trump = [c for c in playable if not is_trump(c, trump_suit)]
        if non_trump:
            return min(non_trump, key=get_offsuit_rank)
        
        return min(playable, key=lambda c: get_trump_rank(c, trump_suit))

class MonteCarloAI(AIPlayer):
    """
    AI player using Monte Carlo simulation.
    Evaluates each move by simulating games and picking the best outcome.
    """
    
    def __init__(self, player_idx: int, num_rollouts=100):
        super().__init__(player_idx)
        self.num_rollouts = num_rollouts
        self.heuristic = HeuristicAI(player_idx)  # Fallback for simple decisions
    
    def decide_bid(self, hand: List[Card], current_high: int, dealer: int,
                   team_score: int, opp_score: int) -> Tuple[int, Optional[Suit]]:
        """Use heuristic for bidding (already optimized)"""
        return self.heuristic.decide_bid(hand, current_high, dealer, team_score, opp_score)
    
    def choose_discards(self, hand: List[Card], trump_suit: Suit,
                       is_bidder: bool, bid_amount: int) -> List[Card]:
        """Use heuristic for discarding (simple decision)"""
        return self.heuristic.choose_discards(hand, trump_suit, is_bidder, bid_amount)
    
    def choose_card(self, state: GameState) -> Card:
        """Use Monte Carlo simulation to choose best card"""
        
        hand = state.hands[self.player_idx]
        led_card = state.current_trick[0][1] if state.current_trick else None
        playable = get_playable_cards(hand, state.trump_suit, led_card)
        
        # If only one choice, no need to simulate
        if len(playable) == 1:
            return playable[0]
        
        # If simple situation, use heuristic (faster)
        if len(playable) == 2 and not led_card:
            # Leading with 2 cards - heuristic is fine
            return self.heuristic.choose_card(state)
        
        # Run simulations for each playable card
        card_scores = {}
        
        for card in playable:
            # Simulate playing this card
            total_points = 0
            
            for _ in range(self.num_rollouts):
                points = self.simulate_game_from_card(state, card)
                total_points += points
            
            avg_points = total_points / self.num_rollouts
            card_scores[card] = avg_points
        
        # Pick card with best average outcome
        best_card = max(card_scores.items(), key=lambda x: x[1])[0]
        return best_card
    
    def simulate_game_from_card(self, state: GameState, card: Card) -> float:
        """
        Simulate rest of game after playing this card.
        Returns points scored by my team.
        """
        # Create a copy of game state
        sim_state = state.copy()
        
        # Sample opponent hands (they don't know what opponents have)
        sim_state.hands = self.sample_opponent_hands(state)
        
        # Play the chosen card
        sim_state.hands[self.player_idx].remove(card)
        sim_state.current_trick.append((self.player_idx, card))
        sim_state.cards_played.append(card)
        
        # Update high trump if this card is higher
        trump_rank = get_trump_rank(card, state.trump_suit)
        if trump_rank > sim_state.high_trump_rank:
            sim_state.high_trump_rank = trump_rank
            sim_state.high_trump_winner = self.player_idx
        
        # Simulate rest of trick
        current_player = (self.player_idx + 1) % 4
        led_card = sim_state.current_trick[0][1]
        
        while len(sim_state.current_trick) < 4:
            hand = sim_state.hands[current_player]
            playable = get_playable_cards(hand, sim_state.trump_suit, led_card)
            
            if not playable:
                break
            
            # Use heuristic for opponents (fast simulation)
            temp_state = sim_state.copy()
            temp_state.hands[current_player] = hand
            ai = HeuristicAI(current_player)
            chosen = ai.choose_card(temp_state)
            
            sim_state.hands[current_player].remove(chosen)
            sim_state.current_trick.append((current_player, chosen))
            sim_state.cards_played.append(chosen)
            
            # Update high trump
            trump_rank = get_trump_rank(chosen, sim_state.trump_suit)
            if trump_rank > sim_state.high_trump_rank:
                sim_state.high_trump_rank = trump_rank
                sim_state.high_trump_winner = current_player
            
            current_player = (current_player + 1) % 4
        
        # Evaluate trick winner
        trick_winner = evaluate_trick(sim_state.current_trick, sim_state.trump_suit, sim_state.trick_leader)
        
        # Simulate remaining tricks using heuristic AI
        tricks_won = [0, 0]
        tricks_won[trick_winner % 2] += 1
        
        leader = trick_winner
        for remaining_trick in range(sim_state.trick_num + 1, 6):
            # Play out trick with heuristic
            trick_winner = self.simulate_trick_heuristic(sim_state.hands, leader, sim_state)
            tricks_won[trick_winner % 2] += 1
            leader = trick_winner
        
        # Calculate points
        my_team = self.player_idx % 2
        bidder_team = sim_state.bid_winner % 2
        high_trick_team = sim_state.high_trump_winner % 2
        
        score_change = calculate_points(tricks_won, bidder_team, sim_state.high_bid, sim_state.high_trump_winner)
        
        return score_change[my_team]
    
    def simulate_trick_heuristic(self, hands: List[List[Card]], leader: int, state: GameState) -> int:
        """Simulate one trick using heuristic AI for all players"""
        trick = []
        current_player = leader
        
        for _ in range(4):
            if not hands[current_player]:
                break
            
            led_card = trick[0][1] if trick else None
            playable = get_playable_cards(hands[current_player], state.trump_suit, led_card)
            
            if not playable:
                break
            
            # Use heuristic
            temp_state = state.copy()
            temp_state.current_trick = [(p, c) for p, c in trick]
            temp_state.trick_leader = leader
            temp_state.hands[current_player] = hands[current_player]
            
            ai = HeuristicAI(current_player)
            chosen = ai.choose_card(temp_state)
            
            hands[current_player].remove(chosen)
            trick.append((current_player, chosen))
            
            # Update high trump
            trump_rank = get_trump_rank(chosen, state.trump_suit)
            if trump_rank > state.high_trump_rank:
                state.high_trump_rank = trump_rank
                state.high_trump_winner = current_player
            
            current_player = (current_player + 1) % 4
        
        if not trick:
            return leader
        
        return evaluate_trick(trick, state.trump_suit, leader)
    
    def sample_opponent_hands(self, state: GameState) -> List[List[Card]]:
        """
        Sample plausible opponent hands based on what we know.
        Returns complete hands for all 4 players.
        """
        my_hand = state.hands[self.player_idx]
        
        # Build list of unknown cards
        deck = Deck().cards
        known_cards = set(my_hand + state.cards_played)
        unknown_cards = [c for c in deck if c not in known_cards]
        
        # Shuffle unknown cards
        random.shuffle(unknown_cards)
        
        # Deal to other players
        sampled_hands = [[] for _ in range(4)]
        sampled_hands[self.player_idx] = my_hand.copy()
        
        idx = 0
        for p in range(4):
            if p == self.player_idx:
                continue
            
            # Each player should have same hand size as me
            hand_size = len(my_hand)
            for _ in range(hand_size):
                if idx < len(unknown_cards):
                    sampled_hands[p].append(unknown_cards[idx])
                    idx += 1
        
        return sampled_hands

if __name__ == "__main__":
    # Test AI
    deck = Deck().shuffle()
    hand = deck.deal(5)
    
    ai = HeuristicAI(0)
    bid, suit = ai.decide_bid(hand, 0, 3, 0, 0)
    
    print("Hand:", hand)
    print(f"AI bid: {bid} with trump {suit.value if suit else 'N/A'}")
    
    # Test MC AI
    mc = MonteCarloAI(0, num_rollouts=10)
    print(f"MC AI created with {mc.num_rollouts} rollouts")
