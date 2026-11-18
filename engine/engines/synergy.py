"""Team Synergy Engine (kutsal_amac.md §10).

Pairwise synergy = observed together-WR minus expectation from main effects.
Composition-level marginal utility with diminishing returns lives in
composition.py; here we only produce pairwise evidence.
"""
from __future__ import annotations

from engine.config import Config
from engine.contracts.evidence import Evidence
from engine.contracts.types import SignalType, QualityStatus, Role
from engine.data.store import Dataset
from engine.engines.meta import MetaEngine
from engine.stats import logit, sigmoid, sample_confidence, wilson_interval

LEGACY_CONFIDENCE = 0.25


class SynergyEngine:
    def __init__(self, config: Config, dataset: Dataset, meta: MetaEngine):
        self.cfg = config
        self.ds = dataset
        self.meta = meta
        self._by_pair: dict[tuple, dict] = {}
        for key, rec in self.ds.synergy_idx.items():
            pk = (key[0], key[2])
            if pk not in self._by_pair or self._prio(rec) > self._prio(self._by_pair[pk]):
                self._by_pair[pk] = rec
        self._cache: dict[tuple, dict] = {}

    def _prio(self, rec: dict) -> tuple:
        return (1 if rec.get("observed_win_rate") is not None else 0,
                1 if rec.get("patch") == self.ds.manifest.get("patch") else 0,
                1 if rec.get("rank_scope") == self.cfg.engine.rank_scope else 0,
                rec.get("sample_size") or 0)

    def _find(self, cid: int, crole: Role, ally_id: int) -> dict | None:
        return self._by_pair.get((cid, ally_id))

    def pair(self, cid: int, crole: Role, ally_id: int, ally_role: Role | None) -> dict:
        ck = (cid, crole.value, ally_id, ally_role.value if ally_role else None)
        if ck in self._cache:
            return self._cache[ck]
        result = self._pair_uncached(cid, crole, ally_id, ally_role)
        self._cache[ck] = result
        return result

    def _pair_uncached(self, cid: int, crole: Role, ally_id: int, ally_role: Role | None) -> dict:
        wa = self.meta.role_strength(cid, crole)["wr"]
        wb = self.meta.role_strength(ally_id, ally_role or Role.MIDDLE)["wr"]
        expected = sigmoid(logit(wa) + logit(wb))  # main-effects team baseline
        s = self._find(cid, crole, ally_id)
        if s is None:
            return {"logodds": 0.0, "confidence": 0.0, "kind": "missing", "evidence": None}
        observed = s.get("observed_win_rate")
        if observed is not None:
            n = s.get("sample_size")
            delta = logit(observed) - logit(expected)
            conf = sample_confidence(n) if n else 0.3
            ci = wilson_interval(observed * n, n) if n else None
            ev = Evidence(
                signal_type=SignalType.SYNERGY,
                subject={"champion_id": cid, "role": crole.value},
                target={"champion_id": ally_id, "role": s.get("ally_role")},
                metric="SYNERGY_DELTA_LOGODDS", raw_value=round(delta, 5), unit="LOG_ODDS",
                context={"patch": s["patch"], "rank_scope": s["rank_scope"],
                         "perspective": "SUBJECT_TEAM",
                         "observed_win_rate": observed, "expected_win_rate": round(expected, 5)},
                sample_size=n,
                uncertainty=ci.to_dict() if ci else {"standard_error": None,
                                                     "lower_bound": None, "upper_bound": None},
                source={"provider": s["provenance"]["provider"], "dataset_id": self.ds.dataset_id},
                validation_status=QualityStatus(s["quality"]["status"]),
                model_version="heuristic-baseline-0.1",
            )
            return {"logodds": delta, "confidence": conf, "kind": "observed", "evidence": ev}
        legacy = s.get("legacy_derived_score")
        if legacy is not None:
            effect = (legacy - 3.0) / 3.0 * 0.2 * LEGACY_CONFIDENCE
            ev = Evidence(
                signal_type=SignalType.SYNERGY,
                subject={"champion_id": cid, "role": crole.value},
                target={"champion_id": ally_id, "role": s.get("ally_role")},
                metric="LEGACY_SYNERGY_SCORE", raw_value=legacy, unit="SCORE",
                context={"patch": s["patch"], "rank_scope": s["rank_scope"],
                         "note": "legacy together-score; semantics not fully verified"},
                source={"provider": s["provenance"]["provider"], "dataset_id": self.ds.dataset_id},
                validation_status=QualityStatus.LEGACY_DERIVED,
                model_version="heuristic-baseline-0.1",
            )
            return {"logodds": effect, "confidence": LEGACY_CONFIDENCE, "kind": "legacy",
                    "evidence": ev}
        return {"logodds": 0.0, "confidence": 0.0, "kind": "missing", "evidence": None}
