"""Seed rules: verified mechanical facts + strategic hypothesis families.

Range facts are derived from Data Dragon (mechanically verified, single record
per champion — §22.10). Pairwise lane-pressure rules are conditional strategic
claims, NOT win guarantees. General principles enter as PROPOSED hypotheses
to be tested against data, never as pre-accepted universal truths (§22.11).
"""
from __future__ import annotations

from engine.contracts.records import Rule, utcnow
from engine.contracts.types import RuleType, RuleStatus, GamePhase, VerificationStatus
from engine.data.store import Dataset
from engine.knowledge.rules.registry import RuleRegistry

MIN_RANGE_DELTA = 100


def seed_rules(registry: RuleRegistry, ds: Dataset) -> int:
    count = 0
    patch = ds.manifest.get("patch", "unknown")

    # 1) single verified range fact per champion
    for cid, mech in ds.mechanics.items():
        rng = mech.get("features", {}).get("attack_range", {})
        if rng.get("value") is None:
            continue
        champ = ds.champions.get(cid, {})
        rule = Rule(
            rule_id="", rule_type=RuleType.MECHANIC, status=RuleStatus.VERIFIED,
            title=f"{champ.get('name', cid)} temel saldırı menzili",
            subject={"champion_id": cid, "champion": champ.get("name")},
            target={"champion_id": cid, "champion": champ.get("name")},
            relation="ATTACK_RANGE",
            claim=f"{champ.get('name', cid)} temel saldırı menzili {rng['value']} birimdir.",
            evidence={"mechanical_sources": [{"source": "data_dragon", "field": "stats.attackrange",
                                               "value": rng["value"]}],
                      "statistical_sources": [], "sample_size": None,
                      "observed_lane_advantage": None, "observed_match_win_rate": None},
            confidence={"mechanical": 0.95, "strategic": None, "empirical": None},
            scope={"patch_from": patch, "patch_to": None, "rank": "ALL", "region": "ALL"},
            impact={"category": "MECHANIC_FACT", "estimated_effect": None,
                    "calibration_status": "verified_fact"},
            provenance={"generated_by": "knowledge_engine", "generation_type": "data_derived",
                        "created_at": utcnow()},
            review={"verification_status": VerificationStatus.MECHANICALLY_VERIFIED.value,
                    "contradictions": [], "last_reviewed_patch": patch},
        ).to_dict()
        _, action = registry.upsert(rule, "seed_range_fact")
        count += int(action != "dedup_skipped")

    # 2) conditional lane-pressure rules for significant range advantages
    ranges = {cid: m.get("features", {}).get("attack_range", {}).get("value")
              for cid, m in ds.mechanics.items()}
    roles_by_champ = {cid: set(ds.champions.get(cid, {}).get("roles") or []) for cid in ranges}
    for a, ra in ranges.items():
        if ra is None:
            continue
        for b, rb in ranges.items():
            if a == b or rb is None or ra - rb < MIN_RANGE_DELTA:
                continue
            shared = roles_by_champ.get(a, set()) & roles_by_champ.get(b, set())
            if not shared:
                continue
            role = sorted(shared)[0]
            ca, cb = ds.champions.get(a, {}), ds.champions.get(b, {})
            rule = Rule(
                rule_id="", rule_type=RuleType.STRATEGIC, status=RuleStatus.VERIFIED,
                title=f"{ca.get('name')} -> {cb.get('name')} menzil baskısı ({role})",
                subject={"champion_id": a, "champion": ca.get("name"), "role": role},
                target={"champion_id": b, "champion": cb.get("name"), "role": role},
                relation="LANE_PRESSURE_ADVANTAGE", game_phase=GamePhase.EARLY,
                claim=(f"{ca.get('name')} ({ra} menzil), {cb.get('name')} ({rb} menzil) karşısında "
                       f"uygun dalga ve pozisyon koşullarında erken koridor baskısı kurabilir."),
                conditions=[f"Her iki şampiyonun {role} rolünde oynanması",
                            "Menzil avantajını kullanacak güvenli pozisyon",
                            "Rakip destek/ormancı baskısının baskıyı etkisizleştirmemesi"],
                exceptions=["Güvenli pozisyon alınamaması", "Erken jungle müdahalesi",
                            "Rakibin güçlü all-in seviye 2-3 penceresi"],
                evidence={"mechanical_sources": [{"source": "data_dragon", "subject_range": ra,
                                                   "target_range": rb}],
                          "statistical_sources": [], "sample_size": None,
                          "observed_lane_advantage": None, "observed_match_win_rate": None},
                confidence={"mechanical": 0.95, "strategic": 0.5, "empirical": None},
                scope={"patch_from": patch, "patch_to": None, "rank": "ALL", "region": "ALL"},
                impact={"category": "LANING", "estimated_effect": None,
                        "calibration_status": "not_calibrated"},
                provenance={"generated_by": "knowledge_engine", "generation_type": "data_derived",
                            "created_at": utcnow()},
                review={"verification_status": VerificationStatus.MECHANICALLY_VERIFIED.value,
                        "contradictions": [], "last_reviewed_patch": patch},
            ).to_dict()
            _, action = registry.upsert(rule, "seed_range_pressure")
            count += int(action != "dedup_skipped")

    # 3) general strategic hypothesis families (PROPOSED — to be tested, not assumed)
    hypotheses = [
        ("range-pressure-family", "Menzil avantajı ve koridor baskısı",
         "Uzun menzilli şampiyonlar kısa menzilli rakiplerine karşı erken koridorda baskı kurabilir.",
         ["Rakip all-in tehdidi düşükken", "Dalga kontrolü menzil lehineyken"]),
        ("waveclear-priority-family", "Waveclear ve koridor önceliği",
         "Güçlü waveclear, koridor önceliği ve rotasyon avantajı sağlayabilir.",
         ["Rakip waveclear'i zayıfken", "Ormancı önceliği kullanabiliyorken"]),
        ("mobility-antimobility-family", "Mobility vs anti-mobility",
         "Dash bağımlı şampiyonlar, hareket engelleyici rakiplere karşı zorlanabilir.",
         ["Rakipte grounding/polymorph/knockup varken"]),
        ("engage-disengage-family", "Engage vs disengage",
         "Engage kompozisyonları, yetersiz disengage rakiplere karşı avantaj elde edebilir.",
         ["Rakipte peel/sustain azken", "Engage menzili rakip disengage menzilini aşıyorken"]),
        ("poke-sustain-family", "Poke vs sustain",
         "Poke kompozisyonları, sustain'i düşük rakipleri kuşatma savaşlarında yıpratabilir.",
         ["Rakip engage'i poke menzilini kapatabiliyorsa istisna"]),
        ("burst-durability-family", "Burst vs dayanıklılık",
         "Burst odaklı rakipler, dayanıklılığı düşük carryleri tehdit eder.",
         ["Carry peel altındaysa etkisi azalır"]),
    ]
    for rid, title, claim, conds in hypotheses:
        rule = Rule(
            rule_id=f"principle-{rid}", rule_type=RuleType.STRATEGIC,
            status=RuleStatus.PROPOSED, title=title,
            subject={"scope": "GENERAL"}, target={"scope": "GENERAL"},
            relation="STRATEGIC_PRINCIPLE", game_phase=GamePhase.ALL, claim=claim,
            conditions=conds, exceptions=["Karşıt kompozisyon koşulları"],
            confidence={"mechanical": None, "strategic": None, "empirical": None},
            scope={"patch_from": None, "patch_to": None, "rank": "ALL", "region": "ALL"},
            impact={"category": "STRATEGY", "estimated_effect": None,
                    "calibration_status": "hypothesis"},
            provenance={"generated_by": "knowledge_engine", "generation_type": "hypothesis_family",
                        "created_at": utcnow()},
            review={"verification_status": VerificationStatus.LLM_HYPOTHESIS_ONLY.value,
                    "contradictions": [], "last_reviewed_patch": None},
        ).to_dict()
        _, action = registry.upsert(rule, "seed_hypothesis")
        count += int(action != "dedup_skipped")
    return count
