# -*- coding: utf-8 -*-
"""
reporter.py — Aggregate results and generate output

Reads the SQLite database after simulation and produces:
  - Console summary table
  - bidding_summary.json (consumed by game AI)
"""

import sqlite3
import json
import math
from typing import Dict, List, Tuple, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Wilson score confidence interval
# ─────────────────────────────────────────────────────────────────────────────

def wilson_ci(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """95% Wilson score interval. Returns (lower, upper) as fractions."""
    if n == 0:
        return (0.0, 1.0)
    p  = successes / n
    denom = 1 + z*z / n
    centre = (p + z*z / (2*n)) / denom
    half   = (z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / denom
    return (max(0, centre - half), min(1, centre + half))


def ev(bid: int, success_rate: float) -> float:
    """Expected value of a bid: positive = profitable."""
    return bid * (2 * success_rate - 1)


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def load_category_stats(
    db_path: str,
    run_id: Optional[int],
    min_samples: int
) -> Dict:
    """
    Load aggregated stats per (category, bid_tested) from the database.
    If run_id is None, aggregates across all runs.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    run_filter = f"AND run_id = {run_id}" if run_id is not None else ""

    # Build category expression inline (mirrors get_category logic)
    category_sql = """
        CASE
            WHEN top_sequence >= 4 THEN 'GUARANTEED_30'
            WHEN top_sequence = 3 AND trump_count >= 4 THEN 'NEAR_GUARANTEED_30'
            WHEN has_5=1 AND has_j=1 AND has_ah=1 THEN '5_J_AH_T' || trump_count
            WHEN has_5=1 AND has_j=1              THEN '5_J_T'    || trump_count
            WHEN has_5=1 AND has_ah=1             THEN '5_AH_T'   || trump_count
            WHEN has_5=1                          THEN '5_T'      || trump_count
            WHEN has_j=1 AND has_ah=1             THEN 'J_AH_T'   || trump_count
            WHEN has_j=1                          THEN 'J_T'      || trump_count
            WHEN has_ah=1 AND has_at=1            THEN 'AH_AT_T'  || trump_count
            WHEN has_ah=1                         THEN 'AH_T'     || trump_count
            WHEN has_at=1                         THEN 'AT_T'     || trump_count
            ELSE                                       'NO_HIGH_T' || trump_count
        END
    """

    rows = conn.execute(f"""
        SELECT
            ({category_sql}) AS category,
            bid_tested,
            COUNT(*)              AS n,
            SUM(round_made)       AS made,
            SUM(tricks_won)       AS total_tricks,
            SUM(points_scored)    AS total_points
        FROM hands
        WHERE 1=1 {run_filter}
        GROUP BY category, bid_tested
        HAVING n >= {min_samples}
        ORDER BY category, bid_tested
    """).fetchall()

    conn.close()

    # Restructure: { category: { bid: {...} } }
    stats: Dict[str, Dict[int, dict]] = {}
    for row in rows:
        cat = row['category']
        bid = row['bid_tested']
        n   = row['n']
        made= row['made']
        sr  = made / n
        lo, hi = wilson_ci(made, n)

        stats.setdefault(cat, {})[bid] = {
            'n':           n,
            'made':        made,
            'success_pct': round(sr * 100, 2),
            'ci_lo':       round(lo * 100, 2),
            'ci_hi':       round(hi * 100, 2),
            'avg_tricks':  round(row['total_tricks'] / n, 2),
            'avg_points':  round(row['total_points'] / n, 2),
            'ev':          round(ev(bid, sr), 2),
        }

    return stats


def load_overall_stats(db_path: str, run_id: Optional[int]) -> Dict:
    """Overall success rate per bid level across all hands."""
    conn  = sqlite3.connect(db_path)
    run_filter = f"AND run_id = {run_id}" if run_id is not None else ""
    rows  = conn.execute(f"""
        SELECT bid_tested, COUNT(*) as n, SUM(round_made) as made
        FROM hands WHERE 1=1 {run_filter}
        GROUP BY bid_tested ORDER BY bid_tested
    """).fetchall()
    conn.close()
    result = {}
    for row in rows:
        n, made = row[1], row[2]
        sr = made / n if n else 0
        result[row[0]] = {
            'n': n, 'made': made,
            'success_pct': round(sr * 100, 2),
            'ev': round(ev(row[0], sr), 2),
        }
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Recommendations
# ─────────────────────────────────────────────────────────────────────────────

def generate_recommendations(stats: Dict[str, Dict[int, dict]]) -> Dict[str, dict]:
    """
    For each category, find the bid with highest positive EV.
    Bid 0 (pass) has EV = 0, so if no bid has positive EV, recommend passing.
    """
    recs = {}
    for cat, bid_data in stats.items():
        best_bid = 0
        best_ev  = 0.0   # pass EV = 0
        options  = {}
        for bid, d in bid_data.items():
            options[bid] = {'success_pct': d['success_pct'], 'ev': d['ev'], 'n': d['n']}
            if d['ev'] > best_ev:
                best_ev  = d['ev']
                best_bid = bid
        recs[cat] = {
            'recommended_bid': best_bid,
            'best_ev':         round(best_ev, 2),
            'options':         options,
        }
    return recs


# ─────────────────────────────────────────────────────────────────────────────
# Console output
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(
    overall: Dict,
    stats: Dict[str, Dict[int, dict]],
    recs:   Dict[str, dict],
    min_samples: int,
    db_path: str,
    json_path: str,
) -> None:
    W = 70
    print()
    print('=' * W)
    print('45s BIDDING SIMULATOR v2 — RESULTS')
    print('=' * W)

    print('\nOverall success rates:')
    for bid in [15, 20, 25, 30]:
        if bid in overall:
            d = overall[bid]
            print(f"  Bid {bid:2d}:  {d['success_pct']:5.1f}%  "
                  f"({d['n']:>10,} samples)   EV: {d['ev']:+.1f}")

    print(f'\nBy hand category  (min {min_samples} samples):')
    print(f"  {'Category':<22} {'Bid':>4} {'N':>8} {'Made%':>7} {'CI':>13} {'EV':>7}  Rec")
    print('  ' + '-' * 65)

    # Sort categories by total sample count descending
    sorted_cats = sorted(
        stats.items(),
        key=lambda kv: sum(d['n'] for d in kv[1].values()),
        reverse=True
    )

    for cat, bid_data in sorted_cats[:30]:
        rec_bid = recs.get(cat, {}).get('recommended_bid', 0)
        for bid in [15, 20, 25, 30]:
            if bid not in bid_data:
                continue
            d   = bid_data[bid]
            rec = '← REC' if bid == rec_bid else ''
            print(f"  {cat:<22} {bid:>4} {d['n']:>8,} {d['success_pct']:>6.1f}%"
                  f"  [{d['ci_lo']:4.1f}–{d['ci_hi']:4.1f}%] {d['ev']:>+7.1f}  {rec}")
        print()

    print(f'\nResults saved to:  {db_path}')
    print(f'Summary saved to:  {json_path}')
    print('=' * W)


# ─────────────────────────────────────────────────────────────────────────────
# JSON output
# ─────────────────────────────────────────────────────────────────────────────

def save_summary_json(
    overall: Dict,
    stats:   Dict,
    recs:    Dict,
    path:    str,
) -> None:
    data = {
        'overall':         overall,
        'by_category':     stats,
        'recommendations': recs,
    }
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Top-level entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_report(
    db_path:     str,
    json_path:   str,
    run_id:      Optional[int] = None,
    min_samples: int = 200,
) -> dict:
    """Generate and print the full report. Returns the summary dict."""
    overall = load_overall_stats(db_path, run_id)
    stats   = load_category_stats(db_path, run_id, min_samples)
    recs    = generate_recommendations(stats)

    print_summary(overall, stats, recs, min_samples, db_path, json_path)
    save_summary_json(overall, stats, recs, json_path)

    return {'overall': overall, 'by_category': stats, 'recommendations': recs}
