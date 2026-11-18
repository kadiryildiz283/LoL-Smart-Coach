"""Role Inference Engine (kutsal_amac.md §9): JOINT role assignment distribution.

Flex picks are resolved together, not independently: we enumerate all valid
assignments of the five roles to the enemy team consistent with plausible-role
sets and locked roles, weight by pick priors, and normalize. For 5 champions
this is at most 5! = 120 permutations — exact, no approximation needed.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from engine.config import Config
from engine.contracts.types import Role, ALL_ROLES
from engine.data.store import Dataset
from engine.engines.meta import MetaEngine
from engine.stats import entropy


@dataclass
class RoleDistribution:
    joints: list[tuple[dict[int, Role], float]] = field(default_factory=list)
    marginals: dict[int, dict[str, float]] = field(default_factory=dict)
    uncertainty: float = 0.0  # mean normalized entropy over champions

    def role_prob(self, champion_id: int, role: Role) -> float:
        return self.marginals.get(champion_id, {}).get(role.value, 0.0)

    def most_likely(self, champion_id: int) -> Role | None:
        m = self.marginals.get(champion_id)
        if not m:
            return None
        return Role(max(m, key=m.get))


class RoleInferenceEngine:
    def __init__(self, config: Config, dataset: Dataset, meta: MetaEngine):
        self.cfg = config
        self.ds = dataset
        self.meta = meta
        self._plausible_cache: dict[int, list[Role]] = {}
        self._role_stats_by_champ: dict[int, list[dict]] = {}
        for r in dataset.role_stats:
            self._role_stats_by_champ.setdefault(r["champion_id"], []).append(r)

    def plausible_roles(self, champion_id: int) -> list[Role]:
        if champion_id in self._plausible_cache:
            return self._plausible_cache[champion_id]
        result = self._plausible_uncached(champion_id)
        self._plausible_cache[champion_id] = result
        return result

    def _plausible_uncached(self, champion_id: int) -> list[Role]:
        roles: list[Role] = []
        for r in self._role_stats_by_champ.get(champion_id, []):
            if r.get("metric_scope") == "ROLE_SPECIFIC":
                pr = r["stats"]["pick_rate"] or 0
                if pr >= 0.005 and Role(r["role"]) not in roles:
                    roles.append(Role(r["role"]))
        if roles:
            return roles
        champ = self.ds.champions.get(champion_id, {})
        for rs in champ.get("roles") or []:
            r = Role(rs) if isinstance(rs, str) else rs
            if r not in roles:
                roles.append(r)
        if roles:
            return roles
        # no evidence: all roles plausible (uniform), flagged via uncertainty
        return list(ALL_ROLES)

    def infer(self, enemy: list[tuple[int, Role | None]]) -> RoleDistribution:
        """enemy: [(champion_id, locked_role_or_None)] — up to 5 entries."""
        if not enemy:
            return RoleDistribution()
        ids = [cid for cid, _ in enemy]
        locked = {cid: role for cid, role in enemy if role is not None}
        plausible = {cid: self.plausible_roles(cid) for cid in ids}
        for cid, role in locked.items():
            plausible[cid] = [role]
        priors = {(cid, r): max(self.meta.pick_prior(cid, r), 1e-4)
                  for cid in ids for r in plausible[cid]}

        joints: list[tuple[dict[int, Role], float]] = []
        n = len(ids)
        for role_perm in itertools.permutations(ALL_ROLES, n):
            assignment = dict(zip(ids, role_perm))
            if any(assignment[cid] not in plausible[cid] for cid in ids):
                continue
            w = 1.0
            for cid in ids:
                w *= priors[(cid, assignment[cid])]
            if w > 0:
                joints.append((assignment, w))
        if not joints:
            # constraints unsatisfiable (bad lock data): fall back to independent marginals
            dist = RoleDistribution()
            for cid in ids:
                rs = plausible[cid]
                weights = [priors[(cid, r)] for r in rs]
                tot = sum(weights) or 1.0
                dist.marginals[cid] = {r.value: w / tot for r, w in zip(rs, weights)}
            dist.uncertainty = sum(entropy(list(m.values())) for m in dist.marginals.values()) / max(1, len(ids))
            return dist

        total = sum(w for _, w in joints)
        joints = [(a, w / total) for a, w in joints]
        joints.sort(key=lambda x: -x[1])
        marginals: dict[int, dict[str, float]] = {cid: {} for cid in ids}
        for assignment, p in joints:
            for cid, role in assignment.items():
                marginals[cid][role.value] = marginals[cid].get(role.value, 0.0) + p
        unc = sum(entropy(list(m.values())) for m in marginals.values()) / max(1, len(ids))
        return RoleDistribution(joints=joints, marginals=marginals, uncertainty=round(unc, 4))
