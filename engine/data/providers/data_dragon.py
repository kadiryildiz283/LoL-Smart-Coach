"""Official Riot Data Dragon provider — static game data, no API key required.

Source of truth for champion IDs, names, tags, base stats (incl. attack range),
spells and passive. Patch is verified from versions.json (never assumed).
"""
from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from engine.config import DataDragonConfig
from engine.contracts.records import Champion, Provenance, Quality, utcnow
from engine.contracts.types import QualityStatus
from engine.data.providers.base import (
    Provider, ProviderResult, cache_get, cache_put, raw_cache_path,
)


def _get_json(url: str, timeout: float = 30.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class DataDragonProvider(Provider):
    name = "data_dragon"

    def __init__(self, cfg: DataDragonConfig):
        self.cfg = cfg

    def _fetch_cached(self, staging: Path, url: str, resume: bool):
        if resume:
            cached = cache_get(staging, url)
            if cached is not None:
                return cached["body"], True
        body = _get_json(url)
        cache_put(staging, url, body)
        time.sleep(self.cfg.request_delay_s)
        return body, False

    def collect(self, staging: Path, resume: bool = True) -> ProviderResult:
        res = ProviderResult(provider=self.name)
        versions, cached = self._fetch_cached(staging, f"{self.cfg.base_url}/api/versions.json", resume)
        res.cached += int(cached)
        res.fetched += int(not cached)
        patch = self.cfg.patch or versions[0]
        res.patch = patch

        summary_url = f"{self.cfg.base_url}/cdn/{patch}/data/en_US/champion.json"
        summary, cached = self._fetch_cached(staging, summary_url, resume)
        res.cached += int(cached); res.fetched += int(not cached)
        entries = summary["data"]  # key -> {id, key(numeric), name, tags, partype}

        full_urls = {key: f"{self.cfg.base_url}/cdn/{patch}/data/en_US/champion/{key}.json"
                     for key in entries}

        def fetch_one(item):
            key, url = item
            try:
                body, cached = self._fetch_cached(staging, url, resume)
                return key, body, cached, None
            except Exception as e:
                return key, None, False, f"{key}: {type(e).__name__}: {e}"

        with ThreadPoolExecutor(max_workers=self.cfg.workers) as ex:
            results = list(ex.map(fetch_one, full_urls.items()))

        provenance = Provenance(provider=self.name, source_url=summary_url,
                                collected_at=utcnow())
        for key, body, cached, err in results:
            res.cached += int(cached); res.fetched += int(not cached)
            if err:
                res.errors.append(err)
                continue
            champ = body["data"][key]
            cid = int(champ["key"])
            record = Champion(
                champion_id=cid, name=champ["name"], slug=champ["id"].lower(),
                tags=champ.get("tags", []),
                provenance=Provenance(provider=self.name,
                                      source_url=full_urls[key], collected_at=utcnow()),
            ).to_dict()
            record["base_stats"] = champ.get("stats", {})
            record["partype"] = champ.get("partype")
            res.add("champions", record)

        # static reference data for knowledge engine (items, runes, summoner spells)
        for fname, url in [
            ("item.json", f"{self.cfg.base_url}/cdn/{patch}/data/en_US/item.json"),
            ("runesReforged.json", f"{self.cfg.base_url}/cdn/{patch}/data/en_US/runesReforged.json"),
        ]:
            try:
                body, cached = self._fetch_cached(staging, url, resume)
                res.cached += int(cached); res.fetched += int(not cached)
                res.extra.setdefault("static_files", {})[fname] = str(raw_cache_path(staging, url))
            except Exception as e:
                res.warnings.append(f"static {fname} failed: {e}")

        res.coverage = {"champions": len(res.records.get("champions", [])),
                        "patch": patch}
        res.status = "ok" if not res.errors else "partial"
        return res
