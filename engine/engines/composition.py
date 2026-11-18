"""Composition Engine (kutsal_amac.md §10): holistic team function with
DIMINISHING RETURNS — a second engage source is worth less than the first.

All outputs are log-odds contributions with documented heuristic weights
(baseline priors; to be learned from match data in CALIBRATED mode).
"""
from __future__ import annotations

import math

from engine.config import Config
from engine.contracts.evidence import Evidence
from engine.contracts.types import SignalType, QualityStatus, Role
from engine.data.store import Dataset

# dimension -> (feature keys, saturation constant, target coverage, weight)
DIMENSIONS = {
    "engage": (["engage", "hard_cc"], 8.0, 0.65, 0.20),
    "frontline": (["frontline"], 6.0, 0.55, 0.18),
    "peel": (["sustain", "soft_cc"], 8.0, 0.50, 0.15),
    "cc_chain": (["hard_cc"], 10.0, 0.60, 0.15),
    "poke": (["poke", "waveclear"], 8.0, 0.45, 0.10),
    "pick": (["hard_cc", "mobility"], 10.0, 0.45, 0.10),
}
DAMAGE_BALANCE_WEIGHT = 0.30


def _feat(mech: dict | None, key: str) -> float:
    if not mech:
        return 0.0
    f = mech.get("features", {}).get(key)
    v = f.get("value") if f else None
    return float(v) if isinstance(v, (int, float)) else 0.0


def coverage(team_feats: list[dict], keys: list[str], sat: float) -> float:
    total = sum(sum(_feat(m, k) for k in keys) for m in team_feats)
    return 1.0 - math.exp(-total / sat) if total > 0 else 0.0


class CompositionEngine:
    def __init__(self, config: Config, dataset: Dataset):
        self.cfg = config
        self.ds = dataset
        self._power_cache: dict[tuple, float] = {}
        self._fit_cache: dict[tuple, dict] = {}

    def team_features(self, ids_roles: list[tuple[int, Role]]) -> list[dict]:
        return [self.ds.mechanics.get(cid) for cid, _ in ids_roles]

    def damage_ratio(self, team_feats: list[dict]) -> float:
        ap = sum(_feat(m, "damage_ap") for m in team_feats)
        ad = sum(_feat(m, "damage_ad") for m in team_feats)
        return ap / (ap + ad) if (ap + ad) > 0 else 0.5

    def marginal_fit(self, candidate_id: int, ally_ids_roles: list[tuple[int, Role]]) -> dict:
        """Log-odds contribution of candidate filling team gaps (diminishing returns)."""
        ck = (candidate_id, tuple(sorted(cid for cid, _ in ally_ids_roles)))
        if ck in self._fit_cache:
            return self._fit_cache[ck]
        result = self._marginal_fit_uncached(candidate_id, ally_ids_roles)
        self._fit_cache[ck] = result
        return result

    def _marginal_fit_uncached(self, candidate_id: int, ally_ids_roles: list[tuple[int, Role]]) -> dict:
        allies = self.team_features(ally_ids_roles)
        cand = self.ds.mechanics.get(candidate_id)
        contributions = []
        total = 0.0
        for dim, (keys, sat, target, weight) in DIMENSIONS.items():
            before = coverage(allies, keys, sat)
            after = coverage(allies + [cand], keys, sat)
            gap = max(0.0, target - before)
            value = weight * gap * (after - before) / max(target, 1e-6) * 2.0
            value = round(min(value, weight), 5)
            total += value
            if value > 0.005:
                contributions.append({"dimension": dim, "logodds": value,
                                      "coverage_before": round(before, 3),
                                      "coverage_after": round(after, 3)})
        # damage balance: mono-damage teams penalized; candidate restoring balance rewarded
        ratio_before = self.damage_ratio(allies)
        ratio_after = self.damage_ratio(allies + [cand])

        def imbalance(r):
            return max(0.0, abs(r - 0.5) - 0.22)  # dead zone 28%-72%

        bal_value = DAMAGE_BALANCE_WEIGHT * (imbalance(ratio_before) - imbalance(ratio_after)) * 2.0
        bal_value = round(bal_value, 5)
        total += bal_value
        if abs(bal_value) > 0.005:
            contributions.append({"dimension": "damage_balance", "logodds": bal_value,
                                  "ap_ratio_before": round(ratio_before, 3),
                                  "ap_ratio_after": round(ratio_after, 3)})
        ev = Evidence(
            signal_type=SignalType.COMPOSITION,
            subject={"champion_id": candidate_id, "role": None},
            target={"team": "ALLY", "members": [cid for cid, _ in ally_ids_roles]},
            metric="COMPOSITION_MARGINAL_FIT", raw_value=round(total, 5), unit="LOG_ODDS",
            context={"patch": self.ds.manifest["patch"], "perspective": "SUBJECT",
                     "contributions": contributions,
                     "note": "heuristic baseline weights; diminishing returns applied"},
            source={"provider": "composition_engine", "dataset_id": self.ds.dataset_id},
            validation_status=QualityStatus.DERIVED,
            model_version="heuristic-baseline-0.1",
        )
        return {"logodds": round(total, 5), "contributions": contributions, "evidence": ev}

    def team_power_terms(self, ids_roles: list[tuple[int, Role]]) -> float:
        """Absolute composition quality of a completed team (for win model)."""
        ck = tuple(sorted(cid for cid, _ in ids_roles))
        if ck in self._power_cache:
            return self._power_cache[ck]
        result = self._team_power_uncached(ids_roles)
        self._power_cache[ck] = result
        return result

    def _team_power_uncached(self, ids_roles: list[tuple[int, Role]]) -> float:
        feats = self.team_features(ids_roles)
        total = 0.0
        for dim, (keys, sat, target, weight) in DIMENSIONS.items():
            cov = coverage(feats, keys, sat)
            total += weight * min(cov, target) / target * 0.5
        ratio = self.damage_ratio(feats)
        total -= DAMAGE_BALANCE_WEIGHT * max(0.0, abs(ratio - 0.5) - 0.22) * 2.0
        return round(total, 5)
