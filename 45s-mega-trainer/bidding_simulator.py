"""
Extended Bidding Simulator for 45s
Tracks bid success rates by hand composition to calibrate AI bidding thresholds.

Optimized for:
- NVIDIA RTX 3070 GPU (for future neural network inference)
- 12 CPU cores (multiprocessing for parallel simulation)

Tracks:
- Initial hand composition (has5, hasJ, hasAH, hasAT, trumpCount, highTrumps)
- Bid amount (15, 20, 25, 30)
- Whether bid was made or set
- Trump exhaustion scenarios (4+ high trump = guaranteed win)
"""

from game_engine import *
from ai_players import HeuristicAI
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import multiprocessing as mp
from multiprocessing import Pool, Manager
import json
import time
import os

# Detect available resources (suppress prints in worker processes)
NUM_CORES = min(12, mp.cpu_count())  # Use up to 12 cores
GPU_AVAILABLE = False
GPU_NAME = "N/A"

# Only print hardware info in main process
if __name__ == "__main__" or mp.current_process().name == 'MainProcess':
    _is_main = True
else:
    _is_main = False

if _is_main:
    print(f"Detected {mp.cpu_count()} CPU cores, using {NUM_CORES}")
    # Check for GPU
    try:
        import torch
        GPU_AVAILABLE = torch.cuda.is_available()
        if GPU_AVAILABLE:
            GPU_NAME = torch.cuda.get_device_name(0)
            print(f"GPU detected: {GPU_NAME}")
        else:
            print("No GPU detected, using CPU only")
    except ImportError:
        GPU_AVAILABLE = False
        print("PyTorch not installed, GPU acceleration unavailable")


@dataclass
class HandProfile:
    """Profile of a hand at bidding time"""
    has_5: bool
    has_j: bool
    has_ah: bool  # Ace of Hearts
    has_at: bool  # Ace of trump (not hearts)
    trump_count: int
    high_trump_count: int  # 5, J, AH, AT, K, Q

    def to_key(self) -> str:
        """Convert to string key for tracking"""
        return f"5:{int(self.has_5)}_J:{int(self.has_j)}_AH:{int(self.has_ah)}_AT:{int(self.has_at)}_T:{self.trump_count}_HT:{self.high_trump_count}"

    def to_dict(self) -> dict:
        return {
            'has_5': self.has_5,
            'has_j': self.has_j,
            'has_ah': self.has_ah,
            'has_at': self.has_at,
            'trump_count': self.trump_count,
            'high_trump_count': self.high_trump_count
        }

    def is_guaranteed_30(self) -> bool:
        """
        Check if hand guarantees 30 via trump exhaustion.
        4 of the top 4 trump (5, J, AH, AT) = guaranteed all 5 tricks
        """
        top4_count = sum([self.has_5, self.has_j, self.has_ah, self.has_at])
        return top4_count >= 4

    def is_near_guaranteed_30(self) -> bool:
        """
        Check if hand is near-guaranteed 30.
        3 of top 4 trump + high trump count >= 4 (has K or Q too)
        """
        top4_count = sum([self.has_5, self.has_j, self.has_ah, self.has_at])
        return top4_count >= 3 and self.high_trump_count >= 4


@dataclass
class BidResult:
    """Result of a single bid test"""
    profile_key: str
    profile_dict: dict
    category: str
    bid: int
    made: bool
    tricks_won: int


def get_category(profile: HandProfile) -> str:
    """Categorize hand for simplified analysis"""
    if profile.is_guaranteed_30():
        return "GUARANTEED_30"
    if profile.is_near_guaranteed_30():
        return "NEAR_GUARANTEED_30"

    # Build category string
    parts = []
    if profile.has_5:
        parts.append("5")
    if profile.has_j:
        parts.append("J")
    if profile.has_ah:
        parts.append("AH")
    if profile.has_at:
        parts.append("AT")

    if not parts:
        parts.append("NO_HIGH")

    parts.append(f"T{profile.trump_count}")

    return "_".join(parts)


def analyze_hand(hand: List[Card], trump_suit: Suit) -> HandProfile:
    """Analyze a hand and return its profile"""
    # Use string comparisons - game_engine uses strings for ranks, not enums
    has_5 = any(c.rank == '5' and c.suit == trump_suit for c in hand)
    has_j = any(c.rank == 'J' and c.suit == trump_suit for c in hand)
    has_ah = any(c.rank == 'A' and c.suit == Suit.HEARTS for c in hand)
    has_at = any(c.rank == 'A' and c.suit == trump_suit and trump_suit != Suit.HEARTS for c in hand)

    trump_count = sum(1 for c in hand if is_trump(c, trump_suit))

    # Count high trump (5, J, AH, AT, K, Q of trump)
    high_trump = 0
    for c in hand:
        if is_trump(c, trump_suit):
            if c.rank in ['5', 'J', 'K', 'Q']:
                high_trump += 1
            elif c.rank == 'A':
                high_trump += 1

    return HandProfile(
        has_5=has_5,
        has_j=has_j,
        has_ah=has_ah,
        has_at=has_at,
        trump_count=trump_count,
        high_trump_count=high_trump
    )


def find_best_trump_suit(hand: List[Card]) -> Tuple[Suit, int, bool, bool]:
    """Find the best trump suit for a hand"""
    best_suit = None
    best_score = -1
    best_count = 0
    best_has_5 = False
    best_has_j = False

    for suit in Suit:
        count = sum(1 for c in hand if is_trump(c, suit))
        has_5 = any(c.rank == '5' and c.suit == suit for c in hand)
        has_j = any(c.rank == 'J' and c.suit == suit for c in hand)

        # Prioritize: has_5 > has_j > trump_count
        score = count + (10 if has_5 else 0) + (5 if has_j else 0)

        if score > best_score:
            best_suit = suit
            best_score = score
            best_count = count
            best_has_5 = has_5
            best_has_j = has_j

    return best_suit, best_count, best_has_5, best_has_j


def play_round_with_bid(
    hands: List[List[Card]],
    kitty: List[Card],
    remaining_deck: List[Card],
    bid_winner: int,
    bid_amount: int,
    trump_suit: Suit,
    players: List[HeuristicAI]
) -> Tuple[bool, int]:
    """
    Play out a round with a specific bidder and bid.
    Returns (made_bid, tricks_won_by_bidder_team)
    """
    # Make copies to avoid mutation
    hands = [h.copy() for h in hands]

    # Bid winner gets kitty
    hands[bid_winner].extend(kitty)

    # Discarding phase
    deck_for_draw = remaining_deck.copy()

    for i in range(4):
        is_bidder = (i == bid_winner)
        discards = players[i].choose_discards(hands[i], trump_suit, is_bidder, bid_amount)

        for card in discards:
            if card in hands[i]:
                hands[i].remove(card)

        # Draw back to 5
        num_draw = max(0, 5 - len(hands[i]))
        for _ in range(num_draw):
            if deck_for_draw:
                hands[i].append(deck_for_draw.pop())

    # Playing phase
    tricks_won = [0, 0]
    trick_leader = bid_winner
    known_out = [False, False, False, False]
    cards_played = []
    high_trump_rank = -1
    high_trump_winner = -1

    for trick_num in range(1, 6):
        trick = []
        current = trick_leader

        for _ in range(4):
            state = GameState(
                hands=[h.copy() for h in hands],
                trump_suit=trump_suit,
                bid_winner=bid_winner,
                high_bid=bid_amount,
                dealer=0,
                current_trick=trick.copy(),
                trick_leader=trick_leader,
                tricks_won=tricks_won.copy(),
                trick_num=trick_num,
                cards_drawn=[0, 0, 0, 0],
                cards_played=cards_played.copy(),
                known_out_of_trump=known_out.copy(),
                bidder_lost_trick=False,
                high_trump_rank=high_trump_rank,
                high_trump_winner=high_trump_winner
            )

            card = players[current].choose_card(state)

            # Validate legal play
            led = trick[0][1] if trick else None
            playable = get_playable_cards(hands[current], trump_suit, led)
            if card not in playable:
                card = playable[0] if playable else hands[current][0]

            hands[current].remove(card)
            trick.append((current, card))
            cards_played.append(card)

            # Track high trump
            trump_rank = get_trump_rank(card, trump_suit)
            if trump_rank > high_trump_rank:
                high_trump_rank = trump_rank
                high_trump_winner = current

            # Track out of trump
            if led and is_trump(led, trump_suit) and not is_trump(card, trump_suit):
                known_out[current] = True

            current = (current + 1) % 4

        # Determine winner
        winner = evaluate_trick(trick, trump_suit, trick_leader)
        tricks_won[winner % 2] += 1
        trick_leader = winner

    # Calculate if bid was made
    bidder_team = bid_winner % 2
    team_tricks = tricks_won[bidder_team]

    # Points: 5 per trick, +5 for high trump if on bidder's team
    points = team_tricks * 5
    if high_trump_winner % 2 == bidder_team:
        points += 5

    made = points >= bid_amount

    return made, team_tricks


def simulate_batch(batch_args: Tuple[int, int]) -> List[BidResult]:
    """
    Simulate a batch of rounds. Called by each worker process.
    Returns list of BidResult objects.
    """
    batch_id, num_rounds = batch_args
    results = []

    # Each process creates its own AI players (they're not picklable across processes)
    players = [HeuristicAI(i) for i in range(4)]

    for _ in range(num_rounds):
        # Deal cards
        deck = Deck().shuffle()
        hands = [deck.deal(5) for _ in range(4)]
        kitty = deck.deal(3)
        remaining = deck.cards.copy()

        # For each player, test all viable bids
        for player_idx in range(4):
            hand = hands[player_idx]
            trump_suit, trump_count, has_5, has_j = find_best_trump_suit(hand)

            # Skip very weak hands
            if trump_count < 2 and not has_5 and not has_j:
                continue

            profile = analyze_hand(hand, trump_suit)
            category = get_category(profile)

            # Test each viable bid level
            for test_bid in [15, 20, 25, 30]:
                # Skip unrealistic bids
                if test_bid >= 25 and not profile.has_5 and not profile.has_j:
                    continue
                if test_bid == 30 and profile.trump_count < 3:
                    continue

                made, tricks = play_round_with_bid(
                    [h.copy() for h in hands],
                    kitty.copy(),
                    remaining.copy(),
                    player_idx,
                    test_bid,
                    trump_suit,
                    players
                )

                results.append(BidResult(
                    profile_key=profile.to_key(),
                    profile_dict=profile.to_dict(),
                    category=category,
                    bid=test_bid,
                    made=made,
                    tricks_won=tricks
                ))

    return results


class BiddingTracker:
    """Tracks bidding statistics by hand profile and bid amount"""

    def __init__(self):
        # stats[bid_amount][category] = {'attempts': 0, 'made': 0, 'tricks': 0}
        self.stats: Dict[int, Dict[str, Dict]] = {
            15: defaultdict(lambda: {'attempts': 0, 'made': 0, 'tricks': 0}),
            20: defaultdict(lambda: {'attempts': 0, 'made': 0, 'tricks': 0}),
            25: defaultdict(lambda: {'attempts': 0, 'made': 0, 'tricks': 0}),
            30: defaultdict(lambda: {'attempts': 0, 'made': 0, 'tricks': 0})
        }

        # Detailed stats by full profile key
        self.detailed: Dict[int, Dict[str, Dict]] = {
            15: defaultdict(lambda: {'attempts': 0, 'made': 0, 'tricks': 0, 'profile': None}),
            20: defaultdict(lambda: {'attempts': 0, 'made': 0, 'tricks': 0, 'profile': None}),
            25: defaultdict(lambda: {'attempts': 0, 'made': 0, 'tricks': 0, 'profile': None}),
            30: defaultdict(lambda: {'attempts': 0, 'made': 0, 'tricks': 0, 'profile': None})
        }

        self.total_results = 0

    def add_result(self, result: BidResult):
        """Add a single result"""
        bid = result.bid
        cat = result.category
        key = result.profile_key

        self.stats[bid][cat]['attempts'] += 1
        self.stats[bid][cat]['tricks'] += result.tricks_won
        if result.made:
            self.stats[bid][cat]['made'] += 1

        self.detailed[bid][key]['attempts'] += 1
        self.detailed[bid][key]['tricks'] += result.tricks_won
        self.detailed[bid][key]['profile'] = result.profile_dict
        if result.made:
            self.detailed[bid][key]['made'] += 1

        self.total_results += 1

    def add_results(self, results: List[BidResult]):
        """Add multiple results"""
        for r in results:
            self.add_result(r)

    def get_summary(self) -> dict:
        """Get summary statistics"""
        summary = {
            'total_bid_tests': self.total_results,
            'by_bid': {},
            'by_category': {},
            'recommendations': {},
            'detailed': {}
        }

        # Overall by bid amount
        for bid in [15, 20, 25, 30]:
            total_attempts = sum(s['attempts'] for s in self.stats[bid].values())
            total_made = sum(s['made'] for s in self.stats[bid].values())
            if total_attempts > 0:
                summary['by_bid'][bid] = {
                    'attempts': total_attempts,
                    'made': total_made,
                    'success_rate': round(total_made / total_attempts * 100, 2)
                }

        # By category
        all_categories = set()
        for bid in [15, 20, 25, 30]:
            all_categories.update(self.stats[bid].keys())

        for category in sorted(all_categories):
            cat_data = {}
            for bid in [15, 20, 25, 30]:
                s = self.stats[bid][category]
                if s['attempts'] > 0:
                    cat_data[bid] = {
                        'attempts': s['attempts'],
                        'made': s['made'],
                        'success_rate': round(s['made'] / s['attempts'] * 100, 2),
                        'avg_tricks': round(s['tricks'] / s['attempts'], 2)
                    }
            if cat_data:
                summary['by_category'][category] = cat_data

        # Generate recommendations
        summary['recommendations'] = self._generate_recommendations()

        # Detailed by profile key (top entries only to keep file size reasonable)
        for bid in [15, 20, 25, 30]:
            sorted_profiles = sorted(
                [(k, v) for k, v in self.detailed[bid].items() if v['attempts'] >= 20],
                key=lambda x: x[1]['attempts'],
                reverse=True
            )[:50]  # Top 50 per bid

            summary['detailed'][bid] = {
                k: {
                    'attempts': v['attempts'],
                    'made': v['made'],
                    'success_rate': round(v['made'] / v['attempts'] * 100, 2) if v['attempts'] > 0 else 0,
                    'avg_tricks': round(v['tricks'] / v['attempts'], 2) if v['attempts'] > 0 else 0,
                    'profile': v['profile']
                }
                for k, v in sorted_profiles
            }

        return summary

    def _generate_recommendations(self) -> Dict[str, dict]:
        """Generate bidding recommendations for each category"""
        recs = {}

        all_categories = set()
        for bid in [15, 20, 25, 30]:
            all_categories.update(self.stats[bid].keys())

        for category in sorted(all_categories):
            best_bid = None
            best_ev = -float('inf')
            bid_options = {}

            for bid in [15, 20, 25, 30]:
                s = self.stats[bid][category]
                if s['attempts'] >= 20:  # Minimum sample size
                    success_rate = s['made'] / s['attempts']
                    # Expected value: success gives +bid, failure gives -bid
                    ev = success_rate * bid - (1 - success_rate) * bid
                    bid_options[bid] = {
                        'success_rate': round(success_rate * 100, 2),
                        'expected_value': round(ev, 2),
                        'attempts': s['attempts']
                    }
                    if ev > best_ev:
                        best_ev = ev
                        best_bid = bid

            if best_bid:
                recs[category] = {
                    'recommended_bid': best_bid,
                    'expected_value': round(best_ev, 2),
                    'all_options': bid_options
                }

        return recs

    def save(self, filename: str):
        """Save statistics to JSON file"""
        data = self.get_summary()
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved statistics to {filename}")


def format_time(seconds: float) -> str:
    """Format seconds into human readable time"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def print_progress_bar(current: int, total: int, start_time: float,
                       results: int = 0, bar_length: int = 50):
    """Print a visual progress bar with stats"""
    elapsed = time.time() - start_time
    percent = current / total if total > 0 else 0
    filled = int(bar_length * percent)
    bar = '█' * filled + '░' * (bar_length - filled)

    # Calculate rate and ETA
    if elapsed > 0 and current > 0:
        rate = results / elapsed
        remaining_batches = total - current
        avg_batch_time = elapsed / current
        eta_seconds = remaining_batches * avg_batch_time
        eta = format_time(eta_seconds)
        rate_str = f"{rate:,.0f}/s"
    else:
        eta = "calculating..."
        rate_str = "---"

    # Build progress line
    pct_str = f"{percent*100:5.1f}%"
    results_str = f"{results:,}" if results > 0 else "---"
    elapsed_str = format_time(elapsed)

    progress_line = f"\r  [{bar}] {pct_str} | {results_str} tests | {rate_str} | {elapsed_str} elapsed | ETA: {eta}"

    # Pad to clear previous line
    print(f"{progress_line:<120}", end='', flush=True)


def run_parallel_simulation(num_rounds: int = 100000, num_workers: int = NUM_CORES) -> BiddingTracker:
    """
    Run bidding simulation using multiple CPU cores.
    """
    print(f"\nUsing {num_workers} worker processes")

    # Divide work into smaller batches for better progress tracking
    # More batches = smoother progress bar updates
    num_batches = max(num_workers * 20, 100)  # At least 100 batches for smooth updates
    rounds_per_batch = max(1, num_rounds // num_batches)

    batches = [(i, rounds_per_batch) for i in range(num_batches)]

    # Handle remainder
    remainder = num_rounds - (rounds_per_batch * num_batches)
    if remainder > 0:
        batches.append((num_batches, remainder))

    tracker = BiddingTracker()
    start_time = time.time()
    total_batches = len(batches)

    print(f"Running {num_rounds:,} rounds in {total_batches} batches...")
    print()

    with Pool(processes=num_workers) as pool:
        completed = 0

        # Initial progress bar
        print_progress_bar(0, total_batches, start_time, 0)

        for batch_results in pool.imap_unordered(simulate_batch, batches):
            completed += 1
            tracker.add_results(batch_results)

            # Update progress bar
            print_progress_bar(completed, total_batches, start_time, tracker.total_results)

    # Final stats
    elapsed = time.time() - start_time
    print()  # Newline after progress bar
    print()
    print(f"  ✓ Completed in {format_time(elapsed)}")
    print(f"  ✓ Total bid tests: {tracker.total_results:,}")
    print(f"  ✓ Average rate: {tracker.total_results/elapsed:,.0f} tests/sec")

    return tracker


def run_bidding_analysis(num_rounds: int = 100000, output_file: str = 'bidding_analysis.json'):
    """Run full bidding analysis and save results"""

    print("="*70)
    print("45s BIDDING ANALYSIS SIMULATOR")
    print("="*70)
    print()
    print(f"Hardware: {NUM_CORES} CPU cores" + (f", {GPU_NAME}" if GPU_AVAILABLE else ""))
    print()
    print("This simulation plays full rounds to determine optimal bidding")
    print("thresholds based on actual success rates with kitty + partner support.")
    print()
    print("Tracks: hand composition, bid amount, success rate, tricks won")
    print("="*70)

    tracker = run_parallel_simulation(num_rounds=num_rounds, num_workers=NUM_CORES)
    summary = tracker.get_summary()

    # Print summary
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)

    print("\n📊 Overall by bid amount:")
    for bid, stats in summary['by_bid'].items():
        print(f"  Bid {bid}: {stats['attempts']:,} attempts, {stats['success_rate']}% success")

    print("\n📋 By hand category (showing categories with 100+ samples):")
    sorted_cats = sorted(
        summary['by_category'].items(),
        key=lambda x: sum(d['attempts'] for d in x[1].values()),
        reverse=True
    )

    for category, bid_stats in sorted_cats[:25]:
        total_attempts = sum(d['attempts'] for d in bid_stats.values())
        if total_attempts < 100:
            continue
        print(f"\n  {category} ({total_attempts:,} total):")
        for bid in [15, 20, 25, 30]:
            if bid in bid_stats and bid_stats[bid]['attempts'] >= 20:
                s = bid_stats[bid]
                print(f"    Bid {bid}: {s['success_rate']:5.1f}% success, {s['avg_tricks']:.1f} avg tricks ({s['attempts']:,} samples)")

    print("\n🎯 RECOMMENDATIONS (optimal bid by hand category):")
    sorted_recs = sorted(
        summary['recommendations'].items(),
        key=lambda x: x[1].get('all_options', {}).get(x[1]['recommended_bid'], {}).get('attempts', 0),
        reverse=True
    )

    for category, rec in sorted_recs[:20]:
        best = rec['recommended_bid']
        ev = rec['expected_value']
        sr = rec['all_options'][best]['success_rate']
        print(f"  {category}: Bid {best} (EV: {ev:+.1f}, {sr:.1f}% success)")

    # Save full results
    tracker.save(output_file)

    return summary


if __name__ == "__main__":
    import sys

    # Allow command line override of rounds
    num_rounds = 100000
    if len(sys.argv) > 1:
        try:
            num_rounds = int(sys.argv[1])
        except ValueError:
            pass

    print(f"\nRunning with {num_rounds:,} rounds")
    print("Usage: python bidding_simulator.py [num_rounds]")
    print()

    run_bidding_analysis(num_rounds=num_rounds, output_file='bidding_analysis.json')
