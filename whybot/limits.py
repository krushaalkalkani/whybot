"""Cost and abuse protection for the public demo. All state lives in Postgres.

  - Each visitor (hashed IP) gets a few live questions per day.
  - A global daily spend cap: when today's LLM cost reaches it, live questions are
    refused and the site stays in cached mode until the next UTC day.

The check happens before a run and the cost is added after it, so one run can overshoot
the cap by its own cost (well under one cent here). That is an accepted trade-off.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from whybot.config import Settings
from whybot.db import Conn


@dataclass
class LimitStatus:
    live_enabled: bool
    remaining_today: int
    daily_limit: int
    cap_reached: bool
    reason: str | None
    code: str | None = None  # error code for /ask: no_llm | spend_cap | rate_limited


def hash_ip(ip: str, salt: str) -> str:
    """We never store raw IP addresses, only a salted hash."""
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:32]


def spent_today(conn: Conn) -> float:
    row = conn.execute("SELECT usd FROM spend_daily WHERE day = CURRENT_DATE").fetchone()
    return float(row["usd"]) if row else 0.0


def status(conn: Conn, settings: Settings, ip_hash: str) -> LimitStatus:
    limit = settings.daily_questions_per_ip
    row = conn.execute(
        "SELECT n FROM ask_counts WHERE day = CURRENT_DATE AND ip_hash = %s", (ip_hash,)
    ).fetchone()
    remaining = max(0, limit - (row["n"] if row else 0))
    cap_reached = spent_today(conn) >= settings.daily_spend_cap_usd
    if not settings.has_llm_key:
        return LimitStatus(
            False,
            remaining,
            limit,
            cap_reached,
            "Live questions are off: the server has no API key. Examples still work.",
            "no_llm",
        )
    if cap_reached:
        return LimitStatus(
            False,
            remaining,
            limit,
            True,
            "Today's demo budget is used up. Examples still work. Live questions return tomorrow (UTC).",
            "spend_cap",
        )
    if remaining == 0:
        return LimitStatus(
            False,
            0,
            limit,
            False,
            f"You have used your {limit} live questions for today. Examples still work.",
            "rate_limited",
        )
    return LimitStatus(True, remaining, limit, False, None)


def count_question(conn: Conn, ip_hash: str) -> None:
    conn.execute(
        "INSERT INTO ask_counts (day, ip_hash, n) VALUES (CURRENT_DATE, %s, 1) "
        "ON CONFLICT (day, ip_hash) DO UPDATE SET n = ask_counts.n + 1",
        (ip_hash,),
    )


def add_spend(conn: Conn, usd: float) -> None:
    conn.execute(
        "INSERT INTO spend_daily (day, usd) VALUES (CURRENT_DATE, %s) "
        "ON CONFLICT (day) DO UPDATE SET usd = spend_daily.usd + EXCLUDED.usd",
        (usd,),
    )
