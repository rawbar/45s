"""
db.py — SQLite database layer

Schema init, run tracking, and batch inserts.
All writes happen in the main process (SQLite is not safe for concurrent writes).
Workers return result dicts; main process inserts in batches of BATCH_SIZE rows.
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

BATCH_SIZE = 10_000   # rows per transaction — ~50× faster than row-by-row


def open_db(path: str) -> sqlite3.Connection:
    """Open (or create) the SQLite database and initialise schema."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")   # faster concurrent reads
    conn.execute("PRAGMA synchronous=NORMAL") # safe + fast
    _create_schema(conn)
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sim_runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at  TEXT    NOT NULL,
            finished_at TEXT,
            version     TEXT    NOT NULL,
            num_rounds  INTEGER NOT NULL,
            ai_type     TEXT    NOT NULL,
            config_json TEXT
        );

        CREATE TABLE IF NOT EXISTS hands (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id           INTEGER NOT NULL REFERENCES sim_runs(id),

            -- trump features
            trump_suit       TEXT    NOT NULL,
            trump_count      INTEGER NOT NULL,
            has_5            INTEGER NOT NULL,
            has_j            INTEGER NOT NULL,
            has_ah           INTEGER NOT NULL,
            has_at           INTEGER NOT NULL,
            has_k            INTEGER NOT NULL,
            has_q            INTEGER NOT NULL,
            high_trump_count INTEGER NOT NULL,
            top_sequence     INTEGER NOT NULL,

            -- off-suit features
            offsuit_aces     INTEGER NOT NULL,
            offsuit_kings    INTEGER NOT NULL,
            void_count       INTEGER NOT NULL,

            -- what was tested
            bid_tested       INTEGER NOT NULL,

            -- outcome
            round_made       INTEGER NOT NULL,
            tricks_won       INTEGER NOT NULL,
            points_scored    INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_hands_run
            ON hands(run_id);
        CREATE INDEX IF NOT EXISTS idx_hands_bid
            ON hands(bid_tested);
        CREATE INDEX IF NOT EXISTS idx_hands_trump
            ON hands(has_5, has_j, has_ah, trump_count);
        CREATE INDEX IF NOT EXISTS idx_hands_top_seq
            ON hands(top_sequence, trump_count);
        CREATE INDEX IF NOT EXISTS idx_hands_offsuit
            ON hands(offsuit_aces, void_count);
    """)
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Run lifecycle
# ─────────────────────────────────────────────────────────────────────────────

def create_run(
    conn: sqlite3.Connection,
    version: str,
    num_rounds: int,
    ai_type: str,
    config: dict
) -> int:
    """Insert a new sim_run row and return its id."""
    cur = conn.execute(
        "INSERT INTO sim_runs (started_at, version, num_rounds, ai_type, config_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(),
            version,
            num_rounds,
            ai_type,
            json.dumps(config),
        )
    )
    conn.commit()
    return cur.lastrowid


def finish_run(conn: sqlite3.Connection, run_id: int) -> None:
    """Stamp finished_at on the run row."""
    conn.execute(
        "UPDATE sim_runs SET finished_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), run_id)
    )
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Batch insert
# ─────────────────────────────────────────────────────────────────────────────

_INSERT_SQL = """
    INSERT INTO hands (
        run_id,
        trump_suit, trump_count,
        has_5, has_j, has_ah, has_at, has_k, has_q,
        high_trump_count, top_sequence,
        offsuit_aces, offsuit_kings, void_count,
        bid_tested,
        round_made, tricks_won, points_scored
    ) VALUES (
        :run_id,
        :trump_suit, :trump_count,
        :has_5, :has_j, :has_ah, :has_at, :has_k, :has_q,
        :high_trump_count, :top_sequence,
        :offsuit_aces, :offsuit_kings, :void_count,
        :bid_tested,
        :round_made, :tricks_won, :points_scored
    )
"""


def batch_insert(conn: sqlite3.Connection, rows: List[Dict[str, Any]]) -> None:
    """Insert a list of result-row dicts in a single transaction."""
    if not rows:
        return
    conn.executemany(_INSERT_SQL, rows)
    conn.commit()


class BatchBuffer:
    """
    Accumulates result rows and flushes to SQLite when BATCH_SIZE is reached.
    Usage: call add() for each row, call flush() at end.
    """
    def __init__(self, conn: sqlite3.Connection):
        self.conn  = conn
        self._buf: List[Dict[str, Any]] = []
        self.total_inserted = 0

    def add(self, row: Dict[str, Any]) -> None:
        self._buf.append(row)
        if len(self._buf) >= BATCH_SIZE:
            self.flush()

    def add_many(self, rows: List[Dict[str, Any]]) -> None:
        self._buf.extend(rows)
        if len(self._buf) >= BATCH_SIZE:
            self.flush()

    def flush(self) -> None:
        if self._buf:
            batch_insert(self.conn, self._buf)
            self.total_inserted += len(self._buf)
            self._buf.clear()
