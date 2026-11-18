"""Calibrated win model (§17, §23.3): regularized logistic on log-odds features.

GATED: a model file is only marked calibration_gate_passed when it beats the
meta-only baseline on a TIME-BASED holdout (no future-patch leakage). Until
then the decision engine stays HEURISTIC and predicted_win_probability=null.

Match-level records (matches.jsonl) come from Riot Match-v5 derivation; the
synthetic generator below is for TESTS ONLY and is labeled synthetic.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from engine.stats import sigmoid, brier_score, log_loss, expected_calibration_error

FEATURE_NAMES = [
    "meta_main_diff",       # Σ logit(wr_ally) - Σ logit(wr_enemy)
    "lane_delta_sum",       # same-lane adjusted deltas (ally perspective)
    "cross_delta_sum",      # cross-team deltas (discounted)
    "synergy_diff",         # ally pair synergy - enemy pair synergy
    "composition_diff",     # composition power terms
    "threat_diff",          # threat exposure differential
]


def draft_features(engine, ally: list[tuple[int, object]],
                   enemy: list[tuple[int, object]]) -> list[float]:
    from engine.contracts.types import RelationType
    meta = sum(engine.meta.logodds(c, r) for c, r in ally) - \
        sum(engine.meta.logodds(c, r) for c, r in enemy)
    lane = cross = 0.0
    for ac, ar in ally:
        for ec, er in enemy:
            rel = RelationType.SAME_LANE if ar == er else RelationType.CROSS_TEAM
            d = engine.matchup.delta(ac, ar, ec, er, rel)
            if rel == RelationType.SAME_LANE:
                lane += d["logodds"] * d["confidence"]
            else:
                cross += d["logodds"] * d["confidence"] * 0.25
    syn = 0.0
    for team, sign in ((ally, 1.0), (enemy, -1.0)):
        for i in range(len(team)):
            for j in range(i + 1, len(team)):
                s = engine.synergy.pair(team[i][0], team[i][1], team[j][0], team[j][1])
                syn += sign * s["logodds"] * s["confidence"] * 0.5
    comp = engine.composition.team_power_terms(ally) - engine.composition.team_power_terms(enemy)
    thr = sum(engine.threat.exposure(c, enemy)["logodds"] for c, _ in ally) - \
        sum(engine.threat.exposure(c, ally)["logodds"] for c, _ in enemy)
    return [meta, lane, cross, syn, comp, thr]


def train_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1.0,
                   lr: float = 0.2, epochs: int = 800) -> dict:
    """L2-regularized logistic regression, full-batch GD, standardized features.
    Feature scaling + shrinkage-built inputs give hierarchical partial pooling."""
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd < 1e-9] = 1.0
    Xs = (X - mu) / sd
    w = np.zeros(Xs.shape[1])
    b = 0.0
    n = len(y)
    for _ in range(epochs):
        p = sigmoid_vec(Xs @ w + b)
        grad_w = Xs.T @ (p - y) / n + l2 * w / n
        grad_b = float((p - y).mean())
        w -= lr * grad_w
        b -= lr * grad_b
    return {"weights": w.tolist(), "bias": b, "feature_mean": mu.tolist(),
            "feature_std": sd.tolist(), "feature_names": FEATURE_NAMES,
            "l2": l2, "trained": True}


def sigmoid_vec(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def predict_proba(model: dict, X: np.ndarray) -> np.ndarray:
    mu = np.array(model["feature_mean"])
    sd = np.array(model["feature_std"])
    Xs = (X - mu) / sd
    return sigmoid_vec(Xs @ np.array(model["weights"]) + model["bias"])


def time_split(records: list[dict], test_frac: float = 0.25) -> tuple[list, list]:
    """Split by patch/time so future patches never leak into training."""
    ordered = sorted(records, key=lambda r: (r.get("patch", ""), r.get("timestamp", "")))
    cut = int(len(ordered) * (1 - test_frac))
    return ordered[:cut], ordered[cut:]


def calibration_gate(model: dict, X_test: np.ndarray, y_test: np.ndarray,
                     baseline_probs: np.ndarray) -> dict:
    probs = predict_proba(model, X_test)
    ll = log_loss(probs.tolist(), y_test.astype(int).tolist())
    base_ll = log_loss(baseline_probs.tolist(), y_test.astype(int).tolist())
    ece = expected_calibration_error(probs.tolist(), y_test.astype(int).tolist())
    passed = bool(ll < base_ll and ece < 0.05)
    return {"log_loss": round(ll, 5), "baseline_log_loss": round(base_ll, 5),
            "brier": round(brier_score(probs.tolist(), y_test.astype(int).tolist()), 5),
            "ece": round(ece, 5), "n_test": int(len(y_test)),
            "calibration_gate_passed": passed}


def save_model(path: Path, model: dict, gate: dict, dataset_id: str) -> None:
    out = {**model, **gate, "dataset_id": dataset_id, "model_version": "logistic-l2-0.1"}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=2), encoding="utf-8")
    tmp.replace(path)


def reconstruct_draft_at_pick(teams: dict, pick_index: int, user_team: str,
                              user_role) -> dict:
    """Leakage guard (§17): rebuild the draft as known AT pick time; later
    picks are hidden. teams = {'BLUE': [(cid, role)...], 'RED': [...]} in pick order."""
    from engine.contracts.types import Role
    known = {t: picks[:pick_index] if t != user_team else picks[:pick_index]
             for t, picks in teams.items()}
    return {"user_team": user_team, "user_role": user_role,
            "known_at_pick": {t: [{"champion_id": c, "role": r} for c, r in p]
                              for t, p in known.items()},
            "hidden_future_picks": True}


def synthetic_matches(n: int = 400, seed: int = 7) -> list[dict]:
    """TEST FIXTURE ONLY — labeled synthetic, never production evidence.
    Generates drafts with a known ground-truth win process so the training
    and gate code paths can be verified without Riot credentials."""
    import random
    from engine.contracts.types import ALL_ROLES
    rng = random.Random(seed)
    ids = list(range(1, 41))
    strength = {cid: rng.gauss(0, 0.3) for cid in ids}
    out = []
    for i in range(n):
        pool = rng.sample(ids, 10)
        blue = [(c, ALL_ROLES[j]) for j, c in enumerate(pool[:5])]
        red = [(c, ALL_ROLES[j]) for j, c in enumerate(pool[5:])]
        lo = sum(strength[c] for c, _ in blue) - sum(strength[c] for c, _ in red)
        win = int(rng.random() < sigmoid(lo))
        out.append({"match_id": f"SYN-{i}", "patch": f"16.{10 + i // 100}",
                    "timestamp": f"2026-{1 + i // 100:02d}-01T00:00:00Z",
                    "teams": {"BLUE": blue, "RED": red}, "win_blue": win,
                    "quality": "synthetic"})
    return out
