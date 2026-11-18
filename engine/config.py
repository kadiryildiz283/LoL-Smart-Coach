"""Central configuration. Secrets come from environment variables only."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class LoGConfig:
    enabled: bool = True
    permission: str = "user_granted_2026-11-18"  # project owner authorization, see kutsal_amac.md §3 amendment
    base_url: str = "https://www.leagueofgraphs.com"
    rank_slug: str = "emerald"   # LoG rank filter slug (verified live 2026-11-18; emerald_plus 404)
    region: str = "ALL"               # LoG aggregates regions; kept separate from rank
    request_delay_s: float = 1.2
    cooldown_429_s: float = 60.0
    cooldown_403_s: float = 15.0
    max_retries: int = 3
    timeout_s: float = 20.0
    max_vs_pages_per_champion: int = 0  # 0 = unlimited (brute force full coverage)
    impersonate: str = "chrome120"
    offline: bool = False  # parse raw cache only, zero network (intermediate publish)


@dataclass
class RiotConfig:
    api_key: str | None = field(default_factory=lambda: os.environ.get("RIOT_API_KEY"))
    platform: str = "euw1"
    regional: str = "europe"
    matches_per_run: int = 100
    request_delay_s: float = 1.3  # conservative vs dev-key limits (20/s, 100/2min)

    @property
    def available(self) -> bool:
        return bool(self.api_key)


@dataclass
class DataDragonConfig:
    base_url: str = "https://ddragon.leagueoflegends.com"
    patch: str | None = None  # None = latest verified from versions.json
    workers: int = 6
    request_delay_s: float = 0.15


@dataclass
class LLMConfig:
    host: str = "172.16.10.142"
    model: str = "qwen3.8:27b"
    # Verified 2026-11-18: vLLM OpenAI-compatible at :8000, Ollama at :11434, both serve qwen3.8:27b
    openai_port: int = 8000
    ollama_port: int = 11434
    prefer: str = "openai"  # "openai" | "ollama"
    timeout_s: float = 60.0
    max_retries: int = 2
    context_budget_chars: int = 12000
    allow_model_substitution: bool = False  # never silently use a different model


@dataclass
class EngineConfig:
    mc_samples: int = 256
    seed: int = 42
    time_budget_s: float = 2.0
    beam_candidates: int = 12
    risk_aversion: float = 0.0  # 0 = pure expected value; >0 penalizes downside (CVaR weight)
    cvar_alpha: float = 0.2     # downside = mean of worst 20% outcomes
    future_counter_temperature: float = 1.0  # >1 flattens opponent counter-response (not perfect counters)
    shrinkage_strength: float = 30.0  # pseudo-count toward role prior
    rank_scope: str = "EMERALD_PLUS"
    queue: str = "RANKED_SOLO"


@dataclass
class Config:
    datasets_dir: Path = REPO_ROOT / "datasets"
    game_rules_dir: Path = REPO_ROOT / "game_rules"
    legacy_data_dir: Path = REPO_ROOT / "data"
    log: LoGConfig = field(default_factory=LoGConfig)
    riot: RiotConfig = field(default_factory=RiotConfig)
    ddragon: DataDragonConfig = field(default_factory=DataDragonConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)


DEFAULT_CONFIG = Config()
