"""Ingestion pipeline (kutsal_amac.md §5):

Acquisition -> Raw Staging -> Parsing -> Normalization -> Validation ->
Deduplication -> Quality Assessment -> Versioned Publish

Guarantees:
- resume: content-addressed raw cache per provider+patch+scope
- invalid results NEVER replace the last good dataset
- failed provider segments are carried forward from previous dataset (flagged)
- natural-key dedup with visible actions; conflicts are reported, not merged silently
- idempotent: same inputs -> same dataset content (dataset_id includes content hash)
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from engine.config import Config
from engine.contracts.schema import validate_record, SchemaError
from engine.data.store import DatasetStore
from engine.data.providers.base import Provider, ProviderResult, ProviderDisabled
from engine.data.providers._browser import ChallengeBlocked

KIND_FILE = {
    "champions": "champions.json",
    "champion_role_stats": "champion_role_stats.json",
    "matchups": "matchups.json",
    "synergies": "synergies.json",
    "builds": "builds.json",
    "champion_mechanics": "champion_mechanics.json",
}
VALIDATED_KINDS = {"champion_role_stats": "champion_role_stats",
                   "matchups": "matchup", "synergies": "synergy"}


class IngestionPipeline:
    def __init__(self, config: Config, store: DatasetStore, providers: list[Provider]):
        self.config = config
        self.store = store
        self.providers = providers

    def run(self, resume: bool = True) -> dict:
        run_id = time.strftime("run-%Y%m%d-%H%M%S")
        report = {
            "schema_version": "1.0", "run_id": run_id,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
            "finished_at": None, "providers": [], "dedup_actions": [],
            "conflicts": [], "quarantined": [], "carried_forward": [],
            "errors": [], "coverage": {}, "published_dataset_id": None,
        }
        previous = self.store.latest()
        merged: dict[str, dict] = {k: {} for k in KIND_FILE}  # kind -> natural_key -> record
        sources: list[dict] = []
        warnings: list[str] = []
        missing_segments: list[str] = []
        patch = self.config.ddragon.patch or (previous.manifest.get("patch") if previous else "unknown")
        rule_proposals: list[dict] = []
        dd_staging_used: Path | None = None

        for provider in self.providers:
            key = f"{provider.name}-{patch}-{self.config.engine.rank_scope}"
            staging = self.store.staging_dir(key)
            if provider.name == "data_dragon":
                dd_staging_used = staging
            pres = ProviderResult(provider=provider.name)
            try:
                pres = provider.collect(staging, resume=resume)
            except ProviderDisabled as e:
                pres.status = "disabled"
                pres.errors.append(str(e))
            except ChallengeBlocked as e:
                pres.status = "blocked"
                pres.errors.append(f"access blocked: {e}")
            except Exception as e:
                pres.status = "failed"
                pres.errors.append(f"{type(e).__name__}: {e}")

            if pres.patch:
                patch = pres.patch
            # LoG overall WR -> champions.json (observed, sample-backed)
            for cid_str, owr in pres.extra.get("overall_wr", {}).items():
                cid = int(cid_str)
                target = merged["champions"].get(cid)
                if target is not None and owr.get("win_rate") is not None:
                    target["overall_win_rate"] = owr["win_rate"]
                    target["overall_win_rate_quality"] = {
                        "status": "observed", "missing_reason": None,
                        "confidence": 0.7 if owr.get("sample_size") else 0.4,
                        "fallback_of": None}
                    target["overall_sample_size"] = owr.get("sample_size")
                    target["overall_pick_rate"] = owr.get("pick_rate")
                    target["overall_ban_rate"] = owr.get("ban_rate")
                    target["overall_rank_scope"] = owr.get("rank_scope")
            report["providers"].append({
                "provider": pres.provider, "status": pres.status,
                "fetched": pres.fetched, "cached": pres.cached,
                "records": {k: len(v) for k, v in pres.records.items()},
                "errors": pres.errors, "warnings": pres.warnings,
                "coverage": pres.coverage,
            })
            report["dedup_actions"].extend(pres.dedup_actions)
            report["quarantined"].extend(pres.quarantined)
            warnings.extend(pres.warnings)
            rule_proposals.extend(pres.extra.get("rule_proposals", []))
            sources.append({"provider": pres.provider, "status": pres.status,
                            "permission": getattr(getattr(provider, "cfg", None), "permission", None)})

            if pres.status in ("failed", "blocked", "disabled", "missing_credentials"):
                missing_segments.append(pres.provider)
                # carry forward previous good records for this provider's kinds
                if previous is not None:
                    for kind in KIND_FILE:
                        prev_records = self._previous_records(previous, kind)
                        carried = [r for r in prev_records
                                   if r.get("provenance", {}).get("provider") == pres.provider]
                        for r in carried:
                            nk = self._natural_key(kind, r)
                            if nk not in merged[kind]:
                                merged[kind][nk] = r
                    report["carried_forward"].append(pres.provider)
                continue

            for kind, records in pres.records.items():
                if kind not in KIND_FILE:
                    continue
                for rec in records:
                    # Validation BEFORE dedup (spec §5 stage order): invalid records
                    # are quarantined even when a valid duplicate exists.
                    if kind in VALIDATED_KINDS:
                        try:
                            validate_record(VALIDATED_KINDS[kind], rec)
                        except SchemaError as e:
                            report["quarantined"].append(
                                {"kind": kind, "key": str(self._natural_key(kind, rec)),
                                 "reason": str(e), "provider": pres.provider})
                            continue
                    nk = self._natural_key(kind, rec)
                    if nk in merged[kind]:
                        existing = merged[kind][nk]
                        if kind == "champions":
                            merged[kind][nk] = self._merge_champion(existing, rec)
                            continue
                        if json.dumps(existing, sort_keys=True) != json.dumps(rec, sort_keys=True):
                            report["conflicts"].append({
                                "kind": kind, "key": list(nk) if isinstance(nk, tuple) else str(nk),
                                "kept_provider": existing.get("provenance", {}).get("provider"),
                                "dropped_provider": rec.get("provenance", {}).get("provider"),
                                "rule": "first_valid_wins_conflict_logged",
                            })
                        continue
                    merged[kind][nk] = rec

            # wire accumulated champion registry into downstream providers
            if merged["champions"]:
                registry = {r["name"].lower(): cid for cid, r in merged["champions"].items()}
                from engine.contracts.types import Role as _Role
                champ_list = [{"id": cid, "name": r["name"], "slug": r.get("slug", ""),
                               "roles": [_Role(x) if isinstance(x, str) else x
                                         for x in r.get("roles", [])]}
                              for cid, r in merged["champions"].items()]
                for downstream in self.providers:
                    if hasattr(downstream, "champion_registry"):
                        downstream.champion_registry = registry
                    if hasattr(downstream, "set_champions"):
                        downstream.set_champions(champ_list)

        # ---- validation gate ----
        validation_errors: list[str] = []
        for kind, schema_kind in VALIDATED_KINDS.items():
            for nk, rec in list(merged[kind].items()):
                try:
                    validate_record(schema_kind, rec)
                except SchemaError as e:
                    validation_errors.append(f"{kind}:{nk}: {e}")
                    report["quarantined"].append({"kind": kind, "key": str(nk), "reason": str(e)})
                    del merged[kind][nk]

        # ---- coverage & quality ----
        coverage = {
            "champions": len(merged["champions"]),
            "champion_roles": len(merged["champion_role_stats"]),
            "matchups": len(merged["matchups"]),
            "synergies": len(merged["synergies"]),
            "builds": len(merged["builds"]),
            "mechanics": len(merged["champion_mechanics"]),
        }
        report["coverage"] = coverage
        if coverage["champions"] == 0:
            report["errors"].append("no champion records; refusing to publish")
            report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
            return report
        if validation_errors:
            warnings.append(f"{len(validation_errors)} records quarantined at validation gate")

        # ---- mechanics derivation (from Data Dragon raw, if available) ----
        from engine.knowledge.mechanics import derive_mechanics_for_dataset
        dd_raw = dd_staging_used or self.store.staging_dir(
            f"data_dragon-{patch}-{self.config.engine.rank_scope}")
        merged["champion_mechanics"] = derive_mechanics_for_dataset(
            merged["champions"], dd_raw, patch,
            legacy_dir=self.config.legacy_data_dir)
        coverage["mechanics"] = len(merged["champion_mechanics"])

        # ---- deterministic dataset id (content-addressed, values included) ----
        files = {}
        for kind, fname in KIND_FILE.items():
            recs = list(merged[kind].values())
            if kind in ("champions", "champion_mechanics"):
                files[fname] = {str(r["champion_id"]): r for r in recs}
            else:
                files[fname] = sorted(recs, key=lambda r: json.dumps(r, sort_keys=True))
        content_hash = hashlib.sha1(json.dumps(files, sort_keys=True,
                                               ensure_ascii=False).encode()).hexdigest()[:10]
        dataset_id = f"ds-{time.strftime('%Y%m%d')}-{patch}-{content_hash}"

        # idempotent: identical content already published -> no-op success
        if (self.store.root / dataset_id / "dataset_manifest.json").exists():
            report["published_dataset_id"] = dataset_id
            report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
            report.setdefault("warnings", []).append("idempotent_noop: identical dataset already published")
            return report

        manifest = {
            "schema_version": "1.0", "dataset_id": dataset_id,
            "status": "validated" if not validation_errors and not missing_segments else "partial",
            "game": "LEAGUE_OF_LEGENDS", "patch": patch,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
            "sources": sources, "coverage": coverage,
            "quality": {"validation_passed": not validation_errors,
                        "warnings": warnings, "missing_segments": missing_segments},
        }
        report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
        try:
            self.store.publish(files, manifest, report)
            report["published_dataset_id"] = dataset_id
        except (SchemaError, ValueError) as e:
            report["errors"].append(f"publish refused: {e}")

        if rule_proposals:
            report["rule_proposals_count"] = len(rule_proposals)
            prop_path = self.store.root / "_staging" / f"rule_proposals_{run_id}.json"
            prop_path.write_text(json.dumps(rule_proposals, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
            report["rule_proposals_path"] = str(prop_path)
        return report

    @staticmethod
    def _merge_champion(existing: dict, new: dict) -> dict:
        """Field-level merge: Data Dragon authoritative for identity/base stats;
        legacy adds plausible roles + curated damage; observed WR beats legacy."""
        out = dict(existing)
        for field in ("roles",):
            vals = list(out.get(field) or [])
            for v in new.get(field) or []:
                if v not in vals:
                    vals.append(v)
            out[field] = vals
        for field in ("damage_profile_curated", "tags", "base_stats", "partype"):
            if new.get(field) and not out.get(field):
                out[field] = new[field]
        new_q = (new.get("overall_win_rate_quality") or {}).get("status")
        old_q = (out.get("overall_win_rate_quality") or {}).get("status")
        rank = {"observed": 3, "derived": 2, "legacy_unverified": 1}
        if new.get("overall_win_rate") is not None and rank.get(new_q, 0) >= rank.get(old_q, 0):
            out["overall_win_rate"] = new["overall_win_rate"]
            out["overall_win_rate_quality"] = new["overall_win_rate_quality"]
        return out

    @staticmethod
    def _natural_key(kind: str, rec: dict):
        if kind == "champions":
            return rec["champion_id"]
        if kind == "champion_mechanics":
            return rec["champion_id"]
        if kind == "champion_role_stats":
            return (rec["champion_id"], rec["role"], rec["patch"], rec["queue"],
                    rec["region"], rec["rank_scope"])
        if kind == "matchups":
            return (rec["champion_id"], rec["champion_role"], rec["opponent_id"],
                    rec["opponent_role"], rec["relation_type"], rec["patch"],
                    rec["region"], rec["rank_scope"], rec.get("queue", "RANKED_SOLO"),
                    rec.get("legacy_direction", ""))
        if kind == "synergies":
            return (rec["champion_id"], rec["champion_role"], rec["ally_id"],
                    rec["ally_role"], rec["patch"], rec["region"], rec["rank_scope"])
        if kind == "builds":
            return (rec["champion_id"], rec["role"], rec["patch"],
                    tuple(rec.get("items", [])))
        return json.dumps(rec, sort_keys=True)

    @staticmethod
    def _previous_records(previous, kind: str) -> list[dict]:
        attr = {"champions": "champions", "champion_role_stats": "role_stats",
                "matchups": "matchups", "synergies": "synergies",
                "builds": "builds", "champion_mechanics": "mechanics"}[kind]
        data = getattr(previous, attr)
        return list(data.values()) if isinstance(data, dict) else data
