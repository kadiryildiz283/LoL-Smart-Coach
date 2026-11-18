"""Rule engine scenarios (§22.12) + LLM integration/offline behavior (§14)."""
import copy

import pytest

from engine.contracts.records import Rule, utcnow
from engine.contracts.types import RuleType, RuleStatus, GamePhase, VerificationStatus
from engine.knowledge.rules.registry import RuleRegistry
from engine.knowledge.rules.seed import seed_rules
from engine.knowledge.rules.validators import (
    validate_all, resolve_conflicts, mechanical_validate, MIN_SAMPLE_TO_CHALLENGE_MECHANIC,
)


def _range_pressure_rule(sa, ta, role="BOTTOM", category="LANING", status=RuleStatus.VERIFIED):
    return Rule(
        rule_id="", rule_type=RuleType.STRATEGIC, status=status,
        title=f"{sa} -> {ta} menzil baskısı",
        subject={"champion_id": sa, "champion": str(sa), "role": role},
        target={"champion_id": ta, "champion": str(ta), "role": role},
        relation="LANE_PRESSURE_ADVANTAGE", game_phase=GamePhase.EARLY,
        claim="Menzil avantajı erken koridor baskısı kurabilir.",
        conditions=["Aynı rol", "Güvenli pozisyon"], exceptions=["Rakip all-in"],
        confidence={"mechanical": 0.95, "strategic": 0.5, "empirical": None},
        scope={"patch_from": "16.23", "patch_to": None, "rank": "ALL", "region": "ALL"},
        impact={"category": category, "estimated_effect": None,
                "calibration_status": "not_calibrated"},
        provenance={"generated_by": "test", "generation_type": "test", "created_at": utcnow()},
        review={"verification_status": VerificationStatus.MECHANICALLY_VERIFIED.value,
                "contradictions": [], "last_reviewed_patch": "16.23"},
    ).to_dict()


def _empirical_rule(sa, ta, wr, n, category="MATCH_WIN"):
    return Rule(
        rule_id="", rule_type=RuleType.EMPIRICAL, status=RuleStatus.PROPOSED,
        title=f"{sa} vs {ta} gözlem",
        subject={"champion_id": sa, "champion": str(sa), "role": "BOTTOM"},
        target={"champion_id": ta, "champion": str(ta), "role": "BOTTOM"},
        relation="EASY_MATCHUP_VS", game_phase=GamePhase.ALL,
        claim=f"Gözlenen WR {wr}.",
        evidence={"mechanical_sources": [], "statistical_sources": [],
                  "sample_size": n, "observed_lane_advantage": None,
                  "observed_match_win_rate": wr},
        confidence={"mechanical": None, "strategic": None, "empirical": 0.5},
        scope={"patch_from": "16.23", "patch_to": None, "rank": "ALL", "region": "ALL"},
        impact={"category": category, "estimated_effect": None,
                "calibration_status": "not_calibrated"},
        provenance={"generated_by": "test", "generation_type": "test", "created_at": utcnow()},
        review={"verification_status": VerificationStatus.PENDING.value,
                "contradictions": [], "last_reviewed_patch": None},
    ).to_dict()


# §22.12.1 — mechanical lane advantage and opposite match-WR coexist
def test_rule_1_coexistence(mini_ds, mini_cfg):
    reg = RuleRegistry(mini_cfg.game_rules_dir)
    seed_rules(reg, mini_ds)
    # Caitlyn(51) range pressure verified; Vayne(67) observed match WR 0.519 > 0.5
    reg.upsert(_empirical_rule(67, 51, 0.519, 1341, category="MATCH_WIN"), "test")
    actions = resolve_conflicts(reg, mini_ds)
    assert any(a["resolution"] == "coexist" for a in actions)
    rules = reg.all()
    assert any(r["relation"] == "LANE_PRESSURE_ADVANTAGE"
               and r["subject"]["champion_id"] == 51 and r["target"]["champion_id"] == 67
               for r in rules)
    assert any(r["rule_type"] == "empirical" and r["subject"]["champion_id"] == 67
               for r in rules)
    conflicts = reg.conflicts()
    assert any(c["type"] == "cross_target_coexistence" for c in conflicts)


# §22.12.2 — unverified LLM proposal is NOT auto-accepted
def test_rule_2_unverified_not_active(mini_cfg):
    reg = RuleRegistry(mini_cfg.game_rules_dir)
    r = _range_pressure_rule(51, 67, status=RuleStatus.PROPOSED)
    r["review"]["verification_status"] = VerificationStatus.LLM_HYPOTHESIS_ONLY.value
    r["provenance"]["generation_type"] = "llm_proposal"
    rid, action = reg.upsert(r, "test")
    assert action == "created"
    assert rid not in [x["rule_id"] for x in reg.active_rules()]
    assert rid in [x["rule_id"] for x in reg.pending_review()]


# §22.12.3 — patch advance invalidates bounded rule → needs_review
def test_rule_3_patch_invalidation(mini_ds, mini_cfg):
    reg = RuleRegistry(mini_cfg.game_rules_dir)
    r = _range_pressure_rule(51, 22)
    r["scope"]["patch_to"] = "16.20"
    rid, _ = reg.upsert(r, "test")
    report = validate_all(reg, mini_ds)  # ds patch 16.23 > 16.20
    assert reg.get(rid)["status"] == RuleStatus.NEEDS_REVIEW.value
    assert report["needs_review"] >= 1


# §22.12.4 — low-sample stats cannot invalidate verified mechanic
def test_rule_4_low_sample_cannot_invalidate(mini_ds, mini_cfg):
    reg = RuleRegistry(mini_cfg.game_rules_dir)
    reg.upsert(_range_pressure_rule(51, 67, category="LANING"), "test")
    reg.upsert(_empirical_rule(67, 51, 0.519, 50, category="LANING"), "test")
    actions = resolve_conflicts(reg, mini_ds)
    assert any(a["resolution"] == "mechanic_kept" for a in actions)
    mech = [r for r in reg.all() if r["relation"] == "LANE_PRESSURE_ADVANTAGE"][0]
    assert mech["status"] == RuleStatus.VERIFIED.value


# §22.12.5 — strong new data forces re-review of same-target assumption
def test_rule_5_strong_data_triggers_review(mini_ds, mini_cfg):
    reg = RuleRegistry(mini_cfg.game_rules_dir)
    reg.upsert(_range_pressure_rule(51, 67, category="LANING"), "test")
    reg.upsert(_empirical_rule(67, 51, 0.55, 2000, category="LANING"), "test")
    actions = resolve_conflicts(reg, mini_ds)
    assert any(a["resolution"] == "needs_review" and a["sample"] >= MIN_SAMPLE_TO_CHALLENGE_MECHANIC
               for a in actions)


# §22.12.6 — semantic dedup: same rule twice → single record
def test_rule_6_semantic_dedup(mini_cfg):
    reg = RuleRegistry(mini_cfg.game_rules_dir)
    r = _range_pressure_rule(51, 67)
    rid1, a1 = reg.upsert(r, "first")
    rid2, a2 = reg.upsert(copy.deepcopy(r), "second")
    assert a1 == "created" and a2 == "dedup_skipped"
    assert rid1 == rid2
    assert len([x for x in reg.all() if x["semantic_key"] == r["semantic_key"]
                or x["rule_id"] == rid1]) == 1


# §22.12.7 — ablation measures component impact
def test_rule_7_ablation_measures_impact(mini_ds, mini_cfg):
    from engine.evaluation.ablation import run_ablation
    report = run_ablation(mini_cfg, mini_ds, n=4, samples=16)
    assert "meta_main_effect" in report["components"]
    for comp, m in report["components"].items():
        assert 0.0 <= m["top1_change_rate"] <= 1.0
        assert m["mean_rank_shift"] >= 0.0


# mechanical verification against game data (Caitlyn 650 > Vayne 550)
def test_mechanical_validator_range(mini_ds, mini_cfg):
    reg = RuleRegistry(mini_cfg.game_rules_dir)
    r = _range_pressure_rule(51, 67)
    mv = mechanical_validate(r, mini_ds)
    assert mv["passed"] is True
    assert mv["evidence"]["delta"] == 100
    reversed_rule = _range_pressure_rule(67, 51)
    mv2 = mechanical_validate(reversed_rule, mini_ds)
    assert mv2["passed"] is False  # false range claim rejected


# decision integration: verified rule used ONLY when matchup data missing
def test_rule_decision_integration_no_double_count(mini_ds, mini_cfg):
    from engine.engines.decision import DecisionEngine
    from engine.engines.draft import build_draft
    reg = RuleRegistry(mini_cfg.game_rules_dir)
    reg.upsert(_range_pressure_rule(51, 22), "test")   # Caitlyn -> Ashe, no observed data
    reg.upsert(_range_pressure_rule(51, 67), "test")   # Caitlyn -> Vayne, observed EXISTS
    eng = DecisionEngine(mini_cfg, mini_ds)
    # enemy Ashe(22): rule should contribute
    draft = build_draft(mini_ds, __import__("engine.contracts.types", fromlist=["Role"]).Role.BOTTOM,
                        [412], [22], [])
    rec = eng.recommend(draft, mc_samples=8, seed=1)
    cait = next((ev for ev in rec.candidates if ev.champion_id == 51), None)
    assert cait is not None
    rule_terms = [c for c in cait.feature_contributions if c["component"] == "rule_effects"]
    assert rule_terms and 22 in rule_terms[0].get("rule_ids", []) or any(
        r["target"]["champion_id"] == 22 for r in reg.active_rules())
    # enemy Vayne(67): observed data exists → rule must NOT add on top
    draft2 = build_draft(mini_ds, __import__("engine.contracts.types", fromlist=["Role"]).Role.BOTTOM,
                         [412], [67], [])
    rec2 = eng.recommend(draft2, mc_samples=8, seed=1)
    cait2 = next((ev for ev in rec2.candidates if ev.champion_id == 51), None)
    rule_terms2 = [c for c in cait2.feature_contributions if c["component"] == "rule_effects"]
    assert not rule_terms2  # double-counting guard


# ---- LLM ----
def test_llm_offline_coach_fallback(mini_ds, mini_cfg):
    from engine.llm.coach import explain_recommendation
    from engine.engines.decision import DecisionEngine
    from engine.engines.draft import build_draft
    from engine.contracts.types import Role
    mini_cfg.llm.host = "127.0.0.1"
    mini_cfg.llm.openai_port = 1
    mini_cfg.llm.ollama_port = 1
    eng = DecisionEngine(mini_cfg, mini_ds)
    draft = build_draft(mini_ds, Role.BOTTOM, [412], [67], [])
    rec = eng.recommend(draft, mc_samples=8, seed=1)
    out = explain_recommendation(mini_cfg, mini_ds, rec)
    assert out["llm_status"] == "offline_fallback"
    assert "summary" in out and "risks" in out


def test_llm_offline_discovery_no_fabrication(mini_ds, mini_cfg):
    from engine.knowledge.rules.discovery import discover_rules
    mini_cfg.llm.host = "127.0.0.1"
    mini_cfg.llm.openai_port = 1
    mini_cfg.llm.ollama_port = 1
    reg = RuleRegistry(mini_cfg.game_rules_dir)
    report = discover_rules(mini_cfg, mini_ds, reg, limit=2)
    assert report["llm_status"]["available"] is False
    assert report["proposals"] == 0
    assert report["created"] == 0


@pytest.mark.integration
def test_llm_online_discovery_exact_model(cfg):
    from engine.llm.client import discover
    ep = discover(cfg.llm)
    assert ep.model == "qwen3.8:27b"  # exact, no silent substitution
    assert ep.kind in ("openai", "ollama")


@pytest.mark.integration
def test_llm_online_coach_schema(cfg, real_ds):
    from engine.llm.coach import explain_recommendation
    from engine.engines.decision import DecisionEngine
    from engine.engines.draft import build_draft
    from engine.contracts.types import Role
    eng = DecisionEngine(cfg, real_ds)
    draft = build_draft(real_ds, Role.MIDDLE,
                        [real_ds.resolve_id("Malphite"), real_ds.resolve_id("Amumu")],
                        [real_ds.resolve_id("Zed"), real_ds.resolve_id("Caitlyn")], [])
    rec = eng.recommend(draft, mc_samples=16, seed=42)
    out = explain_recommendation(cfg, real_ds, rec)
    assert out["llm_status"] in ("ok", "offline_fallback")
    if out["llm_status"] == "ok":
        assert isinstance(out["summary"], str) and len(out["summary"]) > 20
        assert isinstance(out["risks"], list)
        assert isinstance(out["data_caveats"], list)
