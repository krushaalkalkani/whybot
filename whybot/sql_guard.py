"""Makes LLM-written SQL safe to run.

The model writes SQL for run_metric_query. We never trust it. Three layers:

  1. This file: parse the SQL into a syntax tree (sqlglot) and allow only one
     SELECT over an allow-list of tables and functions. The SQL that runs is
     re-generated from the tree, so comments and hidden second statements are gone.
  2. The query runs in a READ ONLY transaction with a 3 second timeout.
  3. The connection uses a database role that can only SELECT from daily_metrics.

Checking a parsed tree is safer than searching the text for bad words: a keyword
block-list is easy to bypass ("DR/**/OP") and also blocks harmless strings.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

ALLOWED_TABLES = frozenset({"daily_metrics"})
ALLOWED_COLUMNS = "date, region, platform, channel, sessions, checkout_starts, payment_attempts, payment_failures, orders, revenue"
# Functions sqlglot has no built-in class for arrive as "Anonymous". Allow only these.
ALLOWED_ANONYMOUS_FUNCTIONS = frozenset({"to_char", "date_part", "isodow"})
FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command,
    exp.Into, exp.Merge, exp.Set, exp.Transaction, exp.Commit, exp.Rollback, exp.Copy, exp.Lock,
)  # fmt: skip
MAX_SQL_CHARS = 2000
MAX_ROWS = 200


class SqlRejected(ValueError):
    """Raised with a message that is safe to show to the model."""


def check_sql(sql: str) -> str:
    """Return a safe version of `sql` with a row limit, or raise SqlRejected."""
    if len(sql) > MAX_SQL_CHARS:
        raise SqlRejected(f"Query is too long (max {MAX_SQL_CHARS} characters).")
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except sqlglot.errors.SqlglotError as error:
        raise SqlRejected(f"Could not parse SQL: {str(error)[:200]}") from error
    if len(statements) != 1:
        raise SqlRejected("Exactly one statement is allowed.")
    tree = statements[0]
    if not isinstance(tree, exp.Select | exp.Union):
        raise SqlRejected("Only SELECT statements are allowed.")
    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SqlRejected(f"{type(node).__name__} is not allowed. This tool is read-only.")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if table.db or table.catalog:
            raise SqlRejected("Schema-qualified table names are not allowed.")
        if not name:
            raise SqlRejected("Table functions are not allowed.")
        if name not in ALLOWED_TABLES and name not in cte_names:
            raise SqlRejected(f"Table '{name}' is not allowed. You can only read: daily_metrics.")
    for func in tree.find_all(exp.Anonymous):
        if func.name.lower() not in ALLOWED_ANONYMOUS_FUNCTIONS:
            raise SqlRejected(f"Function '{func.name}' is not allowed.")

    clean = tree.sql(dialect="postgres", comments=False)
    return f"SELECT * FROM ({clean}) AS q LIMIT {MAX_ROWS + 1}"
