"""Shared fixtures. Tests marked `db` need Postgres with the benchmark loaded
(docker compose up -d db && python -m bench.load). They are skipped if it is not reachable."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from whybot.config import get_settings
from whybot.db import Conn, connect

SECURITY_RESULTS: list[dict] = []


@pytest.fixture(scope="session")
def conn() -> Iterator[Conn]:
    try:
        connection = connect(get_settings().database_url)
        connection.execute("SELECT 1 FROM daily_metrics LIMIT 1")
    except psycopg.Error:
        pytest.skip("Postgres with benchmark data is not available")
    yield connection
    connection.close()


@pytest.fixture(scope="session")
def readonly_conn(conn: Conn) -> Iterator[Conn]:
    connection = connect(get_settings().database_url_readonly)
    yield connection
    connection.close()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "security(owasp): a security test mapped to an OWASP LLM Top 10 item")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Iterator[None]:
    outcome = yield
    report = outcome.get_result()  # type: ignore[attr-defined]
    marker = item.get_closest_marker("security")
    if marker and report.when == "call":
        SECURITY_RESULTS.append({"name": item.name, "owasp": marker.args[0], "passed": report.passed})


def pytest_sessionfinish(session: pytest.Session) -> None:
    """With WRITE_SECURITY_RESULTS=1, save the security test outcomes for the README and the site."""
    if os.environ.get("WRITE_SECURITY_RESULTS") == "1" and SECURITY_RESULTS:
        out = {
            "passed": sum(r["passed"] for r in SECURITY_RESULTS),
            "total": len(SECURITY_RESULTS),
            "tests": sorted(SECURITY_RESULTS, key=lambda r: (r["owasp"], r["name"])),
        }
        path = Path(__file__).resolve().parent.parent / "results" / "security.json"
        path.write_text(json.dumps(out, indent=2) + "\n")
