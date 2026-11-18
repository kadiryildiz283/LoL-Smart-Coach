"""Recommendation audit trail (§4: draft_snapshot.json + recommendation.json).

Every recommendation is persisted with the exact draft state, dataset id and
model version that produced it, so any ranking can be reproduced later.
JSONL append log + latest single-object files, all schema-validated.
"""
from __future__ import annotations

import json
from pathlib import Path

from engine.contracts.schema import validate_record


class AuditLog:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def record(self, recommendation: dict, draft_snapshot: dict) -> None:
        validate_record("recommendation", recommendation)
        entry = {"recommendation": recommendation, "draft_snapshot": draft_snapshot}
        with open(self.root / "recommendations.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        with open(self.root / "draft_snapshots.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(draft_snapshot, ensure_ascii=False) + "\n")
        tmp = self.root / "recommendation.tmp"
        tmp.write_text(json.dumps(recommendation, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.root / "recommendation.json")
        tmp = self.root / "draft_snapshot.tmp"
        tmp.write_text(json.dumps(draft_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.root / "draft_snapshot.json")

    def latest(self) -> dict | None:
        p = self.root / "recommendation.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return None

    def history(self) -> list[dict]:
        p = self.root / "recommendations.jsonl"
        if not p.exists():
            return []
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
