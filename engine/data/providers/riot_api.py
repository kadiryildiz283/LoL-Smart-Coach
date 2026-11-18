"""Riot official API provider — Match-v5 derived statistics.

Credentials: RIOT_API_KEY environment variable ONLY (never hardcoded).
Without a key the provider reports missing_credentials and the pipeline
records it as an external dependency; everything else keeps working.

With a key: challenger league -> summoner PUUIDs -> match-v5 ids -> match
details -> per (champion, teamPosition) win aggregation with REAL sample
sizes. This is the path to match-level training data for calibration.
"""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from collections import defaultdict
from pathlib import Path

from engine.config import RiotConfig
from engine.contracts.records import ChampionRoleStats, Provenance, Quality, utcnow
from engine.contracts.types import QualityStatus, Role
from engine.data.providers.base import Provider, ProviderResult, cache_get, cache_put

POSITION_TO_ROLE = {"TOP": Role.TOP, "JUNGLE": Role.JUNGLE, "MIDDLE": Role.MIDDLE,
                    "BOTTOM": Role.BOTTOM, "UTILITY": Role.UTILITY}


class RiotApiProvider(Provider):
    name = "riot_derived"

    def __init__(self, cfg: RiotConfig):
        self.cfg = cfg

    def _get(self, url: str, staging: Path, resume: bool, res: ProviderResult):
        if resume:
            cached = cache_get(staging, url)
            if cached is not None:
                res.cached += 1
                return cached["body"]
        req = urllib.request.Request(url, headers={"X-Riot-Token": self.cfg.api_key or ""})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                body = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(e.headers.get("Retry-After", 5)))
                return self._get(url, staging, False, res)
            raise
        cache_put(staging, url, body)
        res.fetched += 1
        time.sleep(self.cfg.request_delay_s)
        return body

    def collect(self, staging: Path, resume: bool = True) -> ProviderResult:
        res = ProviderResult(provider=self.name)
        if not self.cfg.available:
            res.status = "missing_credentials"
            res.errors.append("RIOT_API_KEY not set — external dependency; "
                              "match-level calibration data unavailable")
            return res
        try:
            base_p = f"https://{self.cfg.platform}.api.riotgames.com"
            base_r = f"https://{self.cfg.regional}.api.riotgames.com"
            leagues = self._get(f"{base_p}/lol/league/v4/challengerleagues/by-queue/RANKED_SOLO_5x5",
                                staging, resume, res)
            entries = sorted(leagues.get("entries", []),
                             key=lambda e: e.get("leaguePoints", 0), reverse=True)
            match_ids: list[str] = []
            for entry in entries[:20]:
                sid = entry.get("summonerId")
                if not sid:
                    continue
                summ = self._get(f"{base_p}/lol/summoner/v4/summoners/{sid}", staging, resume, res)
                puuid = summ.get("puuid")
                if not puuid:
                    continue
                ids = self._get(f"{base_r}/lol/match/v5/matches/by-puuid/{puuid}/ids?count=10",
                                staging, resume, res)
                for mid in ids:
                    if mid not in match_ids:
                        match_ids.append(mid)
                    if len(match_ids) >= self.cfg.matches_per_run:
                        break
                if len(match_ids) >= self.cfg.matches_per_run:
                    break

            agg: dict[tuple[int, str], dict] = defaultdict(lambda: {"wins": 0, "games": 0})
            patch = None
            for mid in match_ids:
                match = self._get(f"{base_r}/lol/match/v5/matches/{mid}", staging, resume, res)
                info = match.get("info", {})
                patch = ".".join(str(info.get("gameVersion", "")).split(".")[:2]) or patch
                for p in info.get("participants", []):
                    pos = p.get("teamPosition") or ""
                    role = POSITION_TO_ROLE.get(pos)
                    if not role:
                        continue
                    key = (int(p["championId"]), role.value)
                    agg[key]["games"] += 1
                    agg[key]["wins"] += int(bool(p.get("win")))

            prov = Provenance(provider=self.name, collected_at=utcnow(),
                              source_url=f"{base_r}/lol/match/v5", permission="riot_api_key")
            for (cid, role), a in agg.items():
                rs = ChampionRoleStats(
                    champion_id=cid, role=Role(role), patch=patch or "unknown",
                    rank_scope="CHALLENGER", region=self.cfg.regional.upper(),
                    win_rate=round(a["wins"] / a["games"], 5) if a["games"] else None,
                    sample_size=a["games"], provenance=prov,
                    quality=Quality(status=QualityStatus.OBSERVED,
                                    confidence=min(0.9, a["games"] / (a["games"] + 50))),
                ).to_dict()
                rs["metric_scope"] = "ROLE_SPECIFIC"
                res.add("champion_role_stats", rs)
            res.patch = patch
            res.coverage = {"matches": len(match_ids), "champion_roles": len(agg)}
            res.status = "ok"
        except Exception as e:
            res.status = "failed"
            res.errors.append(f"{type(e).__name__}: {e}")
        return res
