"""Canonical enums and role normalization. Riot canonical role names are used everywhere."""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    TOP = "TOP"
    JUNGLE = "JUNGLE"
    MIDDLE = "MIDDLE"
    BOTTOM = "BOTTOM"
    UTILITY = "UTILITY"


ALL_ROLES = [Role.TOP, Role.JUNGLE, Role.MIDDLE, Role.BOTTOM, Role.UTILITY]

# Legacy UI / LCU / scraper strings -> canonical role
ROLE_ALIASES = {
    "top": Role.TOP, "üst": Role.TOP, "upper": Role.TOP,
    "jungle": Role.JUNGLE, "jungler": Role.JUNGLE, "orman": Role.JUNGLE,
    "mid": Role.MIDDLE, "middle": Role.MIDDLE, "orta": Role.MIDDLE,
    "adc": Role.BOTTOM, "ad carry": Role.BOTTOM, "bottom": Role.BOTTOM,
    "bot": Role.BOTTOM, "alt": Role.BOTTOM, "nişancı": Role.BOTTOM, "marksman": Role.BOTTOM,
    "support": Role.UTILITY, "utility": Role.UTILITY, "destek": Role.UTILITY, "sup": Role.UTILITY,
}


def normalize_role(raw: str | None) -> Role | None:
    if not raw:
        return None
    return ROLE_ALIASES.get(str(raw).strip().lower())


def parse_roles(role_str: str | None) -> list[Role]:
    """'Jungler, Top' -> [JUNGLE, TOP] (deduplicated, order preserved)."""
    out: list[Role] = []
    for part in (role_str or "").split(","):
        r = normalize_role(part)
        if r and r not in out:
            out.append(r)
    return out


class RelationType(str, Enum):
    SAME_LANE = "SAME_LANE"
    CROSS_TEAM = "CROSS_TEAM"


class QualityStatus(str, Enum):
    OBSERVED = "observed"                    # directly measured, sample known
    DERIVED = "derived"                      # computed from observed raw data
    LEGACY_DERIVED = "legacy_derived"        # old pipeline normalized score, raw lost
    LEGACY_UNVERIFIED = "legacy_unverified"  # old scrape, semantics not fully verified
    FALLBACK = "fallback"                    # hierarchical fallback, NOT direct observation
    MISSING = "missing"
    SYNTHETIC = "synthetic"                  # test fixtures only, never production


class EvalMode(str, Enum):
    HEURISTIC = "HEURISTIC"      # no calibrated model: ranking_score only
    PROVISIONAL = "PROVISIONAL"  # trained but not fully validated
    CALIBRATED = "CALIBRATED"    # backtested + calibration gate passed


class RuleType(str, Enum):
    MECHANIC = "mechanic"
    STRATEGIC = "strategic"
    EMPIRICAL = "empirical"


class RuleStatus(str, Enum):
    PROPOSED = "proposed"
    VALIDATING = "validating"
    VERIFIED = "verified"
    ACTIVE = "active"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    MECHANICALLY_VERIFIED = "mechanically_verified"
    STATISTICALLY_SUPPORTED = "statistically_supported"
    EXPERT_REVIEWED = "expert_reviewed"
    LLM_HYPOTHESIS_ONLY = "llm_hypothesis_only"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    REVALIDATION_REQUIRED = "revalidation_required"


class SignalType(str, Enum):
    META = "META"
    LANE_MATCHUP = "LANE_MATCHUP"
    CROSS_MATCHUP = "CROSS_MATCHUP"
    SYNERGY = "SYNERGY"
    COMPOSITION = "COMPOSITION"
    THREAT = "THREAT"
    MECHANIC = "MECHANIC"
    RULE = "RULE"
    FUTURE_DRAFT = "FUTURE_DRAFT"


class GamePhase(str, Enum):
    EARLY = "EARLY"
    MID = "MID"
    LATE = "LATE"
    ALL = "ALL"
