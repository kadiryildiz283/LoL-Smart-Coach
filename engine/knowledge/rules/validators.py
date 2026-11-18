"""Independent rule validators + Conflict Resolver (kutsal_amac.md §22.3, §22.7).

A rule is NOT accepted because its JSON is valid or an LLM proposed it.
- MechanicalValidator: checks claims against verified game data (Data Dragon).
- StatisticalValidator: checks empirical claims against matchup records with
  sample size / confidence; LOW-sample stats cannot invalidate verified mechanics.
- ConflictResolver: lane pressure and match win are DIFFERENT target variables;
  apparent contradictions across targets coexist. Same-target conflicts go
  through scope/patch/sample/CI comparison, never silent deletion.
"""
from __future__ import annotations

from engine.contracts.records import utcnow
from engine.contracts.types import RuleStatus, VerificationStatus, RelationType
from engine.data.store import Dataset
from engine.knowledge.rules.registry import RuleRegistry
from engine.stats import wilson_interval

MIN_SAMPLE_TO_CHALLENGE_MECHANIC = 500


def _champ_id(ds: Dataset, subject_or_target: dict) -> int | None:
    if subject_or_target.get("champion_id") is not None:
        return int(subject_or_target["champion_id"])
    name = subject_or_target.get("champion")
    return ds.resolve_id(name) if name else None


def mechanical_validate(rule: dict, ds: Dataset) -> dict:
    """Verify mechanic claims against Data Dragon-derived features."""
    relation = rule.get("relation", "")
    sid = _champ_id(ds, rule.get("subject", {}))
    tid = _champ_id(ds, rule.get("target", {}))
    if relation == "LANE_PRESSURE_ADVANTAGE" and sid and tid:
        fs = ds.mechanics.get(sid, {}).get("features", {})
        ft = ds.mechanics.get(tid, {}).get("features", {})
        rs = fs.get("attack_range", {}).get("value")
        rt = ft.get("attack_range", {}).get("value")
        if rs is not None and rt is not None:
            if rs > rt:
                return {"passed": True,
                        "verification": VerificationStatus.MECHANICALLY_VERIFIED.value,
                        "evidence": {"subject_range": rs, "target_range": rt,
                                     "source": "data_dragon:stats.attackrange",
                                     "delta": rs - rt},
                        "confidence_mechanical": 0.95}
            return {"passed": False,
                    "verification": VerificationStatus.INSUFFICIENT_EVIDENCE.value,
                    "evidence": {"subject_range": rs, "target_range": rt,
                                 "reason": "range claim contradicted by game data"},
                    "confidence_mechanical": 0.0}
    if relation in ("HAS_RANGE", "ATTACK_RANGE"):
        if sid:
            r = ds.mechanics.get(sid, {}).get("features", {}).get("attack_range", {}).get("value")
            if r is not None:
                return {"passed": True,
                        "verification": VerificationStatus.MECHANICALLY_VERIFIED.value,
                        "evidence": {"attack_range": r, "source": "data_dragon"},
                        "confidence_mechanical": 0.95}
    return {"passed": None,
            "verification": VerificationStatus.LLM_HYPOTHESIS_ONLY.value,
            "evidence": {"reason": "no mechanical verification path for this relation"},
            "confidence_mechanical": None}


def statistical_validate(rule: dict, ds: Dataset) -> dict:
    """Check empirical support; return sample-aware confidence."""
    sid = _champ_id(ds, rule.get("subject", {}))
    tid = _champ_id(ds, rule.get("target", {}))
    if not sid or not tid:
        return {"supported": None, "sample_size": None, "confidence_empirical": None}
    srole = rule.get("subject", {}).get("role", "MIDDLE")
    trole = rule.get("target", {}).get("role", "MIDDLE")
    m = ds.matchup_for(sid, srole, tid, trole, RelationType.SAME_LANE.value)
    if m is None:
        m = ds.matchup_for(sid, srole, tid, trole, RelationType.CROSS_TEAM.value)
    if m is None:
        # search across rank scopes (rule validation is rare; linear scan OK)
        for key, rec in ds.matchup_idx.items():
            if (key[0] == sid and key[1] == srole and key[2] == tid
                    and key[3] == trole and rec.get("observed_win_rate") is not None):
                m = rec
                break
    if m is None or m.get("observed_win_rate") is None:
        return {"supported": None, "sample_size": None, "confidence_empirical": None,
                "missing_reason": "no_observed_matchup_data"}
    n = m.get("sample_size") or 0
    wr = m["observed_win_rate"]
    ci = wilson_interval(wr * n, n) if n else None
    relation = rule.get("relation", "")
    if relation in ("EASY_MATCHUP_VS", "LANE_PRESSURE_ADVANTAGE"):
        supported = wr > 0.5
    elif relation == "HARD_COUNTERED_BY":
        supported = wr < 0.5
    else:
        supported = None
    conf = min(0.9, n / (n + 200)) if n else 0.1
    return {"supported": supported, "sample_size": n, "observed_win_rate": wr,
            "confidence_interval": ci.to_dict() if ci else None,
            "confidence_empirical": round(conf, 4)}


def resolve_conflicts(registry: RuleRegistry, ds: Dataset) -> list[dict]:
    """Detect and classify conflicts; never silently delete."""
    actions = []
    rules = registry.all()
    by_pair: dict[tuple, list[dict]] = {}
    for r in rules:
        sid = _champ_id(ds, r.get("subject", {}))
        tid = _champ_id(ds, r.get("target", {}))
        if sid and tid and sid != tid:
            by_pair.setdefault((min(sid, tid), max(sid, tid)), []).append(r)
    for (sid, tid), group in by_pair.items():
        mech = [r for r in group if r["rule_type"] == "mechanic"
                or r.get("review", {}).get("verification_status") == VerificationStatus.MECHANICALLY_VERIFIED.value]
        emp = [r for r in group if r["rule_type"] == "empirical"]
        for m in mech:
            for e in emp:
                # different target variables (LANING vs MATCH_WIN) -> coexist
                m_cat = m.get("impact", {}).get("category", "LANING")
                e_cat = e.get("impact", {}).get("category", "MATCH_WIN")
                if m_cat != e_cat:
                    registry.record_conflict({
                        "type": "cross_target_coexistence",
                        "mechanic_rule": m["rule_id"], "empirical_rule": e["rule_id"],
                        "resolution": "coexist",
                        "reason": "lane pressure and match win are different target variables",
                    })
                    actions.append({"pair": [sid, tid], "resolution": "coexist"})
                    continue
                # the empirical rule's OWN claimed sample decides whether it may
                # challenge a verified mechanic (dataset enrichment happens in validate_all)
                n = e.get("evidence", {}).get("sample_size") or 0
                if n < MIN_SAMPLE_TO_CHALLENGE_MECHANIC:
                    registry.record_conflict({
                        "type": "low_sample_cannot_invalidate_mechanic",
                        "mechanic_rule": m["rule_id"], "empirical_rule": e["rule_id"],
                        "sample_size": n, "resolution": "mechanic_kept",
                    })
                    actions.append({"pair": [sid, tid], "resolution": "mechanic_kept",
                                    "sample": n})
                else:
                    registry.set_status(e["rule_id"], RuleStatus.NEEDS_REVIEW,
                                        f"same-target conflict with verified mechanic {m['rule_id']}, n={n}")
                    registry.record_conflict({
                        "type": "same_target_conflict",
                        "mechanic_rule": m["rule_id"], "empirical_rule": e["rule_id"],
                        "sample_size": n, "resolution": "empirical_needs_review",
                    })
                    actions.append({"pair": [sid, tid], "resolution": "needs_review",
                                    "sample": n})
    return actions


def validate_all(registry: RuleRegistry, ds: Dataset | None) -> dict:
    report = {"validated": 0, "mechanically_verified": 0, "statistically_supported": 0,
              "rejected": 0, "needs_review": 0, "conflict_actions": []}
    for rule in registry.all():
        if rule["status"] in (RuleStatus.REJECTED.value, RuleStatus.SUPERSEDED.value,
                              RuleStatus.DEPRECATED.value):
            continue
        changed = False
        # patch staleness: a rule bounded to an old patch needs revalidation
        patch_to = rule.get("scope", {}).get("patch_to")
        if ds is not None and patch_to and ds.manifest.get("patch", "") > patch_to:
            if rule["status"] in (RuleStatus.VERIFIED.value, RuleStatus.ACTIVE.value):
                registry.set_status(rule["rule_id"], RuleStatus.NEEDS_REVIEW,
                                    f"patch advanced beyond patch_to={patch_to}")
                rule.setdefault("review", {})["verification_status"] = \
                    VerificationStatus.REVALIDATION_REQUIRED.value
                report["needs_review"] += 1
                continue
        if ds is not None:
            mv = mechanical_validate(rule, ds)
            if mv["passed"] is True:
                rule.setdefault("review", {})["verification_status"] = mv["verification"]
                rule.setdefault("confidence", {})["mechanical"] = mv["confidence_mechanical"]
                rule.setdefault("evidence", {}).setdefault("mechanical_sources", []).append(mv["evidence"])
                if rule["status"] == RuleStatus.PROPOSED.value:
                    rule["status"] = RuleStatus.VERIFIED.value
                report["mechanically_verified"] += 1
                changed = True
            elif mv["passed"] is False:
                rule["status"] = RuleStatus.REJECTED.value
                rule.setdefault("review", {})["verification_status"] = mv["verification"]
                report["rejected"] += 1
                changed = True
            sv = statistical_validate(rule, ds)
            if sv.get("supported") is not None:
                rule.setdefault("confidence", {})["empirical"] = sv["confidence_empirical"]
                rule.setdefault("evidence", {})["sample_size"] = sv.get("sample_size")
                rule["evidence"]["observed_match_win_rate"] = sv.get("observed_win_rate")
                if sv["supported"]:
                    report["statistically_supported"] += 1
                changed = True
        if changed:
            registry.upsert(rule, change_reason="validation_pass")
            report["validated"] += 1
    if ds is not None:
        report["conflict_actions"] = resolve_conflicts(registry, ds)
    return report
