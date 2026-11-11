-- WhyBot database schema. Safe to run many times.
CREATE EXTENSION IF NOT EXISTS vector;

-- One row per day x region x platform x channel. The only table the SQL tool may read.
CREATE TABLE IF NOT EXISTS daily_metrics (
    date             date    NOT NULL,
    region           text    NOT NULL,
    platform         text    NOT NULL,
    channel          text    NOT NULL,
    sessions         integer NOT NULL,
    checkout_starts  integer NOT NULL,
    payment_attempts integer NOT NULL,
    payment_failures integer NOT NULL,
    orders           integer NOT NULL,
    revenue          numeric(14, 2) NOT NULL,
    PRIMARY KEY (date, region, platform, channel)
);

-- Evidence: support tickets, GitHub issues, deploy changelog entries.
CREATE TABLE IF NOT EXISTS documents (
    id         text PRIMARY KEY,
    source     text NOT NULL,
    created_at date NOT NULL,
    title      text NOT NULL,
    body       text NOT NULL,
    meta       jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS documents_created_at ON documents (created_at);

-- Documents split into passages, each with a 384-dim embedding (bge-small-en-v1.5).
CREATE TABLE IF NOT EXISTS chunks (
    id        serial PRIMARY KEY,
    doc_id    text NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    idx       integer NOT NULL,
    text      text NOT NULL,
    embedding vector(384) NOT NULL
);

-- One row per question answered by the API.
CREATE TABLE IF NOT EXISTS runs (
    id            text PRIMARY KEY,
    created_at    timestamptz NOT NULL DEFAULT now(),
    question      text NOT NULL,
    question_key  text NOT NULL,          -- normalised question, used to serve cached runs
    system        text NOT NULL,
    status        text NOT NULL,
    report        jsonb,
    error         text,
    is_example    boolean NOT NULL DEFAULT false,
    latency_ms    integer NOT NULL DEFAULT 0,
    input_tokens  integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    cost_usd      numeric(10, 6) NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS runs_question_key ON runs (question_key);

-- One row per agent step (LLM call or tool call) with latency, tokens and cost.
CREATE TABLE IF NOT EXISTS tool_traces (
    run_id     text NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    step_index integer NOT NULL,
    step       jsonb NOT NULL,
    PRIMARY KEY (run_id, step_index)
);

-- Cost protection for the public demo.
CREATE TABLE IF NOT EXISTS spend_daily (
    day date PRIMARY KEY,
    usd numeric(10, 6) NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ask_counts (
    day     date NOT NULL,
    ip_hash text NOT NULL,
    n       integer NOT NULL DEFAULT 0,
    PRIMARY KEY (day, ip_hash)
);

-- The SELECT-only role used by run_metric_query is created by bench/load.py
-- (ensure_readonly_role), with the name and password from DATABASE_URL_READONLY.
