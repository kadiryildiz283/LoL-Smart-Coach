"""Mock-based rule discovery pipeline test (§19: mock/fixture provider tests).

Proves the full path without depending on live LLM mood:
LLM proposal -> schema gate -> registry -> mechanical verification -> dedup.
Mock output is explicitly labeled; never presented as production data.
"""
import json

import pytest

from engine.knowledge.rules.registry import RuleRegistry
from engine.knowledge.rules import discovery
from engine.llm.client import Endpoint


CANNED_PROPOSALS = [
    {
        "rule_type": "strategic",
        "title": "Caitlyn menzil baskısı (mock)",
        "subject": {"champion": "Caitlyn", "role": "BOTTOM"},
        "target": {"champion": "Vayne", "role": "BOTTOM"},
        "relation": "LANE_PRESSURE_ADVANTAGE",
        "game_phase": "EARLY",
        "claim": "Caitlyn 650 menzil ile Vayne 550 menzile karşı erken baskı kurabilir.",
        "conditions": ["Her ikisi BOTTOM"], "exceptions": ["Rakip all-in"],
        "impact_category": "LANING",
    },
    {
        "rule_type": "strategic",
        "title": "SAHTE menzil iddiası (mock)",
        "subject": {"champion": "Vayne", "role": "BOTTOM"},
        "target": {"champion": "Caitlyn", "role": "BOTTOM"},
        "relation": "LANE_PRESSURE_ADVANTAGE",
        "game_phase": "EARLY",
        "claim": "Vayne, Caitlyn'den daha uzun menzile sahiptir.",
        "conditions": [], "exceptions": [],
        "impact_category": "LANING",
    },
]


@pytest.fixture()
def mock_llm(monkeypatch):
    calls = {"n": 0}

    def fake_status(self):
        return {"available": True, "kind": "openai",
                "base_url": "http://mock", "model": "qwen3.8:27b"}

    def fake_post(url, payload, timeout):
        calls["n"] += 1
        return {"choices": [{"message": {"content": json.dumps(CANNED_PROPOSALS)}}]}

    from engine.llm import client as client_mod
    from engine.llm.client import LLMClient
    monkeypatch.setattr(LLMClient, "status", fake_status)
    monkeypatch.setattr(LLMClient, "endpoint",
                        property(lambda self: Endpoint("openai", "http://mock",
                                                       "qwen3.8:27b", ["qwen3.8:27b"])))
    monkeypatch.setattr(client_mod, "_post_json", fake_post)
    return calls


def test_discovery_full_path_mock(mini_ds, mini_cfg, mock_llm):
    reg = RuleRegistry(mini_cfg.game_rules_dir)
    rep = discovery.discover_rules(mini_cfg, mini_ds, reg, pairs=[(51, 67)])
    assert rep["proposals"] == 2
    assert rep["created"] == 2
    assert rep["verified"] == 1   # true range claim mechanically verified
    assert rep["rejected"] == 1   # false range claim rejected by game data
    rules = reg.all()
    verified = [r for r in rules if r["status"] == "verified"
                and r["subject"].get("champion_id") == 51]
    rejected = [r for r in rules if r["status"] == "rejected"]
    assert verified and rejected
    assert verified[0]["provenance"]["generation_type"] == "llm_proposal"
    # unverified proposals never auto-active
    assert all(r["status"] != "active" for r in rules)


def test_discovery_idempotent_mock(mini_ds, mini_cfg, mock_llm):
    reg = RuleRegistry(mini_cfg.game_rules_dir)
    r1 = discovery.discover_rules(mini_cfg, mini_ds, reg, pairs=[(51, 67)])
    n_after_first = len(reg.all())
    r2 = discovery.discover_rules(mini_cfg, mini_ds, reg, pairs=[(51, 67)])
    assert r2["skipped_unchanged"] == 1  # evidence hash unchanged -> no LLM call
    assert len(reg.all()) == n_after_first
    assert mock_llm["n"] == 1  # second run made NO LLM request


def test_discovery_bad_json_preserves_rules(mini_ds, mini_cfg, monkeypatch):
    reg = RuleRegistry(mini_cfg.game_rules_dir)
    from engine.llm.client import LLMClient, Endpoint
    monkeypatch.setattr(LLMClient, "status", lambda self: {
        "available": True, "kind": "openai", "base_url": "http://mock", "model": "qwen3.8:27b"})
    monkeypatch.setattr(LLMClient, "endpoint",
                        property(lambda self: Endpoint("openai", "http://mock",
                                                       "qwen3.8:27b", [])))
    from engine.llm import client as client_mod
    monkeypatch.setattr(client_mod, "_post_json",
                        lambda url, payload, timeout: {"choices": [{"message": {"content": "BOZUK {{{"}}]})
    rep = discovery.discover_rules(mini_cfg, mini_ds, reg, pairs=[(51, 67)])
    assert rep["created"] == 0
    assert rep["errors"]  # parse error reported, old rules untouched
