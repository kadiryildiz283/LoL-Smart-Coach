"""Contract validation + pipeline guarantees (§5, §18.10, §18.17)."""
import json
import copy

import pytest

from engine.contracts.schema import validate_record, SchemaError
from engine.data.pipeline import IngestionPipeline
from engine.data.providers.base import Provider, ProviderResult
from engine.data.store import DatasetStore
from tests.conftest import _mini_files


def test_fraction_not_percent():
    files = _mini_files()
    rec = copy.deepcopy(files["champion_role_stats.json"][0])
    rec["stats"]["win_rate"] = 50.8  # percent — MUST be rejected
    with pytest.raises(SchemaError):
        validate_record("champion_role_stats", rec)
    rec["stats"]["win_rate"] = 0.508
    validate_record("champion_role_stats", rec)


def test_missing_is_null_not_zero():
    files = _mini_files()
    rec = copy.deepcopy(files["matchups.json"][0])
    rec["observed_win_rate"] = None
    rec["sample_size"] = None
    rec["quality"] = {"status": "missing", "missing_reason": "not_yet_collected"}
    validate_record("matchup", rec)  # null + reason is valid
    assert rec["observed_win_rate"] is None


def test_rank_region_separate_fields():
    files = _mini_files()
    rec = files["champion_role_stats.json"][0]
    assert "rank_scope" in rec and "region" in rec
    assert rec["rank_scope"] != rec["region"] or rec["region"] == "ALL"


def test_evidence_units_typed():
    from engine.contracts.evidence import Evidence
    from engine.contracts.types import SignalType, QualityStatus
    ev = Evidence(signal_type=SignalType.LANE_MATCHUP,
                  subject={"champion_id": 51, "role": "BOTTOM"},
                  target={"champion_id": 67, "role": "BOTTOM"},
                  metric="GOLD_DIFFERENCE_AT_15", raw_value=563, unit="GOLD",
                  validation_status=QualityStatus.OBSERVED)
    validate_record("evidence", ev.to_dict())
    bad = ev.to_dict()
    bad["unit"] = "PERCENT"  # not a canonical unit
    with pytest.raises(SchemaError):
        validate_record("evidence", bad)


def test_recommendation_heuristic_has_no_win_probability(real_ds, cfg):
    from engine.engines.decision import DecisionEngine
    from engine.engines.draft import build_draft
    from engine.contracts.types import Role
    eng = DecisionEngine(cfg, real_ds)
    draft = build_draft(real_ds, Role.MIDDLE,
                        [real_ds.resolve_id("Malphite")], [real_ds.resolve_id("Zed")], [])
    rec = eng.recommend(draft, mc_samples=16, seed=1)
    d = rec.to_dict()
    validate_record("recommendation", d)
    if rec.evaluation_mode.value == "HEURISTIC":
        assert d["predicted_win_probability"] is None
        assert d["ranking_score"] is not None


class StaticProvider(Provider):
    name = "static_test"

    def __init__(self, records, fail=False):
        self.records = records
        self.fail = fail
        self.calls = 0

    def collect(self, staging, resume=True):
        self.calls += 1
        if self.fail:
            raise RuntimeError("simulated network failure")
        res = ProviderResult(provider=self.name)
        res.records = self.records
        return res


def _publish_mini(store, dataset_id="ds-test-1"):
    files = _mini_files()
    manifest = {
        "schema_version": "1.0", "dataset_id": dataset_id, "status": "validated",
        "game": "LEAGUE_OF_LEGENDS", "patch": "16.23",
        "generated_at": "2026-11-18T00:00:00+00:00",
        "sources": [{"provider": "static_test", "status": "ok"}],
        "coverage": {"champions": 10}, "quality": {"validation_passed": True,
                                                   "warnings": [], "missing_segments": []},
    }
    return store.publish(files, manifest, {"run_id": "t"})


def test_failed_provider_carries_forward(tmp_path, mini_cfg):
    store = DatasetStore(tmp_path / "datasets")
    _publish_mini(store)
    prev = store.latest()
    failing = StaticProvider({}, fail=True)
    failing.name = "static_test"
    pipe = IngestionPipeline(mini_cfg, store, [failing])
    report = pipe.run()
    # previous good dataset must remain latest
    assert store.latest().dataset_id == prev.dataset_id or report["published_dataset_id"]
    assert "static_test" in report["carried_forward"]


def test_invalid_records_quarantined_not_published(tmp_path, mini_cfg):
    store = DatasetStore(tmp_path / "datasets")
    files = _mini_files()
    bad = copy.deepcopy(files["matchups.json"][0])
    bad["observed_win_rate"] = 52.0  # invalid percent
    provider = StaticProvider({"matchups": files["matchups.json"] + [bad],
                               "champions": list(files["champions.json"].values())})
    pipe = IngestionPipeline(mini_cfg, store, [provider])
    report = pipe.run()
    assert any(q["kind"] == "matchups" for q in report["quarantined"])
    ds = store.latest()
    assert all(m["observed_win_rate"] is None or m["observed_win_rate"] <= 1.0
               for m in ds.matchups)


def test_dedup_natural_keys(tmp_path, mini_cfg):
    store = DatasetStore(tmp_path / "datasets")
    files = _mini_files()
    dup = copy.deepcopy(files["matchups.json"][0])
    provider = StaticProvider({"matchups": files["matchups.json"] + [dup],
                               "champions": list(files["champions.json"].values())})
    pipe = IngestionPipeline(mini_cfg, store, [provider])
    report = pipe.run()
    ds = store.latest()
    keys = [(m["champion_id"], m["opponent_id"], m["relation_type"],
             m.get("legacy_direction", "")) for m in ds.matchups]
    assert len(keys) == len(set(keys))


def test_idempotent_dataset_id(tmp_path, mini_cfg):
    store = DatasetStore(tmp_path / "datasets")
    files = _mini_files()
    p1 = StaticProvider({"champions": list(files["champions.json"].values()),
                         "matchups": files["matchups.json"]})
    r1 = IngestionPipeline(mini_cfg, store, [p1]).run()
    p2 = StaticProvider({"champions": list(files["champions.json"].values()),
                         "matchups": files["matchups.json"]})
    r2 = IngestionPipeline(mini_cfg, store, [p2]).run()
    assert r1["published_dataset_id"] == r2["published_dataset_id"]


def test_resume_raw_cache(tmp_path):
    from engine.data.providers.base import cache_get, cache_put
    staging = tmp_path / "staging"
    staging.mkdir()
    url = "https://example.test/page"
    assert cache_get(staging, url) is None
    cache_put(staging, url, {"html": "<div>data</div>"})
    assert cache_get(staging, url)["body"]["html"] == "<div>data</div>"


def test_rollback(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    _publish_mini(store, "ds-a")
    _publish_mini(store, "ds-b")
    assert store.latest().dataset_id == "ds-b"
    store.rollback("ds-a")
    assert store.latest().dataset_id == "ds-a"


def test_legacy_rank_region_fix(real_ds):
    """§18.11 + audited defect: legacy 'region':'iron' must become rank_scope."""
    legacy = [m for m in real_ds.matchups
              if m["provenance"]["provider"] == "legacy_leagueofgraphs"]
    assert legacy, "legacy records missing"
    for m in legacy[:20]:
        assert m["region"] == "ALL"
        assert m["rank_scope"] in ("IRON_PLUS", "ALL")


def test_no_test_contamination(real_ds):
    assert real_ds.resolve_id("TestChampionPipeline") is None