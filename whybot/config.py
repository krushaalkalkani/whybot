"""Settings. Everything comes from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path = REPO_ROOT / ".env") -> None:
    """Tiny .env reader so local runs need no extra dependency. Real env vars win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class RetrievalConfig:
    """Switches for the retrieval pipeline. The ablations flip these."""

    use_bm25: bool = True
    use_dense: bool = True
    use_rerank: bool = True
    candidates: int = 30  # how many results each of BM25 and dense search returns
    rerank_top: int = 20  # how many fused results the cross-encoder scores


@dataclass(frozen=True)
class AgentConfig:
    """Switches and limits for the agent loop."""

    use_verifier: bool = True
    max_tool_calls: int = 8
    timeout_s: float = 90.0
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)


@dataclass(frozen=True)
class Settings:
    database_url: str
    database_url_readonly: str  # used only by run_metric_query; falls back to database_url
    agent_model: str
    judge_model: str
    agent_effort: str
    has_llm_key: bool
    daily_spend_cap_usd: float
    daily_questions_per_ip: int
    ip_hash_salt: str
    cors_origins: list[str]
    models_dir: Path
    llm_cache_dir: Path | None


def get_settings() -> Settings:
    load_dotenv()
    env = os.environ
    database_url = env.get("DATABASE_URL", "postgresql://whybot:whybot@localhost:54329/whybot")
    cache_dir = env.get("LLM_CACHE_DIR", "")
    return Settings(
        database_url=database_url,
        database_url_readonly=env.get("DATABASE_URL_READONLY") or database_url,
        agent_model=env.get("WHYBOT_AGENT_MODEL", "claude-haiku-5-5"),
        judge_model=env.get("WHYBOT_JUDGE_MODEL", "claude-sonnet-5-5"),
        agent_effort=env.get("WHYBOT_AGENT_EFFORT", "medium"),
        has_llm_key=bool(env.get("ANTHROPIC_API_KEY")),
        daily_spend_cap_usd=float(env.get("WHYBOT_DAILY_SPEND_CAP_USD", "1.0")),
        daily_questions_per_ip=int(env.get("WHYBOT_DAILY_QUESTIONS_PER_IP", "5")),
        ip_hash_salt=env.get("WHYBOT_IP_HASH_SALT", "change-me"),
        cors_origins=[o.strip() for o in env.get("WHYBOT_CORS_ORIGINS", "*").split(",") if o.strip()],
        models_dir=Path(env.get("WHYBOT_MODELS_DIR", str(REPO_ROOT / "models"))),
        llm_cache_dir=Path(cache_dir) if cache_dir else None,
    )
