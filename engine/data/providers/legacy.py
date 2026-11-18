"""Legacy migration provider — reads the OLD repo JSON, never the network.

Fixes the audited legacy defects at the contract level:
- rank/region confusion: legacy "region":"iron" is a RANK -> rank_scope, region=ALL
- raw WR lost by old normalization: kept as legacy_derived_score, observed=null
- overall WR is NOT role-specific: role stats win_rate=null + missing_reason
- duplicates: natural-key dedup with logged actions
- test contamination: quarantine list
- expert_insight: exported as rule PROPOSALS (never auto-active)
"""
from __future__ import annotations

import json
from pathlib import Path

from engine.contracts.records import (
    Champion, ChampionRoleStats, Matchup, Synergy, Provenance, Quality, utcnow,
)
from engine.contracts.types import (
    QualityStatus, RelationType, parse_roles, Role,
)
from engine.data.providers.base import Provider, ProviderResult

QUARANTINE_NAMES = {"testchampionpipeline"}
RANK_FROM_LEGACY_REGION = {
    "iron": "IRON_PLUS", "bronze": "BRONZE_PLUS", "silver": "SILVER_PLUS",
    "gold": "GOLD_PLUS", "platinum": "PLATINUM_PLUS", "emerald": "EMERALD_PLUS",
    "diamond": "DIAMOND_PLUS", "master": "MASTER_PLUS",
    "grandmaster": "GRANDMASTER_PLUS", "challenger": "CHALLENGER",
}


class LegacyProvider(Provider):
    name = "legacy_leagueofgraphs"

    def __init__(self, legacy_dir: Path, patch: str = "legacy-unknown"):
        self.legacy_dir = Path(legacy_dir)
        self.patch = patch
        self.champion_registry: dict[str, int] | None = None  # name(lower)->id, set by pipeline

    def _load(self, fname):
        p = self.legacy_dir / fname
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def collect(self, staging: Path, resume: bool = True) -> ProviderResult:
        # res.patch stays None: legacy patch is unknown and must NOT override
        # the source-verified patch from Data Dragon / LoG.
        res = ProviderResult(provider=self.name)
        data = self._load("tum_sampiyonlar_verisi_full.json")
        if data is None:
            res.status = "failed"
            res.errors.append("legacy main JSON not found")
            return res
        id_map = self._load("champion_id_map.json") or {}
        name_to_id = {v.lower(): int(k) for k, v in id_map.items()}
        if self.champion_registry:
            name_to_id.update(self.champion_registry)
        damage = self._load("champion_damage_scores.json") or {}
        dmg_norm = {k.lower().replace(" ", "").replace("'", "").replace(".", ""): v
                    for k, v in damage.items()}

        prov = Provenance(provider=self.name, collected_at=utcnow(),
                          source_url="repo:data/tum_sampiyonlar_verisi_full.json",
                          permission="user_granted_2026-11-18")
        seen_keys: set = set()

        def dedup(kind: str, key, rec: dict):
            if key in seen_keys:
                res.dedup_actions.append({"kind": kind, "key": str(key),
                                          "action": "duplicate_dropped_first_wins"})
                return
            seen_keys.add(key)
            res.add(kind, rec)

        for c in data:
            name = c.get("name", "")
            if name.lower() in QUARANTINE_NAMES:
                res.quarantined.append({"name": name, "reason": "test_record_contamination"})
                continue
            cid = name_to_id.get(name.lower())
            if cid is None:
                res.quarantined.append({"name": name, "reason": "no_champion_id_mapping"})
                continue
            roles = parse_roles(c.get("role"))
            legacy_rank = str(c.get("region", "")).lower()
            rank_scope = RANK_FROM_LEGACY_REGION.get(legacy_rank, "ALL")
            if legacy_rank and legacy_rank not in RANK_FROM_LEGACY_REGION:
                res.warnings.append(f"{name}: unknown legacy rank '{legacy_rank}'")
            if legacy_rank in RANK_FROM_LEGACY_REGION:
                res.warnings.append(
                    f"legacy field misuse: 'region'='{legacy_rank}' is a RANK; "
                    f"normalized to rank_scope={rank_scope}, region=ALL")

            wr = c.get("general_win_rate")
            wr_frac = round(wr / 100.0, 4) if isinstance(wr, (int, float)) and wr > 0 else None
            champ = Champion(
                champion_id=cid, name=name, slug=c.get("slug", name.lower()),
                roles=roles, overall_win_rate=wr_frac,
                overall_win_rate_quality=Quality(
                    status=QualityStatus.LEGACY_UNVERIFIED if wr_frac else QualityStatus.MISSING,
                    missing_reason=None if wr_frac else "legacy_scrape_failed_or_zero",
                    confidence=0.3 if wr_frac else None),
                provenance=prov,
            ).to_dict()
            dn = name.lower().replace(" ", "").replace("'", "").replace(".", "")
            if dn in dmg_norm:
                champ["damage_profile_curated"] = dmg_norm[dn]
            dedup("champions", cid, champ)

            # role stats: legacy WR is OVERALL, never role-specific
            for role in roles:
                rs = ChampionRoleStats(
                    champion_id=cid, role=role, patch=self.patch,
                    rank_scope=rank_scope, region="ALL",
                    win_rate=None, sample_size=None,
                    provenance=prov,
                    quality=Quality(status=QualityStatus.MISSING,
                                    missing_reason="source_reports_overall_only"),
                ).to_dict()
                dedup("champion_role_stats", (cid, role.value, self.patch, rank_scope), rs)

            primary = roles[0] if roles else Role.MIDDLE
            opp_roles = {}
            for other in data:
                oroles = parse_roles(other.get("role"))
                oid = name_to_id.get(other.get("name", "").lower())
                if oid and oroles:
                    opp_roles[other["name"].lower()] = (oid, oroles[0])

            def matchup_records(list_name: str, relation: RelationType, direction: str):
                for item in c.get(list_name, []) or []:
                    ename = item.get("champion", "")
                    entry = opp_roles.get(ename.lower())
                    if not entry:
                        continue
                    oid, orole = entry
                    score = item.get("score")
                    m = Matchup(
                        champion_id=cid, champion_role=primary,
                        opponent_id=oid, opponent_role=orole,
                        relation_type=relation, patch=self.patch,
                        rank_scope=rank_scope, region="ALL",
                        observed_win_rate=None, sample_size=None,
                        legacy_derived_score=float(score) if score is not None else None,
                        provenance=prov,
                        quality=Quality(
                            status=QualityStatus.LEGACY_DERIVED,
                            missing_reason="raw_wr_discarded_by_legacy_normalization",
                            confidence=0.25),
                    ).to_dict()
                    m["legacy_direction"] = direction
                    dedup("matchups", (cid, primary.value, oid, orole.value,
                                       relation.value, direction), m)

            matchup_records("lane_counters", RelationType.SAME_LANE, "ADVANTAGE")
            matchup_records("lane_countered_by", RelationType.SAME_LANE, "DISADVANTAGE")
            matchup_records("general_good_against", RelationType.CROSS_TEAM, "ADVANTAGE")
            matchup_records("general_bad_against", RelationType.CROSS_TEAM, "DISADVANTAGE")

            for item in c.get("synergies", []) or []:
                ename = item.get("champion", "")
                entry = opp_roles.get(ename.lower())
                if not entry:
                    continue
                oid, orole = entry
                s = Synergy(
                    champion_id=cid, champion_role=primary, ally_id=oid, ally_role=orole,
                    patch=self.patch, rank_scope=rank_scope, region="ALL",
                    observed_win_rate=None, sample_size=None,
                    legacy_derived_score=float(item.get("score", 0)),
                    provenance=prov,
                    quality=Quality(status=QualityStatus.LEGACY_DERIVED,
                                    missing_reason="raw_together_wr_not_captured",
                                    confidence=0.25),
                ).to_dict()
                dedup("synergies", (cid, primary.value, oid, orole.value), s)

            # expert_insight -> rule proposals (pending, never active)
            expert = c.get("expert_insight") or {}
            for relation, targets in (("HARD_COUNTERED_BY", expert.get("hard_counters", [])),
                                      ("EASY_MATCHUP_VS", expert.get("easy_matchups", []))):
                for t in targets or []:
                    entry = opp_roles.get(str(t).lower())
                    if not entry:
                        continue
                    oid, orole = entry
                    res.extra.setdefault("rule_proposals", []).append({
                        "rule_type": "empirical", "status": "proposed",
                        "title": f"{name} {relation} {t} (legacy expert_insight)",
                        "subject": {"champion_id": cid, "champion": name, "role": primary.value},
                        "target": {"champion_id": oid, "champion": t, "role": orole.value},
                        "relation": relation, "game_phase": "ALL",
                        "claim": f"Legacy expert insight: {name} {relation} {t}.",
                        "provenance": {"generated_by": "legacy_expert_insight",
                                       "generation_type": "legacy_migration",
                                       "created_at": utcnow()},
                        "scope": {"patch_from": None, "patch_to": None,
                                  "rank": rank_scope, "region": "ALL"},
                    })

        res.coverage = {"champions": len(res.records.get("champions", [])),
                        "matchups": len(res.records.get("matchups", [])),
                        "synergies": len(res.records.get("synergies", []))}
        res.status = "ok"
        return res
