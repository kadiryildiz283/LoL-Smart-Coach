"""Rule Registry (kutsal_amac.md §22.4, §22.9): persistent, versioned,
semantically deduplicated game-knowledge store with full lifecycle audit.

Files: game_rules/{mechanics,champion_matchups,champion_synergies,
team_compositions,strategic_principles,meta_observations,rule_registry,
rule_conflicts}.json
"""
from __future__ import annotations

import json
from pathlib import Path

from engine.contracts.records import Rule, utcnow
from engine.contracts.schema import validate_record, SchemaError
from engine.contracts.types import RuleType, RuleStatus

COLLECTION_BY_TYPE = {
    "mechanic": "mechanics.json",
    "strategic": "strategic_principles.json",
    "empirical": "meta_observations.json",
}
RELATION_COLLECTION = {
    "LANE_PRESSURE_ADVANTAGE": "champion_matchups.json",
    "HARD_COUNTERED_BY": "champion_matchups.json",
    "EASY_MATCHUP_VS": "champion_matchups.json",
    "SYNERGY_WITH": "champion_synergies.json",
    "COMPOSITION_COUNTER": "team_compositions.json",
}


class RuleRegistry:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._rules: dict[str, dict] = {}
        self._by_semantic: dict[str, str] = {}
        self._load()

    def _files(self) -> list[Path]:
        return [self.root / f for f in
                ["mechanics.json", "champion_matchups.json", "champion_synergies.json",
                 "team_compositions.json", "strategic_principles.json",
                 "meta_observations.json"]]

    def _load(self) -> None:
        for p in self._files():
            if p.exists():
                for r in json.loads(p.read_text(encoding="utf-8")):
                    self._rules[r["rule_id"]] = r
                    if r.get("semantic_key"):
                        self._by_semantic[r["semantic_key"]] = r["rule_id"]

    def all(self) -> list[dict]:
        return list(self._rules.values())

    def get(self, rule_id: str) -> dict | None:
        return self._rules.get(rule_id)

    def find_by_semantic(self, semantic_key: str) -> dict | None:
        rid = self._by_semantic.get(semantic_key)
        return self._rules.get(rid) if rid else None

    def _collection_for(self, rule: dict) -> str:
        rel = rule.get("relation", "")
        if rel in RELATION_COLLECTION:
            return RELATION_COLLECTION[rel]
        return COLLECTION_BY_TYPE.get(rule.get("rule_type", "strategic"), "strategic_principles.json")

    def upsert(self, rule: dict, change_reason: str = "") -> tuple[str, str]:
        """Returns (rule_id, action). action in {created, updated, dedup_skipped}.
        Semantic duplicates never create a second record; updates keep history."""
        validate_record("rule", rule)
        sem = rule.get("semantic_key") or Rule.compute_semantic_key(
            rule["rule_type"], rule["subject"], rule["target"], rule["relation"],
            rule.get("game_phase", "ALL"), rule.get("conditions", []), rule.get("scope", {}))
        rule["semantic_key"] = sem
        existing = self.find_by_semantic(sem)
        if existing is not None:
            if json.dumps(existing, sort_keys=True) == json.dumps(rule, sort_keys=True):
                return existing["rule_id"], "dedup_skipped"
            old = dict(existing)
            rule["rule_id"] = existing["rule_id"]
            rule["version"] = existing.get("version", 1) + 1
            rule.setdefault("history", existing.get("history", []))
            rule["history"].append({"version": old.get("version", 1),
                                    "changed_at": utcnow(), "reason": change_reason,
                                    "previous_status": old.get("status"),
                                    "snapshot": old})
            self._rules[rule["rule_id"]] = rule
            self._by_semantic[sem] = rule["rule_id"]
            self._save()
            return rule["rule_id"], "updated"
        if not rule.get("rule_id"):
            rule["rule_id"] = f"rule-{sem[:12]}"
        self._rules[rule["rule_id"]] = rule
        self._by_semantic[sem] = rule["rule_id"]
        self._save()
        return rule["rule_id"], "created"

    def set_status(self, rule_id: str, status: RuleStatus, reason: str) -> None:
        rule = self._rules.get(rule_id)
        if rule is None:
            raise KeyError(rule_id)
        old = rule["status"]
        rule["status"] = status.value
        rule.setdefault("history", []).append(
            {"version": rule.get("version", 1), "changed_at": utcnow(),
             "reason": reason, "previous_status": old, "status_change": True})
        rule.setdefault("review", {})["last_reviewed_patch"] = rule.get("scope", {}).get("patch_from")
        self._save()

    def active_rules(self) -> list[dict]:
        """Only VERIFIED/ACTIVE rules may influence automatic ranking (§22.8)."""
        return [r for r in self._rules.values()
                if r["status"] in (RuleStatus.VERIFIED.value, RuleStatus.ACTIVE.value)]

    def pending_review(self) -> list[dict]:
        return [r for r in self._rules.values()
                if r["status"] in (RuleStatus.PROPOSED.value, RuleStatus.VALIDATING.value,
                                   RuleStatus.NEEDS_REVIEW.value)]

    def conflicts(self) -> list[dict]:
        p = self.root / "rule_conflicts.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

    def record_conflict(self, conflict: dict) -> None:
        p = self.root / "rule_conflicts.json"
        items = self.conflicts()
        items.append({"recorded_at": utcnow(), **conflict})
        p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save(self) -> None:
        buckets: dict[str, list] = {}
        for r in self._rules.values():
            buckets.setdefault(self._collection_for(r), []).append(r)
        for fname, items in buckets.items():
            tmp = self.root / (fname + ".tmp")
            tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.root / fname)
        reg = self.root / "rule_registry.json"
        index = [{"rule_id": r["rule_id"], "semantic_key": r.get("semantic_key"),
                  "type": r["rule_type"], "status": r["status"], "version": r.get("version", 1)}
                 for r in self._rules.values()]
        tmp = self.root / "rule_registry.tmp"
        tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(reg)
