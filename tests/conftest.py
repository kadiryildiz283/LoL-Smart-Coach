import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from engine.config import Config, DEFAULT_CONFIG
from engine.data.store import DatasetStore


@pytest.fixture(scope="session")
def real_ds():
    ds = DatasetStore(REPO / "datasets").latest()
    if ds is None:
        pytest.skip("no published dataset; run engine.cli ingest first")
    return ds


@pytest.fixture(scope="session")
def cfg():
    return DEFAULT_CONFIG


def _mini_files():
    """Synthetic mini dataset — explicitly SYNTHETIC, never production."""
    prov = {"provider": "synthetic_fixture", "collected_at": "2026-11-18T00:00:00+00:00"}
    q_obs = {"status": "observed", "missing_reason": None, "confidence": 0.8}
    q_syn = {"status": "synthetic", "missing_reason": None, "confidence": 0.5}
    champs = {}
    for cid, name, rng, tags in [
        (51, "Caitlyn", 650, ["Marksman"]), (67, "Vayne", 550, ["Marksman"]),
        (103, "Ahri", 550, ["Mage", "Assassin"]), (238, "Zed", 250, ["Assassin"]),
        (412, "Thresh", 450, ["Support", "Tank"]), (54, "Malphite", 125, ["Tank", "Fighter"]),
        (84, "Akali", 125, ["Assassin"]), (64, "Lee Sin", 125, ["Fighter", "Assassin"]),
        (22, "Ashe", 600, ["Marksman", "Support"]), (99, "Lux", 550, ["Mage", "Support"]),
    ]:
        champs[str(cid)] = {
            "schema_version": "1.0", "champion_id": cid, "name": name,
            "slug": name.lower().replace(" ", "").replace("'", ""),
            "roles": ["BOTTOM"] if cid in (51, 67, 22) else (["MIDDLE"] if cid in (103, 238, 84, 99) else ["TOP", "JUNGLE"]),
            "tags": tags, "overall_win_rate": 0.51,
            "overall_win_rate_quality": q_syn, "provenance": prov,
            "base_stats": {"attackrange": rng, "hp": 600, "armor": 28, "spellblock": 30},
        }
    role_stats = []
    for cid, role, wr, n in [(51, "BOTTOM", 0.52, 5000), (67, "BOTTOM", 0.50, 4000),
                             (103, "MIDDLE", 0.515, 6000), (238, "MIDDLE", 0.49, 5000),
                             (412, "UTILITY", 0.51, 7000), (54, "TOP", 0.52, 4000),
                             (84, "MIDDLE", 0.48, 3000), (64, "JUNGLE", 0.49, 5000),
                             (22, "BOTTOM", 0.53, 3000), (99, "UTILITY", 0.50, 4000)]:
        role_stats.append({
            "schema_version": "1.0", "champion_id": cid, "role": role,
            "patch": "16.23", "queue": "RANKED_SOLO", "region": "ALL",
            "rank_scope": "EMERALD_PLUS",
            "stats": {"win_rate": wr, "pick_rate": 0.1, "ban_rate": 0.05,
                      "role_play_rate": 0.8, "sample_size": n},
            "provenance": prov, "quality": q_obs, "metric_scope": "ROLE_SPECIFIC",
        })
    matchups = []
    for cid, crole, oid, orole, wr, n, rel in [
        (51, "BOTTOM", 67, "BOTTOM", 0.481, 1341, "SAME_LANE"),
        (67, "BOTTOM", 51, "BOTTOM", 0.519, 1341, "SAME_LANE"),
        (103, "MIDDLE", 238, "MIDDLE", 0.53, 2000, "SAME_LANE"),
        (238, "MIDDLE", 103, "MIDDLE", 0.47, 2000, "SAME_LANE"),
        (51, "BOTTOM", 103, "MIDDLE", 0.50, 300, "CROSS_TEAM"),
    ]:
        matchups.append({
            "schema_version": "1.0", "champion_id": cid, "champion_role": crole,
            "opponent_id": oid, "opponent_role": orole, "relation_type": rel,
            "patch": "16.23", "region": "ALL", "rank_scope": "EMERALD_PLUS",
            "queue": "RANKED_SOLO", "sample_size": n, "observed_win_rate": wr,
            "expected_win_rate": None, "adjusted_matchup_delta": None,
            "lane_gold_diff_15": 563 if cid == 51 and oid == 67 else None,
            "lane_cs_diff_15": None, "lane_xp_diff_15": None,
            "confidence_interval": None, "legacy_derived_score": None,
            "provenance": prov, "quality": q_obs,
        })
    synergies = [{
        "schema_version": "1.0", "champion_id": 51, "champion_role": "BOTTOM",
        "ally_id": 412, "ally_role": "UTILITY", "patch": "16.23",
        "region": "ALL", "rank_scope": "EMERALD_PLUS", "sample_size": 800,
        "observed_win_rate": 0.55, "expected_win_rate": None, "synergy_delta": None,
        "pick_together_rate": 0.04, "legacy_derived_score": None,
        "provenance": prov, "quality": q_obs,
    }]
    mechanics = {}
    for cid, c in champs.items():
        mechanics[cid] = {
            "schema_version": "1.0", "champion_id": int(cid), "patch": "16.23",
            "features": {
                "attack_range": {"value": c["base_stats"]["attackrange"], "unit": "GAME_UNITS",
                                 "source": "synthetic_fixture",
                                 "validation_status": "mechanically_verified", "derived_from": []},
                "damage_ap": {"value": 2 if "Marksman" in c["tags"] else 8, "unit": "SCORE_0_10",
                              "source": "synthetic_fixture", "validation_status": "pending", "derived_from": []},
                "damage_ad": {"value": 8 if "Marksman" in c["tags"] else 2, "unit": "SCORE_0_10",
                              "source": "synthetic_fixture", "validation_status": "pending", "derived_from": []},
                "mobility": {"value": 6 if "Assassin" in c["tags"] else 2, "unit": "SCORE_0_10",
                             "source": "synthetic_fixture", "validation_status": "pending", "derived_from": []},
                "hard_cc": {"value": 6 if cid in ("412", "54") else 1, "unit": "SCORE_0_10",
                            "source": "synthetic_fixture", "validation_status": "pending", "derived_from": []},
                "engage": {"value": 7 if cid in ("412", "54") else 2, "unit": "SCORE_0_10",
                           "source": "synthetic_fixture", "validation_status": "pending", "derived_from": []},
                "frontline": {"value": 8 if cid == "54" else 2, "unit": "SCORE_0_10",
                              "source": "synthetic_fixture", "validation_status": "pending", "derived_from": []},
                "sustain": {"value": 4 if cid == "412" else 1, "unit": "SCORE_0_10",
                            "source": "synthetic_fixture", "validation_status": "pending", "derived_from": []},
                "poke": {"value": 6 if cid in ("51", "99") else 1, "unit": "SCORE_0_10",
                         "source": "synthetic_fixture", "validation_status": "pending", "derived_from": []},
                "soft_cc": {"value": 4, "unit": "SCORE_0_10", "source": "synthetic_fixture",
                            "validation_status": "pending", "derived_from": []},
                "waveclear": {"value": 5, "unit": "SCORE_0_10", "source": "synthetic_fixture",
                              "validation_status": "pending", "derived_from": []},
                "anti_mobility": {"value": 0, "unit": "SCORE_0_10", "source": "synthetic_fixture",
                                  "validation_status": "pending", "derived_from": []},
                "true_damage": {"value": 3 if cid == "67" else 0, "unit": "SCORE_0_10",
                                "source": "synthetic_fixture", "validation_status": "pending", "derived_from": []},
            },
            "provenance": prov,
        }
    return {
        "champions.json": champs,
        "champion_role_stats.json": role_stats,
        "matchups.json": matchups,
        "synergies.json": synergies,
        "builds.json": [],
        "champion_mechanics.json": mechanics,
    }


@pytest.fixture()
def mini_store(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    files = _mini_files()
    manifest = {
        "schema_version": "1.0", "dataset_id": "ds-mini-synthetic",
        "status": "validated", "game": "LEAGUE_OF_LEGENDS", "patch": "16.23",
        "generated_at": "2026-11-18T00:00:00+00:00",
        "sources": [{"provider": "synthetic_fixture", "status": "ok"}],
        "coverage": {"champions": 10, "champion_roles": 10, "matchups": 5, "synergies": 1},
        "quality": {"validation_passed": True, "warnings": ["SYNTHETIC TEST FIXTURE"],
                    "missing_segments": []},
    }
    store.publish(files, manifest, {"run_id": "fixture"})
    return store


@pytest.fixture()
def mini_ds(mini_store):
    return mini_store.latest()


@pytest.fixture()
def mini_cfg(tmp_path):
    c = Config()
    c.datasets_dir = tmp_path / "datasets"
    c.game_rules_dir = tmp_path / "game_rules"
    c.engine.mc_samples = 32
    c.engine.beam_candidates = 6
    c.engine.time_budget_s = 5.0
    return c
