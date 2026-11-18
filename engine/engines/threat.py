"""Enemy Threat Engine (kutsal_amac.md §11): candidate vs the WHOLE enemy team.

Lane advantage does not immunize a candidate against dive/burst/poke from the
other four enemies. Threat exposure is a negative log-odds contribution.
"""
from __future__ import annotations

from engine.config import Config
from engine.contracts.evidence import Evidence
from engine.contracts.types import SignalType, QualityStatus, Role
from engine.data.store import Dataset
from engine.engines.composition import _feat, coverage

THREAT_WEIGHTS = {
    "dive": 0.22,        # enemy mobility+engage vs candidate mobility+range+peel
    "burst": 0.18,       # enemy assassins vs candidate durability/sustain
    "cc_chain": 0.15,    # enemy hard CC vs candidate mobility/tenacity proxies
    "poke": 0.12,        # enemy poke vs candidate sustain/range
    "frontline_wall": 0.10,  # enemy frontline vs candidate anti-tank (true damage/range)
}


class ThreatEngine:
    def __init__(self, config: Config, dataset: Dataset):
        self.cfg = config
        self.ds = dataset
        self._cache: dict[tuple, dict] = {}

    def exposure(self, candidate_id: int, enemy_ids_roles: list[tuple[int, Role]]) -> dict:
        ck = (candidate_id, tuple(sorted(cid for cid, _ in enemy_ids_roles)))
        if ck in self._cache:
            return self._cache[ck]
        result = self._exposure_uncached(candidate_id, enemy_ids_roles)
        self._cache[ck] = result
        return result

    def _exposure_uncached(self, candidate_id: int, enemy_ids_roles: list[tuple[int, Role]]) -> dict:
        cand = self.ds.mechanics.get(candidate_id)
        enemies = [self.ds.mechanics.get(cid) for cid, _ in enemy_ids_roles]
        if not enemies or cand is None:
            return {"logodds": 0.0, "confidence": 0.0, "components": {}, "evidence": None}
        e_mob = coverage(enemies, ["mobility"], 8.0)
        e_eng = coverage(enemies, ["engage", "hard_cc"], 8.0)
        e_cc = coverage(enemies, ["hard_cc"], 10.0)
        e_poke = coverage(enemies, ["poke"], 8.0)
        e_front = coverage(enemies, ["frontline"], 6.0)
        e_burst = sum(1 for cid, _ in enemy_ids_roles
                      if "Assassin" in (self.ds.champions.get(cid, {}).get("tags") or [])) / 5.0

        c_mob = _feat(cand, "mobility") / 10.0
        c_range = min(1.0, _feat(cand, "attack_range") / 650.0)
        c_dur = _feat(cand, "frontline") / 10.0
        c_sus = _feat(cand, "sustain") / 10.0
        c_anti_mob = _feat(cand, "anti_mobility") / 10.0
        c_true = _feat(cand, "true_damage") / 10.0
        c_cc = _feat(cand, "hard_cc") / 10.0

        threats = {
            "dive": max(0.0, (e_mob * 0.6 + e_eng * 0.4) - (c_mob * 0.5 + c_range * 0.3 + c_cc * 0.2)),
            "burst": max(0.0, e_burst * 0.8 + e_cc * 0.2 - (c_dur * 0.5 + c_sus * 0.3 + c_mob * 0.2)),
            "cc_chain": max(0.0, e_cc - (c_mob * 0.6 + c_anti_mob * 0.4)),
            "poke": max(0.0, e_poke - (c_sus * 0.5 + c_range * 0.3 + c_dur * 0.2)),
            "frontline_wall": max(0.0, e_front - (c_true * 0.5 + c_range * 0.3 + _feat(cand, "damage_ad") / 10.0 * 0.2)),
        }
        total = -sum(THREAT_WEIGHTS[k] * v for k, v in threats.items())
        total = round(total, 5)
        ev = Evidence(
            signal_type=SignalType.THREAT,
            subject={"champion_id": candidate_id, "role": None},
            target={"team": "ENEMY", "members": [cid for cid, _ in enemy_ids_roles]},
            metric="THREAT_EXPOSURE", raw_value=total, unit="LOG_ODDS",
            context={"patch": self.ds.manifest["patch"], "perspective": "SUBJECT",
                     "components": {k: round(v, 4) for k, v in threats.items()},
                     "note": "mechanic-derived heuristic; not a win guarantee"},
            source={"provider": "threat_engine", "dataset_id": self.ds.dataset_id},
            validation_status=QualityStatus.DERIVED,
            model_version="heuristic-baseline-0.1",
        )
        return {"logodds": total, "confidence": 0.4,
                "components": threats, "evidence": ev}
