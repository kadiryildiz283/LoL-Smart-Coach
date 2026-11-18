"""Future Draft Engine (kutsal_amac.md §12, §23.8).

Q(candidate) = Σ P(future_draft, role_assignment | current, candidate)
               × P(win | completed_draft)

Monte Carlo over: joint enemy role assignments (from RoleInferenceEngine),
conditional future picks (meta prior × strength × counter-response with
temperature — opponents are NOT assumed to counter perfectly), respecting
bans, uniqueness and role validity. Deterministic seed; time-budgeted;
cached per (draft hash, candidate, samples, seed).
"""
from __future__ import annotations

import math
import random
import time

from engine.config import Config
from engine.contracts.records import DraftState
from engine.contracts.types import Role, ALL_ROLES, RelationType
from engine.data.store import Dataset
from engine.engines.draft import future_steps, enemy_known, ally_known
from engine.engines.meta import MetaEngine
from engine.engines.matchup import MatchupEngine
from engine.engines.role_inference import RoleInferenceEngine, RoleDistribution
from engine.stats import mean, cvar, stderr, sigmoid


class FutureDraftEngine:
    def __init__(self, config: Config, dataset: Dataset, meta: MetaEngine,
                 matchup: MatchupEngine, role_inf: RoleInferenceEngine):
        self.cfg = config
        self.ds = dataset
        self.meta = meta
        self.matchup = matchup
        self.role_inf = role_inf
        self._cache: dict[tuple, dict] = {}
        self._static: dict[str, dict[int, float]] = {}
        self._resp_cache: dict[tuple, dict[int, float]] = {}

    # ---------- conditional pick model ----------
    def _static_weights(self, role: Role) -> dict[int, float]:
        """prior × strength per champion-role, computed once (cached)."""
        if role.value not in self._static:
            d = {}
            for cid in self.ds.champions:
                if role in self.role_inf.plausible_roles(cid):
                    d[cid] = max(self.meta.pick_prior(cid, role), 1e-4) * \
                        math.exp(self.meta.logodds(cid, role) * 0.5)
            self._static[role.value] = d
        return self._static[role.value]

    def _pick_weights(self, role: Role, available: list[int],
                      opposing: list[tuple[int, Role]], is_enemy: bool,
                      allies: list[tuple[int, Role]]) -> list[tuple[int, float]]:
        static = self._static_weights(role)
        # response depends only on the OPPOSING SET, not on the shrinking available
        # pool -> computed once and reused across all MC samples.
        ck = (role.value, tuple(sorted(opposing)), is_enemy,
              tuple(sorted(allies)) if not is_enemy else ())
        resp = self._resp_cache.get(ck)
        if resp is None:
            temp = max(self.cfg.engine.future_counter_temperature, 0.1)
            resp = {}
            syn = getattr(self, "_synergy", None)
            for cid in static:
                r = 0.0
                if is_enemy:
                    for oid, orole in opposing:
                        rel = RelationType.SAME_LANE if orole == role else RelationType.CROSS_TEAM
                        d = self.matchup.delta(cid, role, oid, orole, rel)
                        r += d["logodds"] * d["confidence"] * (1.0 if rel == RelationType.SAME_LANE else 0.3)
                elif syn is not None:
                    for aid, arole in allies:
                        s = syn.pair(cid, role, aid, arole)
                        r += s["logodds"] * s["confidence"] * 0.5
                resp[cid] = math.exp(r / temp)
            self._resp_cache[ck] = resp
        out = [(cid, static[cid] * resp.get(cid, 1.0)) for cid in available if cid in static]
        if not out:  # no plausible champ for this role: allow any available (flagged upstream)
            out = [(cid, max(self.meta.pick_prior(cid, role), 1e-4)) for cid in available]
        return out

    @staticmethod
    def _weighted_sample_without_replacement(rng, items_weights, k):
        pool = list(items_weights)
        chosen = []
        for _ in range(min(k, len(pool))):
            total = sum(w for _, w in pool)
            if total <= 0:
                pick = rng.choice(pool)[0]
            else:
                pick = rng.choices([c for c, _ in pool], weights=[w for _, w in pool], k=1)[0]
            chosen.append(pick)
            pool = [(c, w) for c, w in pool if c != pick]
        return chosen

    # ---------- simulation ----------
    def simulate_outcomes(self, draft: DraftState, candidate_id: int,
                          role_dist: RoleDistribution, win_model,
                          n_samples: int, seed: int,
                          deadline: float | None = None) -> list[float]:
        rng = random.Random(seed * 1_000_003 + candidate_id)
        steps = future_steps(draft)
        known_enemy = enemy_known(draft)
        known_ally = ally_known(draft)
        user_role = draft.user_role
        other = "RED" if draft.user_team == "BLUE" else "BLUE"
        banned = set(draft.banned_ids)
        base_picked = set(draft.picked_ids) | {candidate_id}

        # enemy joint assignments (known enemies); cache the distribution list
        joints = role_dist.joints or [({}, 1.0)]
        joint_probs = [p for _, p in joints]

        outcomes = []
        for _ in range(n_samples):
            if deadline and time.monotonic() > deadline:
                break
            picked = set(base_picked)
            available = [cid for cid in draft.available_ids if cid not in picked]

            # --- role assignment for this sample ---
            ji = rng.choices(range(len(joints)), weights=joint_probs, k=1)[0]
            enemy_roles: dict[int, Role] = dict(joints[ji][0])
            used_enemy_roles = set(enemy_roles.values())
            enemy_future_roles = [r for r in ALL_ROLES if r not in used_enemy_roles]
            rng.shuffle(enemy_future_roles)

            ally_roles: dict[int, Role] = {cid: (r or user_role) for cid, r in known_ally if r}
            ally_pool = [r for r in ALL_ROLES if r != user_role and r not in ally_roles.values()]
            # known allies without role: sample weighted by pick prior
            for cid, r in known_ally:
                if r is None and ally_pool:
                    weights = [(rr, max(self.meta.pick_prior(cid, rr), 1e-4)) for rr in ally_pool]
                    pick = self._weighted_sample_without_replacement(rng, weights, 1)[0]
                    ally_roles[cid] = pick
                    ally_pool.remove(pick)
            ally_future_roles = list(ally_pool)
            rng.shuffle(ally_future_roles)

            # --- fill future picks in draft order ---
            enemy_team: list[tuple[int, Role]] = [(cid, enemy_roles.get(cid) or Role.MIDDLE)
                                                   for cid, _ in known_enemy]
            ally_team: list[tuple[int, Role]] = [(candidate_id, user_role)] + \
                [(cid, ally_roles.get(cid) or Role.MIDDLE) for cid, _ in known_ally]
            ef_idx, af_idx = 0, 0
            for order_i, team, slot_index in steps:
                if not available:
                    break  # pool exhausted (tiny fixtures): evaluate partial completion
                if team == other:
                    role = enemy_future_roles[ef_idx] if ef_idx < len(enemy_future_roles) else Role.MIDDLE
                    ef_idx += 1
                    weights = self._pick_weights(role, available, ally_team, True, [])
                else:
                    role = ally_future_roles[af_idx] if af_idx < len(ally_future_roles) else Role.MIDDLE
                    af_idx += 1
                    weights = self._pick_weights(role, available, enemy_team, False, ally_team)
                if not weights:
                    break
                cid = self._weighted_sample_without_replacement(rng, weights, 1)[0]
                (enemy_team if team == other else ally_team).append((cid, role))
                picked.add(cid)
                available = [c for c in available if c != cid]
            outcomes.append(win_model(ally_team, enemy_team))
        return outcomes

    def evaluate(self, draft: DraftState, candidate_id: int, role_dist: RoleDistribution,
                 win_model, n_samples: int | None = None, seed: int | None = None,
                 deadline: float | None = None) -> dict:
        n = n_samples or self.cfg.engine.mc_samples
        s = seed if seed is not None else self.cfg.engine.seed
        ck = (draft.state_hash(), candidate_id, n, s)
        if ck in self._cache:
            return self._cache[ck]
        outcomes = self.simulate_outcomes(draft, candidate_id, role_dist, win_model, n, s, deadline)
        if not outcomes:
            result = {"expected": None, "downside": None, "mc_se": None,
                      "draft_uncertainty": None, "n_actual": 0}
        else:
            exp = mean(outcomes)
            result = {
                "expected": round(exp, 5),
                "downside": round(cvar(outcomes, self.cfg.engine.cvar_alpha), 5),
                "mc_se": round(stderr(outcomes), 5),
                "draft_uncertainty": round(stderr(outcomes) * math.sqrt(len(outcomes)), 5),
                "n_actual": len(outcomes),
            }
        self._cache[ck] = result
        return result
