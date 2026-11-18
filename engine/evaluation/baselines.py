"""Progressive baseline comparison (§17).

With match-level outcome data: train each baseline on a time split and compare
Brier / log-loss / ECE on the holdout. Without outcomes (current state): compare
RANKING behavior on real drafts (top-1 agreement, score spread) and report
honestly that outcome metrics are unavailable.
"""
from __future__ import annotations

import random

import numpy as np

from engine.config import Config
from engine.contracts.types import ALL_ROLES
from engine.data.store import Dataset
from engine.engines.decision import DecisionEngine
from engine.engines.draft import build_draft
from engine.model import (
    FEATURE_NAMES, draft_features, train_logistic, predict_proba,
    time_split, calibration_gate, synthetic_matches,
)
from engine.stats import brier_score, log_loss, expected_calibration_error

BASELINES = {
    "meta_only": [0],
    "lane_only": [1],
    "meta_matchup": [0, 1, 2],
    "meta_matchup_synergy": [0, 1, 2, 3],
    "full_composition": [0, 1, 2, 3, 4, 5],
}


def _xy_from_matches(engine, matches):
    X, y = [], []
    for m in matches:
        ally = [(c, r) for c, r in m["teams"]["BLUE"]]
        enemy = [(c, r) for c, r in m["teams"]["RED"]]
        X.append(draft_features(engine, ally, enemy))
        y.append(m["win_blue"])
    return np.array(X, dtype=float), np.array(y, dtype=float)


def run_baselines(cfg: Config, ds: Dataset, matches: list[dict] | None = None) -> dict:
    engine = DecisionEngine(cfg, ds)
    report = {"dataset_id": ds.dataset_id, "feature_names": FEATURE_NAMES}
    if matches is None:
        # no real match-level data: ranking-only comparison, explicitly labeled
        rng = random.Random(5)
        ids = list(ds.champions.keys())
        drafts = []
        for i in range(10):
            pool = rng.sample(ids, min(12, len(ids)))
            if len(pool) < 11:
                break
            role = rng.choice(ALL_ROLES)
            ally, enemy = (pool[:4], pool[4:9]) if i % 2 == 0 else (pool[:3], pool[3:6])
            drafts.append(build_draft(ds, role, ally, enemy, pool[9:11]))
        tops = {name: [] for name in BASELINES}
        for d in drafts:
            feats_cache = {}
            for name, cols in BASELINES.items():
                scores = []
                for cid in d.available_ids[:40]:
                    if cid not in feats_cache:
                        ally = [(cid, d.user_role)] + [(s.champion_id, s.role or d.user_role)
                                                       for s in d.team_picks(d.user_team)
                                                       if s.champion_id and not s.is_user]
                        enemy = [(s.champion_id, s.role or d.user_role)
                                 for s in d.team_picks("RED" if d.user_team == "BLUE" else "BLUE")
                                 if s.champion_id]
                        feats_cache[cid] = draft_features(engine, ally, enemy)
                    f = feats_cache[cid]
                    scores.append((sum(f[c] for c in cols), cid))
                scores.sort(reverse=True)
                tops[name].append(scores[0][1] if scores else None)
        full = tops["full_composition"]
        report["mode"] = "ranking_only_no_outcome_data"
        report["note"] = ("Maç-seviyesi sonuç verisi yok (RIOT_API_KEY bekleniyor); "
                          "Brier/log-loss/ECE hesaplanamaz. Sıralama davranışı karşılaştırılır.")
        report["baselines"] = {
            name: {"top1_agreement_with_full": round(
                sum(1 for a, b in zip(tops[name], full) if a == b) / max(1, len(full)), 3)}
            for name in BASELINES}
        return report

    train, test = time_split(matches)
    Xtr, ytr = _xy_from_matches(engine, train)
    Xte, yte = _xy_from_matches(engine, test)
    results = {}
    baseline_probs = None
    for name, cols in BASELINES.items():
        model = train_logistic(Xtr[:, cols], ytr)
        probs = predict_proba(model, Xte[:, cols])
        ll = log_loss(probs.tolist(), yte.astype(int).tolist())
        results[name] = {
            "brier": round(brier_score(probs.tolist(), yte.astype(int).tolist()), 5),
            "log_loss": round(ll, 5),
            "ece": round(expected_calibration_error(probs.tolist(), yte.astype(int).tolist()), 5),
        }
        if name == "meta_only":
            baseline_probs = probs
    full_model = train_logistic(Xtr, ytr)
    gate = calibration_gate(full_model, Xte, yte, baseline_probs)
    results["full_composition"]["calibration_gate"] = gate
    report["mode"] = "outcome_backtest"
    report["synthetic"] = all(m.get("quality") == "synthetic" for m in matches)
    report["n_train"] = len(train)
    report["n_test"] = len(test)
    report["baselines"] = results
    report["leakage_guard"] = "time_split by patch/timestamp; future picks hidden in reconstruction"
    return report
