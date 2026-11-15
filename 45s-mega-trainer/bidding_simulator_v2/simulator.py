# -*- coding: utf-8 -*-
"""
simulator.py - 45s Bidding Simulator v2

Entry point. Orchestrates:
  - CPU parallel round simulation (all cores via multiprocessing)
  - Workers generate their own decks in-process (no IPC pickling overhead)
  - SQLite batch logging
  - Real-time progress bar
  - Post-run report

GPU (RTX 3070) is available and detected; used by deck_generator when
called from the main process for future Monte Carlo batching. Workers use
CPU numpy to avoid cross-process GPU context issues.

Usage:
    python -m bidding_simulator_v2.simulator
    python -m bidding_simulator_v2.simulator --rounds 1000000
    python -m bidding_simulator_v2.simulator --workers 8
    python -m bidding_simulator_v2.simulator --db my.db --summary out.json
    python -m bidding_simulator_v2.simulator --min-samples 500
"""

import sys
import io
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Ensure UTF-8 output on Windows (suit symbols etc.)
if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding and \
        sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import argparse
import time
import multiprocessing as mp
from multiprocessing import Pool
from typing import List, Tuple, Dict, Any

from game_engine import Card, Suit, Deck
from bidding_simulator_v2.improved_ai    import ImprovedAI
from bidding_simulator_v2.hand_analyzer  import analyze_hand, find_best_trump_suit, is_viable_bid
from bidding_simulator_v2.round_runner   import play_round
from bidding_simulator_v2.deck_generator import DeckGenerator, GPU_AVAILABLE, GPU_NAME
from bidding_simulator_v2.db             import open_db, create_run, finish_run, BatchBuffer
from bidding_simulator_v2.reporter       import generate_report

GAME_VERSION = '2.31.23'
BIDS         = [15, 20, 25, 30]
BIDDER       = 0        # Player 0 is always the forced bidder

# Rounds per worker task — large enough to amortise spawn overhead on Windows,
# small enough to give smooth progress bar updates.
CHUNK = 500


# =============================================================================
# Worker (runs in subprocess — no GPU access, generates own decks via numpy)
# =============================================================================

def _worker(args: Tuple) -> List[Dict[str, Any]]:
    """
    Simulate num_rounds rounds entirely in-process.
    Workers use numpy for deck shuffling — eliminates pickling Card objects
    through IPC and gives near-linear CPU scaling.

    args: (num_rounds, run_id)
    Returns: list of row dicts ready for SQLite insertion.
    """
    num_rounds, run_id = args

    gen        = DeckGenerator(use_gpu=False)   # CPU numpy in workers
    ai_players = [ImprovedAI(i) for i in range(4)]
    results    = []

    for deck in gen.generate_batch(num_rounds):
        hands     = [deck[i*5:(i+1)*5] for i in range(4)]
        kitty     = deck[20:23]
        remaining = deck[23:]

        best_trump = find_best_trump_suit(hands[BIDDER])
        profile    = analyze_hand(hands[BIDDER], best_trump)

        for bid in BIDS:
            if not is_viable_bid(profile, bid):
                continue

            made, tricks, points = play_round(
                bid            = bid,
                trump_suit     = best_trump,
                hands          = hands,
                kitty          = kitty,
                remaining_deck = remaining,
                ai_players     = ai_players,
            )

            row = profile.as_row()
            row.update({
                'run_id':        run_id,
                'bid_tested':    bid,
                'round_made':    int(made),
                'tricks_won':    tricks,
                'points_scored': points,
            })
            results.append(row)

    return results


# =============================================================================
# Progress bar
# =============================================================================

def _fmt_time(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"


def _progress(done: int, total: int, rows: int, start: float, bar_len: int = 46) -> str:
    pct      = done / total if total else 0
    filled   = int(bar_len * pct)
    bar      = '#' * filled + '-' * (bar_len - filled)
    elapsed  = time.time() - start
    eta_str  = '   ...'
    rate_str = '    ---'
    if elapsed > 0 and done > 0:
        rate     = rows / elapsed
        eta_sec  = (total - done) * (elapsed / done)
        eta_str  = _fmt_time(eta_sec).rjust(6)
        rate_str = f"{rate:>7,.0f}/s"
    return (
        f"\r  [{bar}] {pct*100:5.1f}%  "
        f"{rows:>11,} tests | {rate_str} | "
        f"{_fmt_time(elapsed)} elapsed | ETA {eta_str}"
    )


# =============================================================================
# Main simulation loop
# =============================================================================

def run_simulation(
    num_rounds:   int,
    num_workers:  int,
    db_path:      str,
    summary_path: str,
    min_samples:  int,
    ai_type:      str = 'improved_heuristic',
) -> None:

    W = 66
    print()
    print('=' * W)
    print('  45s BIDDING SIMULATOR v2')
    print('=' * W)
    print(f'  Rounds:   {num_rounds:,}')
    print(f'  Workers:  {num_workers} CPU cores')
    print(f'  GPU:      {GPU_NAME if GPU_AVAILABLE else "not available"}')
    print(f'  AI:       {ai_type}')
    print(f'  DB:       {db_path}')
    print('=' * W)
    print()

    conn   = open_db(db_path)
    run_id = create_run(
        conn,
        version    = GAME_VERSION,
        num_rounds = num_rounds,
        ai_type    = ai_type,
        config     = {
            'rounds':        num_rounds,
            'workers':       num_workers,
            'gpu_available': GPU_AVAILABLE,
            'gpu_name':      GPU_NAME,
            'min_samples':   min_samples,
        }
    )

    buf        = BatchBuffer(conn)
    start_time = time.time()

    # Build task list: each task is (rounds_this_chunk, run_id)
    tasks     = []
    remaining = num_rounds
    while remaining > 0:
        n = min(CHUNK, remaining)
        tasks.append((n, run_id))
        remaining -= n

    print('  Simulating...')
    print()

    total_rows  = 0
    done_rounds = 0

    with Pool(processes=num_workers) as pool:
        for batch_rows in pool.imap_unordered(_worker, tasks):
            buf.add_many(batch_rows)
            total_rows  += len(batch_rows)
            done_rounds  = min(done_rounds + CHUNK, num_rounds)
            print(
                _progress(done_rounds, num_rounds, total_rows, start_time).ljust(110),
                end='', flush=True
            )

    buf.flush()
    elapsed = time.time() - start_time

    print()
    print()
    print(f'  Done in {_fmt_time(elapsed)}')
    print(f'  Bid tests logged:  {buf.total_inserted:,}')
    if elapsed > 0:
        print(f'  Tests/sec:         {buf.total_inserted/elapsed:,.0f}')
        print(f'  Rounds/sec:        {num_rounds/elapsed:,.0f}')
    print()

    finish_run(conn, run_id)
    conn.close()

    generate_report(
        db_path     = db_path,
        json_path   = summary_path,
        run_id      = run_id,
        min_samples = min_samples,
    )


# =============================================================================
# CLI
# =============================================================================

def main():
    p = argparse.ArgumentParser(
        description='45s Bidding Simulator v2'
    )
    p.add_argument('--rounds',      type=int, default=500_000,
                   help='Rounds to simulate (default: 500000)')
    p.add_argument('--workers',     type=int, default=mp.cpu_count(),
                   help='CPU worker processes (default: all cores)')
    p.add_argument('--db',          type=str, default='bidding_sim_v2.db',
                   help='SQLite output (default: bidding_sim_v2.db)')
    p.add_argument('--summary',     type=str, default='bidding_summary.json',
                   help='JSON summary output (default: bidding_summary.json)')
    p.add_argument('--min-samples', type=int, default=200,
                   help='Min samples per category in report (default: 200)')

    args = p.parse_args()

    run_simulation(
        num_rounds   = args.rounds,
        num_workers  = args.workers,
        db_path      = args.db,
        summary_path = args.summary,
        min_samples  = args.min_samples,
    )


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)   # required on Windows
    main()
