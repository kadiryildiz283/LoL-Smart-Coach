"""Versioned dataset store with atomic publish and rollback (kutsal_amac.md §5).

Layout:
  datasets/index.json                  {"latest": id, "history": [ids]}
  datasets/<dataset_id>/*.json         self-contained validated snapshot
  datasets/_staging/<provider-key>/    content-addressed raw cache (resume)

A failed or invalid run NEVER touches the latest pointer.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from engine.contracts.schema import validate_record, SchemaError

DATASET_FILES = [
    "champions.json", "champion_role_stats.json", "matchups.json",
    "synergies.json", "builds.json", "champion_mechanics.json",
]


@dataclass
class Dataset:
    dataset_id: str
    path: Path
    manifest: dict
    champions: dict[int, dict] = field(default_factory=dict)
    role_stats: list[dict] = field(default_factory=list)
    matchups: list[dict] = field(default_factory=list)
    synergies: list[dict] = field(default_factory=list)
    builds: list[dict] = field(default_factory=list)
    mechanics: dict[int, dict] = field(default_factory=dict)
    report: dict = field(default_factory=dict)
    # indexes
    role_stats_idx: dict = field(default_factory=dict)
    matchup_idx: dict = field(default_factory=dict)
    synergy_idx: dict = field(default_factory=dict)
    name_to_id: dict[str, int] = field(default_factory=dict)

    def build_indexes(self) -> None:
        self.name_to_id = {c["name"].lower(): cid for cid, c in self.champions.items()}
        for r in self.role_stats:
            key = (r["champion_id"], r["role"], r["patch"], r["rank_scope"], r["region"])
            self.role_stats_idx.setdefault(key, r)
        for m in self.matchups:
            key = (m["champion_id"], m["champion_role"], m["opponent_id"],
                   m["opponent_role"], m["relation_type"], m["patch"],
                   m["rank_scope"], m["region"])
            self.matchup_idx.setdefault(key, m)
        for s in self.synergies:
            key = (s["champion_id"], s["champion_role"], s["ally_id"],
                   s["ally_role"], s["patch"], s["rank_scope"], s["region"])
            self.synergy_idx.setdefault(key, s)

    def resolve_id(self, name_or_id) -> int | None:
        if isinstance(name_or_id, int):
            return name_or_id if name_or_id in self.champions else None
        return self.name_to_id.get(str(name_or_id).lower())

    def stats_for(self, champion_id: int, role: str, patch: str | None = None,
                  rank_scope: str | None = None) -> dict | None:
        patch = patch or self.manifest.get("patch")
        rank_scope = rank_scope or "ALL"
        for scope in (rank_scope, "ALL"):
            r = self.role_stats_idx.get((champion_id, role, patch, scope, "ALL"))
            if r:
                return r
        return None

    def matchup_for(self, cid: int, crole: str, oid: int, orole: str,
                    relation: str, patch: str | None = None,
                    rank_scope: str | None = None) -> dict | None:
        patch = patch or self.manifest.get("patch")
        for scope in (rank_scope or "ALL", "ALL"):
            m = self.matchup_idx.get((cid, crole, oid, orole, relation, patch, scope, "ALL"))
            if m:
                return m
        return None


class DatasetStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"

    def _read_index(self) -> dict:
        if self.index_path.exists():
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        return {"latest": None, "history": []}

    def staging_dir(self, provider_key: str) -> Path:
        p = self.root / "_staging" / provider_key
        p.mkdir(parents=True, exist_ok=True)
        return p

    def publish(self, files: dict[str, list | dict], manifest: dict,
                report: dict) -> str:
        """Validate everything, write atomically, then move the latest pointer.

        `files` maps filename -> JSON-serializable content. Raises SchemaError
        before anything is written if any record is invalid.
        """
        validate_record("manifest", manifest)
        kind_by_file = {
            "champion_role_stats.json": "champion_role_stats",
            "matchups.json": "matchup",
            "synergies.json": "synergy",
        }
        for fname, kind in kind_by_file.items():
            for rec in files.get(fname, []):
                validate_record(kind, rec)

        dataset_id = manifest["dataset_id"]
        final_dir = self.root / dataset_id
        if final_dir.exists():
            raise ValueError(f"dataset {dataset_id} already exists; immutable once published")

        tmp_dir = Path(tempfile.mkdtemp(prefix=f".tmp-{dataset_id}-", dir=self.root))
        try:
            for fname in DATASET_FILES:
                (tmp_dir / fname).write_text(
                    json.dumps(files.get(fname, [] if fname != "champions.json"
                               and fname != "champion_mechanics.json" else {}),
                               ensure_ascii=False), encoding="utf-8")
            (tmp_dir / "dataset_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            (tmp_dir / "ingestion_report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp_dir, final_dir)
        except BaseException:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise

        idx = self._read_index()
        idx["history"].append(dataset_id)
        idx["latest"] = dataset_id
        tmp_index = self.root / ".index.tmp"
        tmp_index.write_text(json.dumps(idx, indent=2), encoding="utf-8")
        os.replace(tmp_index, self.index_path)
        return dataset_id

    def load(self, dataset_id: str) -> Dataset:
        path = self.root / dataset_id
        manifest = json.loads((path / "dataset_manifest.json").read_text(encoding="utf-8"))
        ds = Dataset(dataset_id=dataset_id, path=path, manifest=manifest)
        champs = json.loads((path / "champions.json").read_text(encoding="utf-8"))
        ds.champions = {int(c["champion_id"]): c for c in champs.values()} if isinstance(champs, dict) \
            else {int(c["champion_id"]): c for c in champs}
        ds.role_stats = json.loads((path / "champion_role_stats.json").read_text(encoding="utf-8"))
        ds.matchups = json.loads((path / "matchups.json").read_text(encoding="utf-8"))
        ds.synergies = json.loads((path / "synergies.json").read_text(encoding="utf-8"))
        ds.builds = json.loads((path / "builds.json").read_text(encoding="utf-8"))
        mechs = json.loads((path / "champion_mechanics.json").read_text(encoding="utf-8"))
        ds.mechanics = {int(m["champion_id"]): m for m in mechs.values()} if isinstance(mechs, dict) \
            else {int(m["champion_id"]): m for m in mechs}
        report_path = path / "ingestion_report.json"
        ds.report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
        ds.build_indexes()
        return ds

    def latest(self) -> Dataset | None:
        idx = self._read_index()
        if not idx.get("latest"):
            return None
        return self.load(idx["latest"])

    def rollback(self, dataset_id: str) -> None:
        if not (self.root / dataset_id / "dataset_manifest.json").exists():
            raise ValueError(f"unknown dataset: {dataset_id}")
        idx = self._read_index()
        idx["latest"] = dataset_id
        idx["history"].append(f"rollback:{dataset_id}")
        tmp = self.root / ".index.tmp"
        tmp.write_text(json.dumps(idx, indent=2), encoding="utf-8")
        os.replace(tmp, self.index_path)

    def list_datasets(self) -> list[str]:
        return self._read_index().get("history", [])
