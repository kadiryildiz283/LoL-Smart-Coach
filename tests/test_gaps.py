"""Gap-closure tests: model gate, audit trail, interrupt-resume, builds,
coverage honesty, derived rates, changed segments, baselines."""
import json

import numpy as np
import pytest

from engine.contracts.types import Role, ALL_ROLES
from engine.data.pipeline import IngestionPipeline
from engine.data.providers.base import Provider, ProviderResult, cache_put, cache_get
from engine.data.store import DatasetStore
from engine.engines.decision import DecisionEngine
from engine.engines.draft import build_draft
from engine.model import (
    train_logistic, predict_proba, time_split, calibration_gate, draft_features,
)
from engine.stats import sigmoid, logit
from tests.conftest import _mini_files


def test_model_train_and_gate_synthetic(real_ds, cfg):
    """SYNTHETIC ground truth from overall WRs; verifies training + gate code paths."""
    eng = DecisionEngine(cfg, real_ds)
    ids = [cid for cid, c in real_ds.champions.items() if c.get("overall_win_rate")]
    import random
    rng = random.Random(3)
    matches = []
    for i in range(200):
        pool = rng.sample(ids, 10)
        blue = [(c, ALL_ROLES[j]) for j, c in enumerate(pool[:5])]
        red = [(c, ALL_ROLES[j]) for j, c in enumerate(pool[5:])]
        lo = sum(logit(real_ds.champions[c]["overall_win_rate"]) for c, _ in blue) - \
            sum(logit(real_ds.champions[c]["overall_win_rate"]) for c, _ in red)
        matches.append({"match_id": f"SYN-{i}", "patch": f"16.{10 + i // 80}",
                        "timestamp": f"2026-{1 + i // 80:02d}-01",
                        "teams": {"BLUE": blue, "RED": red},
                        "win_blue": int(rng.random() < sigmoid(lo)), "quality": "synthetic"})
    train, test = time_split(matches)
    assert train[-1]["patch"] <= test[0]["patch"]  # no future leakage

    def xy(ms):
        X, y = [], []
        for m in ms:
            X.append(draft_features(eng, m["teams"]["BLUE"], m["teams"]["RED"]))
            y.append(m["win_blue"])
        return np.array(X), np.array(y)

    Xtr, ytr = xy(train)
    Xte, yte = xy(test)
    model = train_logistic(Xtr, ytr)
    probs = predict_proba(model, Xte)
    assert ((probs >= 0) & (probs <= 1)).all()
    base = predict_proba(train_logistic(Xtr[:, [0]], ytr), Xte[:, [0]])
    gate = calibration_gate(model, Xte, yte, base)
    assert "calibration_gate_passed" in gate and "ece" in gate
    assert isinstance(gate["calibration_gate_passed"], bool)


def test_audit_trail(mini_ds, mini_cfg):
    from engine.data.audit import AuditLog
    eng = DecisionEngine(mini_cfg, mini_ds)
    draft = build_draft(mini_ds, Role.BOTTOM, [412], [67], [])
    rec = eng.recommend(draft, mc_samples=8, seed=1)
    audit = AuditLog(mini_cfg.datasets_dir / "audit")
    latest = audit.latest()
    assert latest is not None
    assert latest["recommended_champion_id"] == rec.recommended_champion_id
    snap = json.loads((mini_cfg.datasets_dir / "audit" / "draft_snapshot.json").read_text())
    assert snap["user_role"] == "BOTTOM"
    assert len(audit.history()) >= 1


class InterruptProvider(Provider):
    name = "interrupt_test"

    def __init__(self):
        self.calls = 0

    def collect(self, staging, resume=True):
        self.calls += 1
        urls = ["https://x.test/a", "https://x.test/b"]
        if self.calls == 1:
            cache_put(staging, urls[0], {"v": 1})
            raise RuntimeError("simulated interruption")
        res = ProviderResult(provider=self.name)
        for u in urls:
            cached = cache_get(staging, u)
            if cached is not None:
                res.cached += 1
            else:
                cache_put(staging, u, {"v": 2})
                res.fetched += 1
        files = _mini_files()
        res.records = {"champions": list(files["champions.json"].values())}
        return res


def test_interrupt_then_resume(tmp_path, mini_cfg):
    store = DatasetStore(tmp_path / "datasets")
    p = InterruptProvider()
    pipe = IngestionPipeline(mini_cfg, store, [p])
    r1 = pipe.run()
    assert r1["published_dataset_id"] is None  # interrupted run publishes nothing
    assert any("interrupt_test" in e for e in r1["errors"])
    r2 = pipe.run()
    assert r2["published_dataset_id"] is not None
    prov = [x for x in r2["providers"] if x["provider"] == "interrupt_test"][0]
    assert prov["cached"] == 1 and prov["fetched"] == 1  # resumed, not re-downloaded


def test_builds_parser_fixtures():
    from engine.data.providers.leagueofgraphs import parse_items, parse_runes
    items_html = """
    <h2>Starting Build</h2><div class="lolg-table">
    <div class="lolg-table__row" data-sort-popularity="0.78" data-sort-winrate="0.485">
      <img tooltip-var="item-3340" alt="Stealth Ward"/><img tooltip-var="item-1086"/>
    </div></div>
    <h2>Core Build</h2><div class="lolg-table">
    <div class="lolg-table__row" data-sort-popularity="0.5" data-sort-winrate="0.52">
      <img tooltip-var="item-3031"/><img tooltip-var="item-3006"/>
    </div></div>"""
    rows = parse_items(items_html)
    assert len(rows) == 2
    assert rows[0]["section"] == "starting" and 3340 in rows[0]["items"]
    assert rows[1]["win_rate"] == 0.52
    runes_html = """
    <h2>Best runes</h2><div class="lolg-meter-pair">
    <span class="lolg-meter__label">Popularity</span> <span class="lolg-meter__value">73.9%</span>
    <span class="lolg-meter__label">Winrate</span> <span class="lolg-meter__value">47.8%</span>
    </div><img tooltip-var="perk-8005"/><img tooltip-var="perk-8008"/>"""
    rr = parse_runes(runes_html)
    assert len(rr) == 1
    assert rr[0]["popularity"] == 0.739 and rr[0]["win_rate"] == 0.478
    assert 8005 in rr[0]["perks"]


def test_coverage_ratio_and_derived_shares(tmp_path, mini_cfg):
    store = DatasetStore(tmp_path / "datasets")
    files = _mini_files()
    from tests.test_contracts_pipeline import StaticProvider
    p = StaticProvider({"champions": list(files["champions.json"].values()),
                        "champion_role_stats": files["champion_role_stats.json"],
                        "matchups": files["matchups.json"]})
    rep = IngestionPipeline(mini_cfg, store, [p]).run()
    cov = rep["coverage"]
    assert "matchup_pair_coverage_ratio" in cov
    assert cov["matchup_pairs_observed"] <= cov["matchup_pairs_possible"]
    ds = store.latest()
    # Caitlyn has one role with pick 0.1 -> role_play_rate derived = 1.0
    cait = [r for r in ds.role_stats if r["champion_id"] == 51][0]
    assert cait["stats"]["role_play_rate"] == 1.0
    assert cait.get("role_play_rate_derived") is True


def test_changed_segments(tmp_path, mini_cfg):
    store = DatasetStore(tmp_path / "datasets")
    files = _mini_files()
    from tests.test_contracts_pipeline import StaticProvider
    p1 = StaticProvider({"champions": list(files["champions.json"].values())})
    IngestionPipeline(mini_cfg, store, [p1]).run()
    modified = list(files["champions.json"].values())
    modified[0]["overall_win_rate"] = 0.60  # big shift
    p2 = StaticProvider({"champions": modified})
    rep2 = IngestionPipeline(mini_cfg, store, [p2]).run()
    assert modified[0]["champion_id"] in rep2["changed_segments"]["champions"]


def test_observed_beats_legacy_shadow(tmp_path, mini_cfg):
    """Legacy record listed first must NOT shadow the observed one for a pair."""
    from engine.engines.matchup import MatchupEngine
    from engine.engines.meta import MetaEngine
    from engine.contracts.types import RelationType
    store = DatasetStore(tmp_path / "datasets")
    files = _mini_files()
    shadow = {
        "schema_version": "1.0", "champion_id": 51, "champion_role": "BOTTOM",
        "opponent_id": 67, "opponent_role": "BOTTOM", "relation_type": "SAME_LANE",
        "patch": "legacy-unknown", "region": "ALL", "rank_scope": "IRON_PLUS",
        "queue": "RANKED_SOLO", "sample_size": None, "observed_win_rate": None,
        "expected_win_rate": None, "adjusted_matchup_delta": None,
        "lane_gold_diff_15": None, "lane_cs_diff_15": None, "lane_xp_diff_15": None,
        "confidence_interval": None, "legacy_derived_score": 9.0,
        "legacy_direction": "ADVANTAGE",
        "provenance": {"provider": "legacy_leagueofgraphs"},
        "quality": {"status": "legacy_derived", "missing_reason": "raw_wr_lost",
                    "confidence": 0.25},
    }
    # shadow FIRST in the list, like the real pipeline merge order
    files["matchups.json"] = [shadow] + files["matchups.json"]
    manifest = {
        "schema_version": "1.0", "dataset_id": "ds-shadow-test", "status": "validated",
        "game": "LEAGUE_OF_LEGENDS", "patch": "16.23",
        "generated_at": "2026-11-18T00:00:00+00:00",
        "sources": [{"provider": "test", "status": "ok"}],
        "coverage": {"champions": 10},
        "quality": {"validation_passed": True, "warnings": [], "missing_segments": []},
    }
    store.publish(files, manifest, {"run_id": "t"})
    ds = store.latest()
    eng = MatchupEngine(mini_cfg, ds, MetaEngine(mini_cfg, ds))
    d = eng.delta(51, Role.BOTTOM, 67, Role.BOTTOM, RelationType.SAME_LANE)
    assert d["kind"] == "observed", d
    assert d["observed"] == 0.481
    assert d["confidence"] > 0.5


def test_baselines_ranking_only(real_ds, cfg):
    from engine.evaluation.baselines import run_baselines
    rep = run_baselines(cfg, real_ds)
    assert rep["mode"] == "ranking_only_no_outcome_data"
    assert "meta_only" in rep["baselines"]
    assert "full_composition" in rep["baselines"]
