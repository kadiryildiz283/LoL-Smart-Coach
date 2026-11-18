"""Meta Engine (kutsal_amac.md §7): role-based strength with shrinkage and
explicit hierarchical fallback. Never converts WR to 0-10; stays in log-odds.
"""
from __future__ import annotations

from engine.config import Config
from engine.contracts.evidence import Evidence
from engine.contracts.types import SignalType, QualityStatus, Role
from engine.data.store import Dataset
from engine.stats import (
    logit, shrink_win_rate, wilson_interval, sample_confidence,
)


class MetaEngine:
    def __init__(self, config: Config, dataset: Dataset):
        self.cfg = config
        self.ds = dataset
        self._role_prior: dict[str, float] = {}
        self._strength_cache: dict[tuple[int, str], dict] = {}
        self._compute_role_priors()

    def _compute_role_priors(self) -> None:
        sums: dict[str, list[float]] = {}
        for r in self.ds.role_stats:
            wr = r["stats"]["win_rate"]
            n = r["stats"]["sample_size"] or 0
            if wr is not None and r.get("metric_scope") == "ROLE_SPECIFIC":
                sums.setdefault(r["role"], []).extend([wr] * max(1, min(n, 50)))
        for role, vals in sums.items():
            self._role_prior[role] = sum(vals) / len(vals)
        # global prior from overall WRs when role data is thin
        overalls = [c["overall_win_rate"] for c in self.ds.champions.values()
                    if c.get("overall_win_rate")]
        self._global_prior = sum(overalls) / len(overalls) if overalls else 0.5

    def role_prior(self, role: Role) -> float:
        return self._role_prior.get(role.value, self._global_prior)

    def role_strength(self, champion_id: int, role: Role) -> dict:
        """Returns {wr, confidence, fallback, source, sample_size}."""
        ck = (champion_id, role.value)
        if ck in self._strength_cache:
            return self._strength_cache[ck]
        result = self._role_strength_uncached(champion_id, role)
        self._strength_cache[ck] = result
        return result

    def _role_strength_uncached(self, champion_id: int, role: Role) -> dict:
        stats = self.ds.stats_for(champion_id, role.value,
                                  rank_scope=self.cfg.engine.rank_scope)
        prior = self.role_prior(role)
        if stats and stats["stats"]["win_rate"] is not None:
            n = stats["stats"]["sample_size"]
            wr, fb = shrink_win_rate(stats["stats"]["win_rate"], n, prior,
                                     self.cfg.engine.shrinkage_strength)
            conf = sample_confidence(n)
            return {"wr": wr, "confidence": max(conf, 0.05), "fallback": fb,
                    "source": "role_stats", "sample_size": n,
                    "quality": stats["quality"]["status"]}
        champ = self.ds.champions.get(champion_id, {})
        owr = champ.get("overall_win_rate")
        if owr is not None:
            n = champ.get("overall_sample_size")
            wr, fb = shrink_win_rate(owr, n, prior, self.cfg.engine.shrinkage_strength)
            return {"wr": wr, "confidence": sample_confidence(n) * 0.6,
                    "fallback": True, "source": "overall_fallback", "sample_size": n,
                    "quality": champ.get("overall_win_rate_quality", {}).get("status", "missing"),
                    "fallback_of": "overall_all_roles"}
        return {"wr": prior, "confidence": 0.0, "fallback": True,
                "source": "prior_only", "sample_size": None, "quality": "missing",
                "fallback_of": "role_prior"}

    def pick_prior(self, champion_id: int, role: Role) -> float:
        stats = self.ds.stats_for(champion_id, role.value,
                                  rank_scope=self.cfg.engine.rank_scope)
        if stats and stats["stats"]["pick_rate"]:
            return stats["stats"]["pick_rate"]
        champ = self.ds.champions.get(champion_id, {})
        if champ.get("overall_pick_rate") and role.value in (champ.get("roles") or []):
            return champ["overall_pick_rate"] / max(1, len(champ["roles"]))
        return 0.001  # small floor: plausible but unobserved

    def signal(self, champion_id: int, role: Role) -> Evidence:
        s = self.role_strength(champion_id, role)
        ci = wilson_interval(s["wr"] * (s["sample_size"] or 0), s["sample_size"]) \
            if s["sample_size"] else None
        status = (QualityStatus.OBSERVED if s["source"] == "role_stats" and not s["fallback"]
                  else QualityStatus.FALLBACK if s["fallback"] and s["confidence"] > 0
                  else QualityStatus.MISSING)
        return Evidence(
            signal_type=SignalType.META,
            subject={"champion_id": champion_id, "role": role.value},
            target=None,
            metric="WIN_RATE",
            raw_value=round(s["wr"], 5),
            unit="FRACTION",
            context={"patch": self.ds.manifest["patch"],
                     "rank_scope": self.cfg.engine.rank_scope, "region": "ALL",
                     "perspective": "SUBJECT", "fallback_of": s.get("fallback_of")},
            sample_size=s["sample_size"],
            uncertainty=ci.to_dict() if ci else {"standard_error": None,
                                                 "lower_bound": None, "upper_bound": None},
            source={"provider": "meta_engine", "dataset_id": self.ds.dataset_id},
            validation_status=status,
            model_version="heuristic-baseline-0.1",
        )

    def logodds(self, champion_id: int, role: Role) -> float:
        return logit(self.role_strength(champion_id, role)["wr"])
