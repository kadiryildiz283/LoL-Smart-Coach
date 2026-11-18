"""Latency benchmark (kutsal_amac.md §16): p95 target 2s with warm data."""
from __future__ import annotations

import random
import time

from engine.config import Config
from engine.contracts.types import Role, ALL_ROLES
from engine.data.store import Dataset
from engine.engines.decision import DecisionEngine
from engine.engines.draft import build_draft


def run_benchmark(cfg: Config, ds: Dataset, n: int = 20, samples: int = 128) -> dict:
    eng = DecisionEngine(cfg, ds)
    rng = random.Random(7)
    ids = list(ds.champions.keys())
    latencies = []
    scenarios = {"complete": 0, "partial": 0, "blind": 0}
    for i in range(n):
        role = rng.choice(ALL_ROLES)
        pool = rng.sample(ids, min(12, len(ids)))
        mode = i % 3
        if len(pool) >= 11:
            if mode == 0:      # 9 known, user last
                ally, enemy = pool[:4], pool[4:9]
                scenarios["complete"] += 1
            elif mode == 1:    # 3v3, user picks now
                ally, enemy = pool[:3], pool[3:6]
                scenarios["partial"] += 1
            else:              # blind
                ally, enemy = pool[:1], pool[1:2]
                scenarios["blind"] += 1
            bans = pool[9:11]
        else:
            k = min(8, len(pool) - 2)
            ally, enemy = pool[:k // 2], pool[k // 2:k]
            bans = pool[k:k + 2]
            scenarios["partial" if mode else "complete"] += 1
        draft = build_draft(ds, role, ally, enemy, bans)
        t0 = time.monotonic()
        eng.recommend(draft, mc_samples=samples, seed=42)
        latencies.append(time.monotonic() - t0)
    latencies.sort()

    def pct(p):
        return round(latencies[min(len(latencies) - 1, int(p * len(latencies)))], 4)

    p95 = pct(0.95)
    return {
        "n_drafts": n, "mc_samples": samples, "scenarios": scenarios,
        "p50_s": pct(0.50), "p95_s": p95, "max_s": round(latencies[-1], 4),
        "target_p95_s": 2.0, "target_met": p95 <= 2.0,
        "dataset_id": ds.dataset_id,
        "note": "warm caches; first-call cold start excluded by design (engines pre-built)",
    }
