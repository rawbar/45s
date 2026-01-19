"""
Game Simulator
Plays complete 45s games with AI players
"""

from game_engine import *
from ai_players import AIPlayer, HeuristicAI, MonteCarloAI
from typing import List, Tuple
import random

class Game45s:
    """Simulates a complete game of 45s"""
    
    def __init__(self, players: List[AIPlayer], verbose=False):
        """
        Initialize game with 4 AI players.
        Players[0] and Players[2] are teammates (Team 0)
        Players[1] and Players[3] are teammates (Team 1)
        """
        assert len(players) == 4, "Need exactly 4 players"
        self.players = players
        self.verbose = verbose
        self.reset()
    
    def reset(self):
        """Reset for a new game"""
        self.scores = [0, 0]  # [Team 0, Team 1]
        self.dealer = 0
        self.game_history = []
    
    def log(self, msg):
        """Print if verbose"""
        if self.verbose:
            print(msg)
    
    def play_game(self, target_score=120) -> Tuple[int, List[dict]]:
        """
        Play a complete game to target score.
        Returns (winning_team, game_history)
        """
        self.reset()
        round_num = 0
        
        while max(self.scores) < target_score:
            round_num += 1
            self.log(f"\n{'='*60}")
            self.log(f"ROUND {round_num} - Dealer: Player {self.dealer}")
            self.log(f"Scores: Team 0: {self.scores[0]}, Team 1: {self.scores[1]}")
            
            round_result = self.play_round()
            self.game_history.append(round_result)
            
            # Update scores
            team0_delta, team1_delta = round_result['score_change']
            self.scores[0] += team0_delta
            self.scores[1] += team1_delta
            
            self.log(f"Round result: Team 0: {team0_delta:+d}, Team 1: {team1_delta:+d}")
            self.log(f"New scores: Team 0: {self.scores[0]}, Team 1: {self.scores[1]}")
            
            # Move dealer
            self.dealer = (self.dealer + 1) % 4
            
            # Safety check - prevent infinite games
            if round_num > 100:
                self.log("WARNING: Game exceeded 100 rounds, ending")
                break
        
        winner = 0 if self.scores[0] >= target_score else 1
        self.log(f"\n{'='*60}")
        self.log(f"GAME OVER! Team {winner} wins!")
        self.log(f"Final scores: Team 0: {self.scores[0]}, Team 1: {self.scores[1]}")
        
        return winner, self.game_history
    
    def play_round(self) -> dict:
        """Play one complete round (bidding, discarding, playing 5 tricks)"""
        
        # Deal cards
        deck = Deck().shuffle()
        hands = [deck.deal(5) for _ in range(4)]
        kitty = deck.deal(3)
        
        self.log("\n--- BIDDING ---")
        
        # Bidding phase
        bids = []
        high_bid = 0
        bid_winner = None
        trump_suit = None
        
        first_bidder = (self.dealer + 1) % 4
        for i in range(4):
            player_idx = (first_bidder + i) % 4
            player = self.players[player_idx]
            team = player_idx % 2
            
            bid, suit = player.decide_bid(
                hands[player_idx],
                high_bid,
                self.dealer,
                self.scores[team],
                self.scores[1 - team]
            )
            
            bids.append(bid)
            
            if bid > high_bid:
                high_bid = bid
                bid_winner = player_idx
                trump_suit = suit
                self.log(f"Player {player_idx}: bids {bid} (trump: {suit.value})")
            else:
                self.log(f"Player {player_idx}: passes")
        
        # If everyone passed, dealer must bid 15
        if bid_winner is None:
            bid_winner = self.dealer
            high_bid = 15
            _, trump_suit = self.players[self.dealer].decide_bid(
                hands[self.dealer], 0, self.dealer,
                self.scores[self.dealer % 2],
                self.scores[1 - (self.dealer % 2)]
            )
            self.log(f"All passed - Dealer (Player {self.dealer}) must bid 15 (trump: {trump_suit.value})")
        
        # Bid winner gets kitty
        hands[bid_winner].extend(kitty)
        
        self.log("\n--- DISCARDING ---")
        
        # Discarding phase
        cards_drawn = [0, 0, 0, 0]
        for i in range(4):
            player = self.players[i]
            is_bidder = (i == bid_winner)
            
            discards = player.choose_discards(hands[i], trump_suit, is_bidder, high_bid)
            
            # Remove discards
            for card in discards:
                if card in hands[i]:
                    hands[i].remove(card)
            
            # Draw cards to get back to 5
            num_draw = max(0, 5 - len(hands[i]))
            drawn = deck.deal(num_draw)
            hands[i].extend(drawn)
            cards_drawn[i] = num_draw
            
            if is_bidder:
                self.log(f"Player {i} (BIDDER): discarded {len(discards)}, drew {num_draw}")
            else:
                self.log(f"Player {i}: discarded {len(discards)}, drew {num_draw}")
        
        self.log("\n--- PLAYING ---")
        
        # Playing phase
        tricks_won = [0, 0]  # Team tricks
        trick_leader = bid_winner
        known_out_of_trump = [False, False, False, False]
        cards_played = []
        bidder_lost_trick = False
        high_trump_rank = -1
        high_trump_winner = -1
        
        for trick_num in range(1, 6):
            self.log(f"\nTrick {trick_num} - Leader: Player {trick_leader}")
            
            trick, trick_leader, known_out_of_trump, high_trump_rank, high_trump_winner = self.play_trick(
                hands,
                trick_leader,
                trump_suit,
                bid_winner,
                high_bid,
                trick_num,
                cards_drawn,
                known_out_of_trump,
                cards_played,
                high_trump_rank,
                high_trump_winner
            )
            
            # Update cards played
            for _, card in trick:
                cards_played.append(card)
            
            # Update tricks won
            winner_team = trick_leader % 2
            tricks_won[winner_team] += 1
            
            # Track if bidder lost a trick
            bidder_team = bid_winner % 2
            if winner_team != bidder_team:
                bidder_lost_trick = True
            
            self.log(f"Winner: Player {trick_leader} (Team {winner_team})")
        
        self.log(f"\nTricks won: Team 0: {tricks_won[0]}, Team 1: {tricks_won[1]}")
        self.log(f"High trump winner: Player {high_trump_winner}")
        
        # Calculate scores
        bidder_team = bid_winner % 2
        score_change = calculate_points(tricks_won, bidder_team, high_bid, high_trump_winner)
        
        return {
            'bids': bids,
            'bid_winner': bid_winner,
            'high_bid': high_bid,
            'trump_suit': trump_suit,
            'tricks_won': tricks_won,
            'score_change': score_change,
            'made_bid': score_change[bidder_team] > 0,
            'high_trump_winner': high_trump_winner
        }
    
    def play_trick(self, hands: List[List[Card]], leader: int, trump_suit: Suit,
                   bid_winner: int, high_bid: int, trick_num: int,
                   cards_drawn: List[int], known_out_of_trump: List[bool],
                   cards_played: List[Card], high_trump_rank: int, 
                   high_trump_winner: int) -> Tuple[List[Tuple[int, Card]], int, List[bool], int, int]:
        """
        Play one trick.
        Returns (trick_cards, winner, updated_known_out_of_trump, high_trump_rank, high_trump_winner)
        """
        
        trick = []
        current_player = leader
        
        for i in range(4):
            # Create game state for AI
            state = GameState(
                hands=[h.copy() for h in hands],  # Copy to prevent cheating
                trump_suit=trump_suit,
                bid_winner=bid_winner,
                high_bid=high_bid,
                dealer=self.dealer,
                current_trick=trick.copy(),
                trick_leader=leader,
                tricks_won=[0, 0],  # Not used in card selection
                trick_num=trick_num,
                cards_drawn=cards_drawn,
                cards_played=cards_played.copy(),
                known_out_of_trump=known_out_of_trump.copy(),
                bidder_lost_trick=False,  # Simplified for now
                high_trump_rank=high_trump_rank,
                high_trump_winner=high_trump_winner
            )
            
            # AI chooses card
            card = self.players[current_player].choose_card(state)
            
            # Verify legal play
            led_card = trick[0][1] if trick else None
            playable = get_playable_cards(hands[current_player], trump_suit, led_card)
            
            if card not in playable:
                # AI made illegal play - pick first playable card
                self.log(f"WARNING: Player {current_player} attempted illegal play {card}")
                card = playable[0]
            
            # Remove card from hand
            hands[current_player].remove(card)
            trick.append((current_player, card))
            
            self.log(f"Player {current_player} plays {card}")
            
            # Update high trump tracking
            trump_rank = get_trump_rank(card, trump_suit)
            if trump_rank > high_trump_rank:
                high_trump_rank = trump_rank
                high_trump_winner = current_player
                self.log(f"  -> New high trump! (rank {trump_rank})")
            
            # Update known_out_of_trump
            if led_card and is_trump(led_card, trump_suit) and not is_trump(card, trump_suit):
                known_out_of_trump[current_player] = True
            
            current_player = (current_player + 1) % 4
        
        # Determine winner
        winner = evaluate_trick(trick, trump_suit, leader)
        
        return trick, winner, known_out_of_trump, high_trump_rank, high_trump_winner

def run_tournament(num_games=1000, verbose=False):
    """
    Run a tournament of games and collect statistics.
    """
    print(f"Running tournament: {num_games} games")
    
    # Create players (all heuristic for now)
    players = [HeuristicAI(i) for i in range(4)]
    
    results = {
        'team0_wins': 0,
        'team1_wins': 0,
        'team0_total_score': 0,
        'team1_total_score': 0,
        'rounds_per_game': [],
        'bids_made': 0,
        'bids_set': 0
    }
    
    import time
    start_time = time.time()
    
    for game_num in range(num_games):
        # Progress bar
        if (game_num + 1) % max(1, num_games // 50) == 0 or game_num == 0:
            elapsed = time.time() - start_time
            games_per_sec = (game_num + 1) / elapsed if elapsed > 0 else 0
            percent = (game_num + 1) / num_games * 100
            
            # Calculate ETA
            if games_per_sec > 0:
                remaining = (num_games - game_num - 1) / games_per_sec
                eta_min = int(remaining // 60)
                eta_sec = int(remaining % 60)
                eta_str = f"{eta_min}m {eta_sec}s" if eta_min > 0 else f"{eta_sec}s"
            else:
                eta_str = "calculating..."
            
            # Progress bar
            bar_length = 40
            filled = int(bar_length * (game_num + 1) / num_games)
            bar = '█' * filled + '░' * (bar_length - filled)
            
            print(f"\r[{bar}] {percent:5.1f}% | {game_num + 1}/{num_games} games | {games_per_sec:.1f} g/s | ETA: {eta_str}", end='', flush=True)
        
        game = Game45s(players, verbose=verbose)
        winner, history = game.play_game()
        
        results['rounds_per_game'].append(len(history))
        
        if winner == 0:
            results['team0_wins'] += 1
            results['team0_total_score'] += game.scores[0]
            results['team1_total_score'] += game.scores[1]
        else:
            results['team1_wins'] += 1
            results['team0_total_score'] += game.scores[0]
            results['team1_total_score'] += game.scores[1]
        
        # Count bids made/set
        for round_data in history:
            if round_data['made_bid']:
                results['bids_made'] += 1
            else:
                results['bids_set'] += 1
    
    print()  # New line after progress bar
    elapsed = time.time() - start_time
    
    # Print results
    print("\n" + "="*60)
    print("TOURNAMENT RESULTS")
    print("="*60)
    print(f"Games played: {num_games}")
    print(f"Time elapsed: {elapsed:.1f}s ({num_games/elapsed:.1f} games/sec)")
    print(f"Team 0 wins: {results['team0_wins']} ({results['team0_wins']/num_games*100:.1f}%)")
    print(f"Team 1 wins: {results['team1_wins']} ({results['team1_wins']/num_games*100:.1f}%)")
    print(f"Average rounds per game: {sum(results['rounds_per_game'])/len(results['rounds_per_game']):.1f}")
    print(f"Average score - Team 0: {results['team0_total_score']/num_games:.1f}")
    print(f"Average score - Team 1: {results['team1_total_score']/num_games:.1f}")
    print(f"Bids made: {results['bids_made']} ({results['bids_made']/(results['bids_made']+results['bids_set'])*100:.1f}%)")
    print(f"Bids set: {results['bids_set']} ({results['bids_set']/(results['bids_made']+results['bids_set'])*100:.1f}%)")
    
    return results

def compare_strategies(num_games=1000, mc_rollouts=100, verbose=False):
    """
    Compare Heuristic AI vs Monte Carlo AI.
    Team 0: Heuristic
    Team 1: Monte Carlo
    """
    print(f"Running comparison tournament: {num_games} games")
    print(f"Team 0: Heuristic AI")
    print(f"Team 1: Monte Carlo AI ({mc_rollouts} rollouts)")
    print()
    
    # Create mixed teams
    players = [
        HeuristicAI(0),      # Team 0
        MonteCarloAI(1, mc_rollouts),  # Team 1
        HeuristicAI(2),      # Team 0
        MonteCarloAI(3, mc_rollouts)   # Team 1
    ]
    
    results = {
        'heuristic_wins': 0,
        'montecarlo_wins': 0,
        'heuristic_total_score': 0,
        'montecarlo_total_score': 0,
        'rounds_per_game': [],
        'bids_made': 0,
        'bids_set': 0,
        'high_trick_stats': {'heuristic': 0, 'montecarlo': 0}
    }
    
    import time
    start_time = time.time()
    
    for game_num in range(num_games):
        # Progress bar
        if (game_num + 1) % max(1, num_games // 50) == 0 or game_num == 0:
            elapsed = time.time() - start_time
            games_per_sec = (game_num + 1) / elapsed if elapsed > 0 else 0
            percent = (game_num + 1) / num_games * 100
            
            # Calculate ETA
            if games_per_sec > 0:
                remaining = (num_games - game_num - 1) / games_per_sec
                eta_min = int(remaining // 60)
                eta_sec = int(remaining % 60)
                eta_str = f"{eta_min}m {eta_sec}s" if eta_min > 0 else f"{eta_sec}s"
            else:
                eta_str = "calculating..."
            
            # Progress bar
            bar_length = 40
            filled = int(bar_length * (game_num + 1) / num_games)
            bar = '█' * filled + '░' * (bar_length - filled)
            
            print(f"\r[{bar}] {percent:5.1f}% | {game_num + 1}/{num_games} games | {games_per_sec:.2f} g/s | ETA: {eta_str}", end='', flush=True)
        
        game = Game45s(players, verbose=verbose)
        winner, history = game.play_game()
        
        results['rounds_per_game'].append(len(history))
        
        if winner == 0:  # Heuristic wins
            results['heuristic_wins'] += 1
            results['heuristic_total_score'] += game.scores[0]
            results['montecarlo_total_score'] += game.scores[1]
        else:  # Monte Carlo wins
            results['montecarlo_wins'] += 1
            results['heuristic_total_score'] += game.scores[0]
            results['montecarlo_total_score'] += game.scores[1]
        
        # Count bids made/set and high trick winners
        for round_data in history:
            if round_data['made_bid']:
                results['bids_made'] += 1
            else:
                results['bids_set'] += 1
            
            # Track high trick
            ht_winner = round_data['high_trump_winner']
            if ht_winner % 2 == 0:
                results['high_trick_stats']['heuristic'] += 1
            else:
                results['high_trick_stats']['montecarlo'] += 1
    
    print()  # New line after progress bar
    elapsed = time.time() - start_time
    
    # Print results
    print("\n" + "="*60)
    print("COMPARISON RESULTS")
    print("="*60)
    print(f"Games played: {num_games}")
    print(f"Time elapsed: {elapsed:.1f}s ({num_games/elapsed:.2f} games/sec)")
    print()
    print(f"Heuristic AI wins: {results['heuristic_wins']} ({results['heuristic_wins']/num_games*100:.1f}%)")
    print(f"Monte Carlo AI wins: {results['montecarlo_wins']} ({results['montecarlo_wins']/num_games*100:.1f}%)")
    print()
    print(f"Average rounds per game: {sum(results['rounds_per_game'])/len(results['rounds_per_game']):.1f}")
    print(f"Average score - Heuristic: {results['heuristic_total_score']/num_games:.1f}")
    print(f"Average score - Monte Carlo: {results['montecarlo_total_score']/num_games:.1f}")
    print()
    print(f"Bids made: {results['bids_made']} ({results['bids_made']/(results['bids_made']+results['bids_set'])*100:.1f}%)")
    print(f"Bids set: {results['bids_set']} ({results['bids_set']/(results['bids_made']+results['bids_set'])*100:.1f}%)")
    print()
    print(f"High tricks - Heuristic: {results['high_trick_stats']['heuristic']}")
    print(f"High tricks - Monte Carlo: {results['high_trick_stats']['montecarlo']}")
    
    return results

if __name__ == "__main__":
    # Test single game
    print("Testing single game...")
    players = [HeuristicAI(i) for i in range(4)]
    game = Game45s(players, verbose=True)
    winner, history = game.play_game()
    
    print("\n" + "="*60)
    print("Running quick tournament...")
    run_tournament(num_games=100, verbose=False)
