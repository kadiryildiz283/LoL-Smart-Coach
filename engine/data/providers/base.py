"""Provider protocol. Site-specific parsing stays INSIDE each provider;
the pipeline only sees normalized, schema-valid records."""
from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


class ProviderDisabled(RuntimeError):
    pass


@dataclass
class ProviderResult:
    provider: str
    status: str = "ok"  # ok | partial | failed | disabled | missing_credentials
    patch: str | None = None
    records: dict[str, list] = field(default_factory=dict)  # kind -> [record dicts]
    extra: dict = field(default_factory=dict)               # e.g. rule_proposals, raw refs
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dedup_actions: list[dict] = field(default_factory=list)
    quarantined: list[dict] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)
    fetched: int = 0
    cached: int = 0

    def add(self, kind: str, record: dict) -> None:
        self.records.setdefault(kind, []).append(record)


class Provider(ABC):
    name: str = "base"

    @abstractmethod
    def collect(self, staging: Path, resume: bool = True) -> ProviderResult:
        ...


def raw_cache_path(staging: Path, url: str) -> Path:
    return staging / (hashlib.sha1(url.encode()).hexdigest() + ".json")


def cache_get(staging: Path, url: str) -> dict | None:
    p = raw_cache_path(staging, url)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def cache_put(staging: Path, url: str, body) -> None:
    p = raw_cache_path(staging, url)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"url": url, "fetched_at": time.time(), "body": body},
                              ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)
