"""Mandatory draft scenarios (§18) on the real published dataset."""
import pytest

from engine.contracts.types import Role, ALL_ROLES, RelationType
from engine.engines.decision import DecisionEngine
from engine.engines.draft import build_draft, DraftError, future_steps
from engine.engines.role_inference import RoleInferenceEngine
from engine.engines.meta import MetaEngine
from engine.stats import expected_matchup_wr, shrink_win_rate, wilson_interval, cvar


@pytest.fixture(scope="module")
def engine(real_ds, cfg):
    return DecisionEngine(cfg, real_ds)


def ids(ds, names):
    out = [ds.resolve_id(n) for n in names]
    assert all(x is not None for x in out), f"unknown champion in {names}"
    return out


# 1. Dokuz şampiyon belli, son seçim bizde
def test_scenario_a_nine_known(engine, real_ds):
    ally = ids(real_ds, ["Malphite", "Amumu", "Kai'Sa", "Nautilus"])
    enemy = ids(real_ds, ["Jayce", "Kha'Zix", "Zed", "Caitlyn", "Lux"])
    bans = ids(real_ds, ["Yasuo", "Yone"])
    draft = build_draft(real_ds, Role.MIDDLE, ally, enemy, bans)
    rec = engine.recommend(draft, mc_samples=32, seed=42)
    assert rec.recommended_champion_id is not None
    assert rec.recommended_champion_id not in bans + ally + enemy
    assert rec.recommended_role == Role.MIDDLE
    assert not future_steps(draft)  # complete draft


# 2. Üç arkadaş + üç rakip, sıra bizde → gelecek simülasyonu
def test_scenario_b_partial_future(engine, real_ds):
    ally = ids(real_ds, ["Malphite", "Amumu", "Kai'Sa"])
    enemy = ids(real_ds, ["Jayce", "Kha'Zix", "Zed"])
    draft = build_draft(real_ds, Role.MIDDLE, ally, enemy, [])
    assert future_steps(draft)
    rec = engine.recommend(draft, mc_samples=32, seed=42)
    best = rec.candidates[0]
    assert best.expected_future_draft_value is not None
    assert best.mc_standard_error is not None
    assert best.downside_risk is not None


# 3. Blind pick
def test_scenario_c_blind(engine, real_ds):
    draft = build_draft(real_ds, Role.BOTTOM, ids(real_ds, ["Thresh"]),
                        ids(real_ds, ["Caitlyn"]), [])
    rec = engine.recommend(draft, mc_samples=32, seed=42)
    assert rec.recommended_champion_id is not None
    assert rec.risk["role_uncertainty"] is not None


# 4. Flex pick: joint distribution, not independent forced assignment
def test_scenario_d_flex_joint(real_ds, cfg):
    meta = MetaEngine(cfg, real_ds)
    ri = RoleInferenceEngine(cfg, real_ds, meta)
    # Pantheon flex (TOP/JUNGLE/MIDDLE/SUPPORT historically); use a known flex id
    flex = real_ds.resolve_id("Pantheon")
    if flex is None:
        pytest.skip("Pantheon not in dataset")
    cait = real_ds.resolve_id("Caitlyn")
    # flex + one locked BOTTOM: flex keeps multiple plausible roles (joint, not forced)
    dist = ri.infer([(flex, None), (cait, Role.BOTTOM)])
    total = sum(p for _, p in dist.joints)
    assert abs(total - 1.0) < 1e-6
    assert len(dist.marginals[flex]) >= 2
    assert dist.uncertainty > 0.0
    # partially locked teammates: flex distribution narrows but stays joint
    partial = ri.infer([(flex, None), (cait, Role.BOTTOM),
                        (real_ds.resolve_id("Thresh"), Role.UTILITY)])
    assert abs(sum(p for _, p in partial.joints) - 1.0) < 1e-6
    assert set(partial.marginals[flex]) <= {"TOP", "JUNGLE", "MIDDLE"}
    # over-constrained teams degrade gracefully, never crash
    over = ri.infer([(cait, Role.BOTTOM), (real_ds.resolve_id("Kai'Sa"), Role.BOTTOM)])
    assert over.marginals  # fallback marginals produced
    over2 = ri.infer([(flex, None), (cait, Role.BOTTOM),
                      (real_ds.resolve_id("Thresh"), Role.UTILITY),
                      (real_ds.resolve_id("Lee Sin"), Role.JUNGLE),
                      (real_ds.resolve_id("Malphite"), Role.TOP)])
    assert over2.marginals  # no valid assignment left -> fallback, not exception


# 5. Known enemy role concentrates marginal
def test_scenario_e_known_role(real_ds, cfg):
    meta = MetaEngine(cfg, real_ds)
    ri = RoleInferenceEngine(cfg, real_ds, meta)
    zed = real_ds.resolve_id("Zed")
    dist = ri.infer([(zed, Role.MIDDLE)])
    assert dist.role_prob(zed, Role.MIDDLE) == pytest.approx(1.0)


# 6. Banned/picked never recommended; duplicates rejected
def test_scenario_f_bans_and_duplicates(engine, real_ds):
    ally = ids(real_ds, ["Malphite", "Amumu", "Kai'Sa", "Nautilus"])
    enemy = ids(real_ds, ["Jayce", "Kha'Zix", "Zed", "Caitlyn", "Lux"])
    bans = ids(real_ds, ["Yasuo", "Yone", "Ahri", "Akali"])
    draft = build_draft(real_ds, Role.MIDDLE, ally, enemy, bans)
    rec = engine.recommend(draft, mc_samples=16, seed=42)
    forbidden = set(bans + ally + enemy)
    assert all(ev.champion_id not in forbidden for ev in rec.candidates)
    with pytest.raises(DraftError):
        build_draft(real_ds, Role.MIDDLE, ally, enemy + [ally[0]], bans)


# 7. New patch / thin data → flagged fallback, low confidence
def test_scenario_g_thin_data_fallback(mini_ds, mini_cfg):
    eng = DecisionEngine(mini_cfg, mini_ds)
    # champion 99 (Lux) has UTILITY stats only; ask MIDDLE → fallback
    s = eng.meta.role_strength(99, Role.MIDDLE)
    assert s["fallback"] is True
    assert s["confidence"] <= 0.6


# 8. Low sample → lower confidence than high sample
def test_scenario_h_sample_confidence():
    lo = wilson_interval(5, 10)
    hi = wilson_interval(500, 1000)
    assert (lo.upper - lo.lower) > (hi.upper - hi.lower)
    est_lo, fb_lo = shrink_win_rate(0.8, 5, 0.5, 30)
    est_hi, fb_hi = shrink_win_rate(0.8, 5000, 0.5, 30)
    assert abs(est_lo - 0.5) < abs(est_hi - 0.5)  # shrunk toward prior
    assert not fb_lo and not fb_hi
    _, fb_missing = shrink_win_rate(None, None, 0.5, 30)
    assert fb_missing  # no data → explicit fallback


# 11. Rank/region filter separation is enforced at contract level (see contracts test)


# 12. LLM off → decision engine fully functional
def test_scenario_l_llm_offline_engine_works(engine, real_ds):
    draft = build_draft(real_ds, Role.MIDDLE, ids(real_ds, ["Malphite"]),
                        ids(real_ds, ["Zed"]), [])
    rec = engine.recommend(draft, mc_samples=16, seed=42)
    assert rec.status.startswith("evaluated")
    assert rec.llm_explanation is None  # numeric path never needs LLM


# 13. Composition need vs raw strength: mono-AD team rewards AP candidate
def test_scenario_m_composition_marginal(real_ds, cfg):
    from engine.engines.composition import CompositionEngine
    comp = CompositionEngine(cfg, real_ds)
    # all-AD allies
    allies = [(real_ds.resolve_id(n), Role.TOP) for n in ["Malphite", "Amumu", "Kai'Sa", "Nautilus"]]
    ap_cand = real_ds.resolve_id("Ahri")
    ad_cand = real_ds.resolve_id("Ashe")
    fit_ap = comp.marginal_fit(ap_cand, allies)
    fit_ad = comp.marginal_fit(ad_cand, allies)
    bal_ap = next((c["logodds"] for c in fit_ap["contributions"]
                   if c["dimension"] == "damage_balance"), 0.0)
    bal_ad = next((c["logodds"] for c in fit_ad["contributions"]
                   if c["dimension"] == "damage_balance"), 0.0)
    assert bal_ap >= bal_ad  # AP fills the gap at least as well


# 14. Lane-strong but team-weak: threat and lane signals can oppose
def test_scenario_n_lane_vs_team_threat(engine, real_ds):
    from engine.engines.threat import ThreatEngine
    thr = ThreatEngine(engine.cfg, real_ds)
    # melee lane bully into heavy dive/poke team
    cand = real_ds.resolve_id("Darius") or real_ds.resolve_id("Garen")
    if cand is None:
        pytest.skip("no melee test champion")
    enemies = [(real_ds.resolve_id(n), r) for n, r in
               [("Jayce", Role.TOP), ("Kha'Zix", Role.JUNGLE), ("Zed", Role.MIDDLE),
                ("Caitlyn", Role.BOTTOM), ("Lux", Role.UTILITY)]]
    exposure = thr.exposure(cand, enemies)
    assert exposure["logodds"] <= 0.0  # threat is a penalty, never a bonus
    assert exposure["components"]


# 15. Future counter risk: downside below expectation
def test_scenario_o_downside_risk(engine, real_ds):
    ally = ids(real_ds, ["Malphite", "Amumu", "Kai'Sa"])
    enemy = ids(real_ds, ["Jayce", "Kha'Zix", "Zed"])
    draft = build_draft(real_ds, Role.MIDDLE, ally, enemy, [])
    rec = engine.recommend(draft, mc_samples=48, seed=42)
    best = rec.candidates[0]
    assert best.downside_risk <= best.expected_future_draft_value + 1e-9


# 16. Pick order changes future steps
def test_scenario_p_order_matters(real_ds):
    ally = ids(real_ds, ["Malphite", "Amumu"])
    enemy = ids(real_ds, ["Jayce", "Kha'Zix"])
    d1 = build_draft(real_ds, Role.MIDDLE, ally, enemy, [])
    d2 = build_draft(real_ds, Role.MIDDLE, ally, enemy, [])
    d2.current_step = 6  # earlier pick → more future steps
    assert len(future_steps(d2)) >= len(future_steps(d1))


# 18. Multi-role champion plausible in >1 role
def test_scenario_r_multi_role(real_ds, cfg):
    meta = MetaEngine(cfg, real_ds)
    ri = RoleInferenceEngine(cfg, real_ds, meta)
    multi = [cid for cid in real_ds.champions
             if len(ri.plausible_roles(cid)) > 1]
    assert len(multi) > 10


# 19. Metric definitions stay distinct (units + metric names)
def test_scenario_s_metric_separation(engine, real_ds):
    d = engine.matchup.delta(51, Role.BOTTOM, 67, Role.BOTTOM, RelationType.SAME_LANE)
    if d["evidence"]:
        assert d["evidence"].unit in ("LOG_ODDS", "SCORE")
        assert d["evidence"].metric in ("MATCHUP_DELTA_LOGODDS", "LEGACY_MATCHUP_SCORE")


# 20. Determinism: same data + seed → identical result
def test_scenario_t_determinism(engine, real_ds):
    ally = ids(real_ds, ["Malphite", "Amumu", "Kai'Sa"])
    enemy = ids(real_ds, ["Jayce", "Kha'Zix", "Zed"])
    draft = build_draft(real_ds, Role.MIDDLE, ally, enemy, [])
    r1 = engine.recommend(draft, mc_samples=32, seed=42)
    r2 = engine.recommend(draft, mc_samples=32, seed=42)
    assert r1.recommended_champion_id == r2.recommended_champion_id
    assert r1.ranking_score == r2.ranking_score
    assert [c.champion_id for c in r1.candidates] == [c.champion_id for c in r2.candidates]


# §8 core math: expected vs observed, no double counting
def test_matchup_expectation_math():
    assert expected_matchup_wr(0.5, 0.5) == pytest.approx(0.5, abs=1e-6)
    assert expected_matchup_wr(0.55, 0.45) > 0.5
    # delta is orthogonal to main effects by construction
    from engine.stats import logit
    obs, wa, wb = 0.54, 0.52, 0.50
    delta = logit(obs) - logit(expected_matchup_wr(wa, wb))
    assert delta != logit(obs)  # not the raw WR


def test_cvar_downside():
    vals = [0.4, 0.5, 0.6, 0.3, 0.55]
    assert cvar(vals, 0.2) == pytest.approx(0.3)