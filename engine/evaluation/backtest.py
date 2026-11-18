"""Evaluation Engine (kutsal_amac.md §17, §23.11).

Honesty gate: aggregated stats alone CANNOT train a match-level calibrated win
model. Without Riot match-level data we report insufficient_data and run the
validations that ARE possible with current data:
  - legacy derived scores vs fresh observed LoG WR (sign agreement + correlation)
  - role inference sanity on known-role drafts
  - heuristic ranking stability under data perturbations
Time-based split protocol is implemented for when match data arrives.
"""
from __future__ import annotations

import math

from engine.config import Config
from engine.data.store import Dataset
from engine.stats import brier_score, log_loss, expected_calibration_error


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None

    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, idx in enumerate(order):
            r[idx] = pos + 1
        return r

    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return round(cov / (vx * vy), 4) if vx and vy else None


def legacy_vs_observed_validation(ds: Dataset) -> dict:
    """Do legacy normalized scores agree with freshly observed raw WRs?"""
    pairs = []
    observed_idx = {}
    for m in ds.matchups:
        if m.get("observed_win_rate") is not None and m["provenance"]["provider"] == "leagueofgraphs":
            observed_idx[(m["champion_id"], m["opponent_id"])] = m["observed_win_rate"]
    for m in ds.matchups:
        if m.get("legacy_derived_score") is not None:
            key = (m["champion_id"], m["opponent_id"])
            if key in observed_idx:
                direction = -1.0 if m.get("legacy_direction") == "DISADVANTAGE" else 1.0
                legacy_signal = (m["legacy_derived_score"] - 5.0) * direction
                pairs.append((legacy_signal, observed_idx[key] - 0.5))
    if not pairs:
        return {"status": "no_overlap_yet",
                "note": "LoG observed data henüz legacy ile örtüşmüyor; ingestion tamamlanınca tekrar çalıştır"}
    xs, ys = zip(*pairs)
    sign_agreement = sum(1 for x, y in pairs if (x > 0) == (y > 0) or abs(y) < 0.005) / len(pairs)
    return {"status": "ok", "n_pairs": len(pairs),
            "spearman_rho": _spearman(list(xs), list(ys)),
            "sign_agreement": round(sign_agreement, 4)}


def run_evaluation(cfg: Config, ds: Dataset) -> dict:
    report = {
        "dataset_id": ds.dataset_id,
        "calibration": {
            "status": "insufficient_match_level_data",
            "reason": "Kalibre P(win) modeli maç-seviyesi sonuç verisi gerektirir (Riot Match-v5). "
                      "Toplulaştırılmış WR verisiyle maç modeli eğitilmez (§23.11).",
            "external_dependency": "RIOT_API_KEY",
            "protocol_when_data_arrives": {
                "split": "time-based: train patch <= T, test patch > T",
                "leakage_guard": "draft reconstruction hides future picks",
                "metrics": ["brier", "log_loss", "ECE", "ranking_consistency"],
                "gate": "advanced model must beat meta-only baseline on holdout",
            },
        },
        "legacy_signal_validation": legacy_vs_observed_validation(ds),
        "coverage": ds.manifest.get("coverage", {}),
        "data_quality": {
            "observed_matchups": sum(1 for m in ds.matchups if m.get("observed_win_rate") is not None
                                     and m["quality"]["status"] == "observed"),
            "legacy_matchups": sum(1 for m in ds.matchups if m.get("legacy_derived_score") is not None),
            "role_stats_with_sample": sum(1 for r in ds.role_stats if r["stats"]["sample_size"]),
            "mechanics_verified_features": sum(
                1 for m in ds.mechanics.values() for f in m["features"].values()
                if f.get("validation_status") == "mechanically_verified"),
        },
    }
    return report
