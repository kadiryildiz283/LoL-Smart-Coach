"""JSON Schema definitions + validation gate. Nothing publishes without passing."""
from __future__ import annotations

from jsonschema import Draft202012Validator


class SchemaError(ValueError):
    def __init__(self, kind: str, errors: list[str]):
        self.kind = kind
        self.errors = errors
        super().__init__(f"{kind} schema violation: {'; '.join(errors[:5])}")


def _num(nullable=True):
    t = ["number", "null"] if nullable else ["number"]
    return {"type": t}


def _int(nullable=True):
    return {"type": ["integer", "null"] if nullable else ["integer"]}


def _str(nullable=True):
    return {"type": ["string", "null"] if nullable else ["string"]}


PROVENANCE = {
    "type": "object",
    "required": ["provider"],
    "properties": {
        "provider": {"type": "string"},
        "source_url": _str(), "collected_at": _str(),
        "period_start": _str(), "period_end": _str(),
        "permission": _str(), "dataset_id": _str(),
    },
}

QUALITY = {
    "type": "object",
    "required": ["status"],
    "properties": {
        "status": {"enum": ["observed", "derived", "legacy_derived", "legacy_unverified",
                             "fallback", "missing", "synthetic"]},
        "missing_reason": _str(),
        "confidence": _num(),
        "fallback_of": _str(),
    },
}

ROLE_ENUM = {"enum": ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]}

CHAMPION_ROLE_STATS = {
    "type": "object",
    "required": ["schema_version", "champion_id", "role", "patch", "stats", "provenance", "quality"],
    "properties": {
        "schema_version": {"type": "string"},
        "champion_id": _int(False),
        "role": ROLE_ENUM,
        "patch": {"type": "string"},
        "queue": {"type": "string"},
        "region": {"type": "string"},
        "rank_scope": {"type": "string"},
        "stats": {
            "type": "object",
            "required": ["win_rate", "pick_rate", "ban_rate", "role_play_rate", "sample_size"],
            "properties": {
                "win_rate": {**_num(), "minimum": 0, "maximum": 1},
                "pick_rate": {**_num(), "minimum": 0, "maximum": 1},
                "ban_rate": {**_num(), "minimum": 0, "maximum": 1},
                "role_play_rate": {**_num(), "minimum": 0, "maximum": 1},
                "sample_size": {**_int(), "minimum": 0},
            },
        },
        "side_win_rates": {"type": ["object", "null"]},
        "provenance": PROVENANCE,
        "quality": QUALITY,
    },
}

MATCHUP = {
    "type": "object",
    "required": ["schema_version", "champion_id", "champion_role", "opponent_id",
                 "opponent_role", "relation_type", "patch", "provenance", "quality"],
    "properties": {
        "schema_version": {"type": "string"},
        "champion_id": _int(False), "champion_role": ROLE_ENUM,
        "opponent_id": _int(False), "opponent_role": ROLE_ENUM,
        "relation_type": {"enum": ["SAME_LANE", "CROSS_TEAM"]},
        "patch": {"type": "string"},
        "region": {"type": "string"}, "rank_scope": {"type": "string"}, "queue": {"type": "string"},
        "sample_size": {**_int(), "minimum": 0},
        "observed_win_rate": {**_num(), "minimum": 0, "maximum": 1},
        "expected_win_rate": {**_num(), "minimum": 0, "maximum": 1},
        "adjusted_matchup_delta": _num(),
        "lane_gold_diff_15": _num(), "lane_cs_diff_15": _num(), "lane_xp_diff_15": _num(),
        "confidence_interval": {"type": ["object", "null"]},
        "legacy_derived_score": _num(),
        "provenance": PROVENANCE, "quality": QUALITY,
    },
}

SYNERGY = {
    "type": "object",
    "required": ["schema_version", "champion_id", "champion_role", "ally_id",
                 "ally_role", "patch", "provenance", "quality"],
    "properties": {
        "schema_version": {"type": "string"},
        "champion_id": _int(False), "champion_role": ROLE_ENUM,
        "ally_id": _int(False),
        "ally_role": {"enum": ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY", None]},
        "patch": {"type": "string"},
        "region": {"type": "string"}, "rank_scope": {"type": "string"},
        "sample_size": {**_int(), "minimum": 0},
        "observed_win_rate": {**_num(), "minimum": 0, "maximum": 1},
        "expected_win_rate": {**_num(), "minimum": 0, "maximum": 1},
        "synergy_delta": _num(),
        "pick_together_rate": {**_num(), "minimum": 0, "maximum": 1},
        "legacy_derived_score": _num(),
        "provenance": PROVENANCE, "quality": QUALITY,
    },
}

MANIFEST = {
    "type": "object",
    "required": ["schema_version", "dataset_id", "status", "patch", "generated_at",
                 "sources", "coverage", "quality"],
    "properties": {
        "schema_version": {"type": "string"},
        "dataset_id": {"type": "string"},
        "status": {"enum": ["validated", "invalid", "partial"]},
        "game": {"type": "string"},
        "patch": {"type": "string"},
        "generated_at": {"type": "string"},
        "sources": {"type": "array"},
        "coverage": {"type": "object"},
        "quality": {
            "type": "object",
            "required": ["validation_passed", "warnings", "missing_segments"],
            "properties": {
                "validation_passed": {"type": "boolean"},
                "warnings": {"type": "array"},
                "missing_segments": {"type": "array"},
            },
        },
    },
}

EVIDENCE = {
    "type": "object",
    "required": ["schema_version", "signal_id", "signal_type", "subject", "metric",
                 "raw_value", "unit", "validation_status"],
    "properties": {
        "schema_version": {"type": "string"},
        "signal_id": {"type": "string"},
        "signal_type": {"type": "string"},
        "subject": {"type": "object"},
        "target": {"type": ["object", "null"]},
        "context": {"type": "object"},
        "metric": {"type": "string"},
        "raw_value": _num(),
        "unit": {"enum": ["FRACTION", "LOG_ODDS", "GOLD", "CS", "XP", "GAME_UNITS",
                           "COUNT", "SCORE", "PROBABILITY", "ENTROPY"]},
        "sample_size": {**_int(), "minimum": 0},
        "uncertainty": {"type": "object"},
        "source": {"type": "object"},
        "validation_status": {"type": "string"},
        "model_version": _str(),
        "derived_from": {"type": "array"},
    },
}

CANDIDATE_EVALUATION = {
    "type": "object",
    "required": ["schema_version", "champion_id", "role", "evaluation_mode",
                 "ranking_scale", "model_version"],
    "properties": {
        "schema_version": {"type": "string"},
        "champion_id": _int(False),
        "role": ROLE_ENUM,
        "evaluation_mode": {"enum": ["HEURISTIC", "PROVISIONAL", "CALIBRATED"]},
        "predicted_win_probability": {**_num(), "minimum": 0, "maximum": 1},
        "ranking_score": _num(),
        "ranking_scale": {"type": "string"},
        "prediction_interval": {"type": ["object", "null"]},
        "expected_future_draft_value": _num(),
        "downside_risk": _num(),
        "model_uncertainty": _num(),
        "draft_uncertainty": _num(),
        "mc_standard_error": _num(),
        "confidence": {**_num(), "minimum": 0, "maximum": 1},
        "feature_contributions": {"type": "array"},
        "evidence_ids": {"type": "array"},
        "model_version": {"type": "string"},
        "dataset_id": _str(),
    },
}

RECOMMENDATION = {
    "type": "object",
    "required": ["schema_version", "draft_id", "model_version", "evaluation_mode", "status"],
    "properties": {
        "schema_version": {"type": "string"},
        "draft_id": {"type": "string"},
        "model_version": {"type": "string"},
        "dataset_id": _str(),
        "recommended_champion_id": _int(),
        "recommended_role": {**ROLE_ENUM, "type": ["string", "null"]},
        "predicted_win_probability": {**_num(), "minimum": 0, "maximum": 1},
        "ranking_score": _num(),
        "confidence": _num(),
        "evaluation_mode": {"enum": ["HEURISTIC", "PROVISIONAL", "CALIBRATED"]},
        "evidence": {"type": "object"},
        "risk": {"type": "object"},
        "alternatives": {"type": "array"},
        "explanations": {"type": "array"},
        "source_references": {"type": "array"},
        "limitations": {"type": "array"},
        "candidates": {"type": "array"},
        "status": {"type": "string"},
        "llm_explanation": {"type": ["object", "null"]},
    },
}

RULE = {
    "type": "object",
    "required": ["schema_version", "rule_id", "rule_type", "status", "title",
                 "subject", "target", "relation", "claim", "provenance"],
    "properties": {
        "schema_version": {"type": "string"},
        "rule_id": {"type": "string"},
        "rule_type": {"enum": ["mechanic", "strategic", "empirical"]},
        "status": {"enum": ["proposed", "validating", "verified", "active",
                             "needs_review", "rejected", "superseded", "deprecated"]},
        "title": {"type": "string"},
        "subject": {"type": "object"},
        "target": {"type": "object"},
        "relation": {"type": "string"},
        "game_phase": {"enum": ["EARLY", "MID", "LATE", "ALL"]},
        "claim": {"type": "string"},
        "conditions": {"type": "array"},
        "exceptions": {"type": "array"},
        "evidence": {"type": "object"},
        "confidence": {"type": "object"},
        "scope": {"type": "object"},
        "impact": {"type": "object"},
        "provenance": {"type": "object"},
        "review": {"type": "object"},
        "version": {"type": "integer"},
        "semantic_key": {"type": "string"},
        "history": {"type": "array"},
    },
}

LLM_COACH_OUTPUT = {
    "type": "object",
    "required": ["summary", "lane_plan", "teamfight_plan", "risks", "data_caveats"],
    "properties": {
        "summary": {"type": "string"},
        "lane_plan": {"type": "string"},
        "teamfight_plan": {"type": "string"},
        "risks": {"type": "array", "items": {"type": "string"}},
        "alternatives_rationale": {"type": "array", "items": {"type": "string"}},
        "data_caveats": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

LLM_RULE_PROPOSAL = {
    "type": "object",
    "required": ["rule_type", "title", "subject", "target", "relation", "claim"],
    "properties": {
        "rule_type": {"enum": ["mechanic", "strategic", "empirical"]},
        "title": {"type": "string"},
        "subject": {"type": "object"},
        "target": {"type": "object"},
        "relation": {"type": "string"},
        "game_phase": {"enum": ["EARLY", "MID", "LATE", "ALL"]},
        "claim": {"type": "string"},
        "conditions": {"type": "array", "items": {"type": "string"}},
        "exceptions": {"type": "array", "items": {"type": "string"}},
        "impact_category": {"type": "string"},
    },
}

SCHEMAS: dict[str, dict] = {
    "champion_role_stats": CHAMPION_ROLE_STATS,
    "matchup": MATCHUP,
    "synergy": SYNERGY,
    "manifest": MANIFEST,
    "evidence": EVIDENCE,
    "candidate_evaluation": CANDIDATE_EVALUATION,
    "recommendation": RECOMMENDATION,
    "rule": RULE,
    "llm_coach_output": LLM_COACH_OUTPUT,
    "llm_rule_proposal": LLM_RULE_PROPOSAL,
}

_VALIDATORS = {k: Draft202012Validator(v) for k, v in SCHEMAS.items()}


def validate_record(kind: str, record: dict) -> None:
    """Raise SchemaError on violation. Used at publish, LLM output and rule gates."""
    if kind not in _VALIDATORS:
        raise SchemaError(kind, [f"unknown schema kind: {kind}"])
    errors = [f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
              for e in _VALIDATORS[kind].iter_errors(record)]
    if errors:
        raise SchemaError(kind, errors)
