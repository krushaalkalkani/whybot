"""Postgres access. Plain psycopg, no ORM, so every query is visible."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

SCHEMA_FILE = Path(__file__).parent / "schema.sql"

# A connection whose rows come back as dicts, e.g. row["id"].
Conn = psycopg.Connection[dict[str, Any]]


def connect(url: str) -> Conn:
    """Open a connection. Autocommit keeps each statement independent."""
    return psycopg.connect(url, autocommit=True, row_factory=dict_row)


def apply_schema(conn: Conn) -> None:
    conn.execute(SCHEMA_FILE.read_text())


def vector_literal(values: list[float]) -> str:
    """pgvector accepts '[0.1,0.2,...]' text, so no extra driver package is needed."""
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"
