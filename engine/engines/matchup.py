"""Lane Matchup Engine (kutsal_amac.md §8).

Core principle: observed WR is compared against the expectation from main
effects; only the ADJUSTED DELTA (log-odds) enters the decision model, so the
champion's general strength is never double-counted. SAME_LANE and CROSS_TEAM
relations are kept strictly separate.
"""
from __future__ import annotations

from engine.config import Config
from engine.contracts.evidence import Evidence
from engine.contracts.types import SignalType, QualityStatus, Role, RelationType
from engine.data.store import Dataset
from engine.engines.meta import MetaEngine
from engine.stats import (
    logit, expected_matchup_wr, wilson_interval, sample_confidence,
)

LEGACY_SCORE_TO_LOGODDS = 0.3   # max ±0.3 log-odds at score extremes
LEGACY_CONFIDENCE = 0.25        # raw WR was discarded; weak ordinal signal only


class MatchupEngine:
    def __init__(self, config: Config, dataset: Dataset, meta: MetaEngine):
        self.cfg = config
        self.ds = dataset
        self.meta = meta
        # O(1) pair indexes (MC simulation calls this thousands of times).
        # Quality-aware priority: observed beats legacy, current patch/scope beats
        # old ones, bigger sample beats smaller. setdefault would let the legacy
        # record (listed first) shadow the observed one for the same pair.
        self._exact: dict[tuple, dict] = {}
        self._relaxed: dict[tuple, dict] = {}
        for key, rec in self.ds.matchup_idx.items():
            cid, crole, oid, orole, relation = key[0], key[1], key[2], key[3], key[4]
            ek = (cid, crole, oid, orole, relation)
            rk = (cid, crole, oid, relation)
            if ek not in self._exact or self._prio(rec) > self._prio(self._exact[ek]):
                self._exact[ek] = rec
            if rk not in self._relaxed or self._prio(rec) > self._prio(self._relaxed[rk]):
                self._relaxed[rk] = rec
        self._delta_cache: dict[tuple, dict] = {}

    def _prio(self, rec: dict) -> tuple:
        return (1 if rec.get("observed_win_rate") is not None else 0,
                1 if rec.get("patch") == self.ds.manifest.get("patch") else 0,
                1 if rec.get("rank_scope") == self.cfg.engine.rank_scope else 0,
                rec.get("sample_size") or 0)

    def _find(self, cid: int, crole: Role, oid: int, orole: Role,
              relation: RelationType) -> dict | None:
        return (self._exact.get((cid, crole.value, oid, orole.value, relation.value))
                or self._relaxed.get((cid, crole.value, oid, relation.value)))

    def delta(self, cid: int, crole: Role, oid: int, orole: Role,
              relation: RelationType) -> dict:
        """Returns {logodds, confidence, kind, observed, expected, evidence}."""
        ck = (cid, crole.value, oid, orole.value, relation.value)
        if ck in self._delta_cache:
            return self._delta_cache[ck]
        result = self._delta_uncached(cid, crole, oid, orole, relation)
        self._delta_cache[ck] = result
        return result

    def _delta_uncached(self, cid: int, crole: Role, oid: int, orole: Role,
                        relation: RelationType) -> dict:
        wa = self.meta.role_strength(cid, crole)["wr"]
        wb = self.meta.role_strength(oid, orole)["wr"]
        expected = expected_matchup_wr(wa, wb)
        m = self._find(cid, crole, oid, orole, relation)
        if m is None:
            return {"logodds": 0.0, "confidence": 0.0, "kind": "missing",
                    "observed": None, "expected": expected, "evidence": None}
        observed = m.get("observed_win_rate")
        if observed is not None:
            n = m.get("sample_size")
            delta = logit(observed) - logit(expected)
            conf = sample_confidence(n) if n else 0.3
            ci = wilson_interval(observed * n, n) if n else None
            ev = Evidence(
                signal_type=SignalType.LANE_MATCHUP if relation == RelationType.SAME_LANE
                else SignalType.CROSS_MATCHUP,
                subject={"champion_id": cid, "role": crole.value},
                target={"champion_id": oid, "role": orole.value},
                metric="MATCHUP_DELTA_LOGODDS", raw_value=round(delta, 5), unit="LOG_ODDS",
                context={"patch": m["patch"], "rank_scope": m["rank_scope"],
                         "region": m["region"], "relation": relation.value,
                         "perspective": "SUBJECT",
                         "observed_win_rate": observed, "expected_win_rate": round(expected, 5)},
                sample_size=n,
                uncertainty=ci.to_dict() if ci else {"standard_error": None,
                                                     "lower_bound": None, "upper_bound": None},
                source={"provider": m["provenance"]["provider"],
                        "dataset_id": self.ds.dataset_id,
                        "source_url": m["provenance"].get("source_url")},
                validation_status=QualityStatus(m["quality"]["status"]),
                model_version="heuristic-baseline-0.1",
            )
            return {"logodds": delta, "confidence": conf, "kind": "observed",
                    "observed": observed, "expected": expected, "evidence": ev,
                    "gold15": m.get("lane_gold_diff_15")}
        legacy = m.get("legacy_derived_score")
        if legacy is not None:
            direction = -1.0 if m.get("legacy_direction") == "DISADVANTAGE" else 1.0
            effect = (legacy - 5.0) / 5.0 * LEGACY_SCORE_TO_LOGODDS * direction * LEGACY_CONFIDENCE
            ev = Evidence(
                signal_type=SignalType.LANE_MATCHUP if relation == RelationType.SAME_LANE
                else SignalType.CROSS_MATCHUP,
                subject={"champion_id": cid, "role": crole.value},
                target={"champion_id": oid, "role": orole.value},
                metric="LEGACY_MATCHUP_SCORE", raw_value=legacy, unit="SCORE",
                context={"patch": m["patch"], "rank_scope": m["rank_scope"],
                         "relation": relation.value, "perspective": "SUBJECT",
                         "direction": m.get("legacy_direction"),
                         "note": "raw WR discarded by legacy normalization; weak ordinal signal"},
                sample_size=None,
                source={"provider": m["provenance"]["provider"], "dataset_id": self.ds.dataset_id},
                validation_status=QualityStatus.LEGACY_DERIVED,
                model_version="heuristic-baseline-0.1",
            )
            return {"logodds": effect, "confidence": LEGACY_CONFIDENCE, "kind": "legacy",
                    "observed": None, "expected": expected, "evidence": ev}
        return {"logodds": 0.0, "confidence": 0.0, "kind": "missing",
                "observed": None, "expected": expected, "evidence": None}
