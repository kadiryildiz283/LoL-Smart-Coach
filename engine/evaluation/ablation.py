"""Ablation runner (kutsal_amac.md §22.8, §23.5): measure each component's
real contribution to ranking. Reports top-1 change rate and mean rank shift
when a component is zeroed — on HEURISTIC scores (not win probabilities).
"""
from __future__ import annotations

import random

from engine.config import Config
from engine.contracts.types import ALL_ROLES
from engine.data.store import Dataset
from engine.engines.decision import DecisionEngine
from engine.engines.draft import build_draft

COMPONENTS = ["meta_main_effect", "matchup_effects", "ally_synergy",
              "composition_fit", "enemy_threat", "future_draft_expectation"]


def run_ablation(cfg: Config, ds: Dataset, n: int = 12, samples: int = 64) -> dict:
    eng = DecisionEngine(cfg, ds)
    rng = random.Random(11)
    ids = list(ds.champions.keys())
    drafts = []
    for i in range(n):
        pool = rng.sample(ids, min(12, len(ids)))
        role = rng.choice(ALL_ROLES)
        if len(pool) >= 11:
            ally, enemy = (pool[:4], pool[4:9]) if i % 2 == 0 else (pool[:3], pool[3:6])
            bans = pool[9:11]
        else:
            k = min(4, max(2, len(pool) - 6))  # leave headroom for future picks
            ally, enemy = pool[:k // 2], pool[k // 2:k]
            bans = pool[k:k + 2]
        drafts.append(build_draft(ds, role, ally, enemy, bans))

    def ranking(draft, zero=None):
        rec = eng.recommend(draft, mc_samples=samples, seed=42)
        scores = {}
        for ev in rec.candidates:
            s = ev.ranking_score or 0.0
            if zero:
                s -= sum(c.get("logodds", 0) for c in ev.feature_contributions
                         if c["component"] == zero)
            scores[ev.champion_id] = s
        return sorted(scores, key=lambda c: (-scores[c], c))

    base = [ranking(d) for d in drafts]
    results = {}
    for comp in COMPONENTS:
        top1_changes = 0
        rank_shifts = []
        for d, b in zip(drafts, base):
            if not b:
                continue
            alt = ranking(d, zero=comp)
            if not alt:
                continue
            if alt[0] != b[0]:
                top1_changes += 1
            pos = {c: i for i, c in enumerate(alt)}
            rank_shifts.append(sum(abs(pos.get(c, len(alt)) - i)
                                   for i, c in enumerate(b)) / len(b))
        results[comp] = {
            "top1_change_rate": round(top1_changes / n, 3),
            "mean_rank_shift": round(sum(rank_shifts) / n, 3),
        }
    return {"n_drafts": n, "mc_samples": samples, "components": results,
            "scale": "heuristic log-odds ranking (not calibrated probabilities)"}
