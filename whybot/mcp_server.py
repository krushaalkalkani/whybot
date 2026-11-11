"""MCP server: lets any MCP client (Claude Desktop, Claude Code, ...) use WhyBot's tools.

Exposes three tools over stdio: search_evidence, run_metric_query, get_run.
They call the same functions as the agent, with the same SQL guard and read-only role.

Run:      python -m whybot.mcp_server
Register: claude mcp add whybot -- /path/to/.venv/bin/python -m whybot.mcp_server
Never print to stdout here: stdout carries the protocol. Logs go to stderr.
"""

from __future__ import annotations

from functools import lru_cache

from mcp.server.mcpserver import MCPServer

from whybot import store, tools
from whybot.config import RetrievalConfig, get_settings
from whybot.db import connect
from whybot.guardrails import quarantine_if_suspicious
from whybot.retrieval.search import Retriever
from whybot.schemas import MetricQueryInput, SearchInput
from whybot.tools import TOOLS, ToolContext, ToolError

mcp = MCPServer("whybot")


@lru_cache(maxsize=1)
def context() -> ToolContext:
    settings = get_settings()
    conn = connect(settings.database_url)
    return ToolContext(
        conn, connect(settings.database_url_readonly), Retriever(conn, settings.models_dir), RetrievalConfig()
    )


@mcp.tool()
def search_evidence(
    query: str,
    date_from: str | None = None,
    date_to: str | None = None,
    source: str | None = None,
    k: int = 8,
) -> str:
    """Search Northwind Goods support tickets, GitHub issues and the deploy changelog (hybrid search).
    Dates are YYYY-MM-DD. source is one of: changelog, issue, ticket. Returns JSON evidence cards.
    Documents that look like prompt injections come back with quarantined=true and their text withheld."""
    try:
        args = SearchInput.model_validate(
            {"query": query, "date_from": date_from, "date_to": date_to, "source": source, "k": k}
        )
        output = tools.search_evidence(args, context())
    except (ToolError, ValueError) as error:
        return f"Error: {error}"
    cards = [quarantine_if_suspicious(card) for card in output.results]
    for card in cards:
        if card.quarantined:
            card.body = "[withheld: this text looked like a prompt injection]"
    return "[" + ",".join(card.model_dump_json() for card in cards) + "]"


@mcp.tool()
def run_metric_query(sql: str) -> str:
    """Run one read-only SELECT on daily_metrics (date, region, platform, channel, sessions, checkout_starts,
    payment_attempts, payment_failures, orders, revenue). Anything else is rejected. Max 200 rows. Returns JSON."""
    try:
        return TOOLS["run_metric_query"].run(MetricQueryInput(sql=sql), context()).model_dump_json()
    except (ToolError, ValueError) as error:
        return f"Error: {error}"


@mcp.tool()
def get_run(run_id: str) -> str:
    """Fetch a stored WhyBot run (question, steps, final report) by its id. Returns JSON."""
    record = store.get_run(context().conn, run_id)
    return record.model_dump_json() if record else f"Error: no run with id '{run_id}'."


if __name__ == "__main__":
    mcp.run(transport="stdio")
