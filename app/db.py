"""SQLite access: one connection per thread, numbered SQL migrations, small query helpers.

The SQL is kept close to ANSI so that moving to PostgreSQL later is a driver swap plus
small type changes (see README "Moving to PostgreSQL").
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from . import config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_local = threading.local()
_db_path: Path = config.DATABASE_PATH


def set_path(path: Path) -> None:
    """Point the module at another database file (tests use a temp file)."""
    global _db_path
    close()
    _db_path = Path(path)


def connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is not None and getattr(_local, "path", None) == _db_path:
        return conn
    conn = sqlite3.connect(str(_db_path), timeout=15, isolation_level=None,
                           detect_types=0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 8000")
    _local.conn = conn
    _local.path = _db_path
    return conn


def close() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


def now() -> str:
    """UTC timestamp, ISO 8601, second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def q(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return connect().execute(sql, tuple(params)).fetchall()


def one(sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
    return connect().execute(sql, tuple(params)).fetchone()


def val(sql: str, params: Iterable[Any] = (), default: Any = None) -> Any:
    row = connect().execute(sql, tuple(params)).fetchone()
    return default if row is None or row[0] is None else row[0]


def run(sql: str, params: Iterable[Any] = ()) -> int:
    """Execute a write; returns lastrowid."""
    cur = connect().execute(sql, tuple(params))
    return cur.lastrowid


def insert(table: str, data: dict) -> int:
    cols = ", ".join(data)
    marks = ", ".join("?" for _ in data)
    return run(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(data.values()))


def update(table: str, row_id: int, data: dict, key: str = "id") -> None:
    if not data:
        return
    sets = ", ".join(f"{k} = ?" for k in data)
    run(f"UPDATE {table} SET {sets} WHERE {key} = ?", [*data.values(), row_id])


class transaction:
    """`with db.transaction():` — BEGIN IMMEDIATE / COMMIT / ROLLBACK."""

    def __enter__(self):
        self.conn = connect()
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.execute("COMMIT")
        else:
            self.conn.execute("ROLLBACK")
        return False


def loads(text: Optional[str], default: Any = None) -> Any:
    if not text:
        return {} if default is None else default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return {} if default is None else default


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def migrate() -> list[str]:
    """Apply every migrations/NNN_*.sql file not yet recorded. Returns names applied."""
    conn = connect()
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if f.name in done:
            continue
        conn.executescript("BEGIN;\n" + f.read_text(encoding="utf-8") + "\nCOMMIT;")
        conn.execute("INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)", (f.name, now()))
        applied.append(f.name)
    return applied
