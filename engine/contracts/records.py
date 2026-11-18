"""Versioned data contracts (kutsal_amac.md §4, §12.1, §15, §22.5, §23.10).

Raw statistics and derived scores are separate fields. Missing statistics are
null + missing_reason, never zero. Rates are fractions (0.508, not 50.8).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from engine import SCHEMA_VERSION
from engine.contracts.types import (
    Role, RelationType, QualityStatus, EvalMode, RuleType, RuleStatus,
    VerificationStatus, GamePhase,
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(d: Any) -> Any:
    if isinstance(d, dict):
        return {k: _clean(v) for k, v in d.items()}
    if isinstance(d, (list, tuple)):
        return [_clean(v) for v in d]
    if isinstance(d, (Role, RelationType, QualityStatus, EvalMode, RuleType,
                      RuleStatus, VerificationStatus, GamePhase)):
        return d.value
    return d


@dataclass
class Provenance:
    provider: str
    source_url: str | None = None
    collected_at: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    permission: str | None = None
    dataset_id: str | None = None

    def to_dict(self) -> dict:
        return _clean(asdict(self))


@dataclass
class Quality:
    status: QualityStatus = QualityStatus.MISSING
    missing_reason: str | None = None
    confidence: float | None = None
    fallback_of: str | None = None  # which scope this fallback came from

    def to_dict(self) -> dict:
        return _clean(asdict(self))


@dataclass
class Champion:
    champion_id: int
    name: str
    slug: str
    roles: list[Role] = field(default_factory=list)  # plausible roles, evidence-backed
    tags: list[str] = field(default_factory=list)    # Data Dragon tags
    overall_win_rate: float | None = None            # NOT role-specific
    overall_win_rate_quality: Quality = field(default_factory=Quality)
    provenance: Provenance = field(default_factory=lambda: Provenance("unknown"))

    def to_dict(self) -> dict:
        d = _clean(asdict(self))
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class ChampionRoleStats:
    champion_id: int
    role: Role
    patch: str
    queue: str = "RANKED_SOLO"
    region: str = "ALL"
    rank_scope: str = "ALL"
    win_rate: float | None = None
    pick_rate: float | None = None
    ban_rate: float | None = None
    role_play_rate: float | None = None
    sample_size: int | None = None
    side_win_rates: dict | None = None
    provenance: Provenance = field(default_factory=lambda: Provenance("unknown"))
    quality: Quality = field(default_factory=Quality)

    def natural_key(self) -> tuple:
        return (self.champion_id, self.role.value, self.patch, self.queue,
                self.region, self.rank_scope)

    def to_dict(self) -> dict:
        d = _clean(asdict(self))
        d["schema_version"] = SCHEMA_VERSION
        d["stats"] = {k: d.pop(k) for k in
                      ("win_rate", "pick_rate", "ban_rate", "role_play_rate", "sample_size")}
        return d


@dataclass
class Matchup:
    champion_id: int
    champion_role: Role
    opponent_id: int
    opponent_role: Role
    relation_type: RelationType
    patch: str
    region: str = "ALL"
    rank_scope: str = "ALL"
    queue: str = "RANKED_SOLO"
    sample_size: int | None = None
    observed_win_rate: float | None = None   # raw, perspective = champion_id wins
    expected_win_rate: float | None = None   # from main effects
    adjusted_matchup_delta: float | None = None  # log-odds observed vs expected
    lane_gold_diff_15: float | None = None
    lane_cs_diff_15: float | None = None
    lane_xp_diff_15: float | None = None
    confidence_interval: dict | None = None
    legacy_derived_score: float | None = None  # old 0.1-10 normalization, raw WR lost
    provenance: Provenance = field(default_factory=lambda: Provenance("unknown"))
    quality: Quality = field(default_factory=Quality)

    def natural_key(self) -> tuple:
        return (self.champion_id, self.champion_role.value, self.opponent_id,
                self.opponent_role.value, self.relation_type.value, self.patch,
                self.region, self.rank_scope, self.queue)

    def to_dict(self) -> dict:
        d = _clean(asdict(self))
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class Synergy:
    champion_id: int
    champion_role: Role
    ally_id: int
    ally_role: Role | None  # LoG partner rows do not tag the ally role
    patch: str
    region: str = "ALL"
    rank_scope: str = "ALL"
    sample_size: int | None = None
    observed_win_rate: float | None = None  # together, perspective = champion_id team
    expected_win_rate: float | None = None
    synergy_delta: float | None = None      # log-odds beyond main effects
    pick_together_rate: float | None = None
    legacy_derived_score: float | None = None
    provenance: Provenance = field(default_factory=lambda: Provenance("unknown"))
    quality: Quality = field(default_factory=Quality)

    def natural_key(self) -> tuple:
        return (self.champion_id, self.champion_role.value, self.ally_id,
                self.ally_role.value if self.ally_role else None,
                self.patch, self.region, self.rank_scope)

    def to_dict(self) -> dict:
        d = _clean(asdict(self))
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class Build:
    champion_id: int
    role: Role
    patch: str
    items: list[int] = field(default_factory=list)
    runes: dict = field(default_factory=dict)
    skill_order: list[str] = field(default_factory=list)
    sample_size: int | None = None
    win_rate: float | None = None
    popularity: float | None = None
    section: str = "core"  # starting | core | boots | final | runes
    provenance: Provenance = field(default_factory=lambda: Provenance("unknown"))
    quality: Quality = field(default_factory=Quality)

    def to_dict(self) -> dict:
        d = _clean(asdict(self))
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class Feature:
    value: Any
    unit: str
    source: str                 # e.g. "data_dragon", "expert_curated", "keyword_heuristic"
    validation_status: VerificationStatus = VerificationStatus.PENDING
    derived_from: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return _clean(asdict(self))


@dataclass
class ChampionMechanics:
    champion_id: int
    patch: str
    features: dict[str, dict] = field(default_factory=dict)  # serialized Feature records
    provenance: Provenance = field(default_factory=lambda: Provenance("unknown"))

    def to_dict(self) -> dict:
        d = _clean(asdict(self))
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class DatasetManifest:
    dataset_id: str
    status: str  # "validated" | "invalid" | "partial"
    patch: str
    generated_at: str = field(default_factory=utcnow)
    game: str = "LEAGUE_OF_LEGENDS"
    sources: list[dict] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)
    quality: dict = field(default_factory=lambda: {
        "validation_passed": False, "warnings": [], "missing_segments": []})

    def to_dict(self) -> dict:
        d = _clean(asdict(self))
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class IngestionReport:
    run_id: str
    started_at: str = field(default_factory=utcnow)
    finished_at: str | None = None
    providers: list[dict] = field(default_factory=list)
    dedup_actions: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    quarantined: list[dict] = field(default_factory=list)
    carried_forward: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)
    published_dataset_id: str | None = None

    def to_dict(self) -> dict:
        d = _clean(asdict(self))
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class DraftSlot:
    team: str                 # "BLUE" | "RED"
    index: int                # 0..4 within team
    actor: str                # "PICK" | "BAN"
    champion_id: int | None = None
    role: Role | None = None  # known/locked role, None = uncertain
    is_user: bool = False

    def to_dict(self) -> dict:
        return _clean(asdict(self))


# Standard ranked draft order (configurable per format/patch).
STANDARD_DRAFT_ORDER = [
    ("BLUE", "BAN"), ("RED", "BAN"), ("BLUE", "BAN"), ("RED", "BAN"), ("BLUE", "BAN"), ("RED", "BAN"),
    ("BLUE", "PICK"), ("RED", "PICK"), ("RED", "PICK"), ("BLUE", "PICK"), ("BLUE", "PICK"), ("RED", "PICK"),
    ("RED", "BAN"), ("BLUE", "BAN"), ("RED", "BAN"), ("BLUE", "BAN"),
    ("RED", "PICK"), ("BLUE", "PICK"), ("BLUE", "PICK"), ("RED", "PICK"),
]


@dataclass
class DraftState:
    draft_id: str
    user_team: str = "BLUE"
    user_role: Role = Role.MIDDLE
    queue: str = "RANKED_SOLO"
    patch: str = "unknown"
    order: list[tuple[str, str]] = field(default_factory=lambda: list(STANDARD_DRAFT_ORDER))
    slots: list[DraftSlot] = field(default_factory=list)
    picked_ids: list[int] = field(default_factory=list)
    banned_ids: list[int] = field(default_factory=list)
    current_step: int = 0
    available_ids: list[int] = field(default_factory=list)  # full selectable pool

    def to_dict(self) -> dict:
        d = _clean(asdict(self))
        d["schema_version"] = SCHEMA_VERSION
        return d

    def state_hash(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha1(payload.encode()).hexdigest()[:16]

    def team_picks(self, team: str) -> list[DraftSlot]:
        return [s for s in self.slots if s.team == team and s.actor == "PICK" and s.champion_id]

    def future_pick_steps(self) -> list[tuple[int, tuple[str, str]]]:
        return [(i, step) for i, step in enumerate(self.order)
                if i >= self.current_step and step[1] == "PICK"]


@dataclass
class CandidateEvaluation:
    champion_id: int
    role: Role
    evaluation_mode: EvalMode
    predicted_win_probability: float | None = None  # ONLY when CALIBRATED
    ranking_score: float | None = None              # log-odds scale in heuristic mode
    ranking_scale: str = "log_odds_heuristic"
    prediction_interval: dict | None = None
    expected_future_draft_value: float | None = None
    downside_risk: float | None = None
    model_uncertainty: float | None = None
    draft_uncertainty: float | None = None
    mc_standard_error: float | None = None
    confidence: float | None = None
    feature_contributions: list[dict] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    model_version: str = "heuristic-baseline-0.1"
    dataset_id: str | None = None

    def to_dict(self) -> dict:
        d = _clean(asdict(self))
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class Recommendation:
    draft_id: str
    model_version: str
    dataset_id: str | None
    recommended_champion_id: int | None = None
    recommended_role: Role | None = None
    predicted_win_probability: float | None = None
    ranking_score: float | None = None
    confidence: float | None = None
    evaluation_mode: EvalMode = EvalMode.HEURISTIC
    evidence: dict = field(default_factory=dict)
    risk: dict = field(default_factory=dict)
    alternatives: list[dict] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)
    source_references: list[dict] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    candidates: list[CandidateEvaluation] = field(default_factory=list)
    status: str = "not_evaluated"
    llm_explanation: dict | None = None

    def to_dict(self) -> dict:
        d = _clean(asdict(self))
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class Rule:
    rule_id: str
    rule_type: RuleType
    status: RuleStatus
    title: str
    subject: dict
    target: dict
    relation: str
    claim: str
    game_phase: GamePhase = GamePhase.ALL
    conditions: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=lambda: {
        "mechanical_sources": [], "statistical_sources": [],
        "sample_size": None, "observed_lane_advantage": None,
        "observed_match_win_rate": None})
    confidence: dict = field(default_factory=lambda: {
        "mechanical": None, "strategic": None, "empirical": None})
    scope: dict = field(default_factory=lambda: {
        "patch_from": None, "patch_to": None, "rank": "ALL", "region": "ALL"})
    impact: dict = field(default_factory=lambda: {
        "category": "LANING", "estimated_effect": None,
        "calibration_status": "not_calibrated"})
    provenance: dict = field(default_factory=dict)
    review: dict = field(default_factory=lambda: {
        "verification_status": VerificationStatus.PENDING.value,
        "contradictions": [], "last_reviewed_patch": None})
    version: int = 1
    semantic_key: str = ""
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = _clean(asdict(self))
        d["schema_version"] = SCHEMA_VERSION
        return d

    @staticmethod
    def compute_semantic_key(rule_type: str, subject: dict, target: dict,
                             relation: str, phase: str, conditions: list[str],
                             scope: dict) -> str:
        payload = json.dumps({
            "t": rule_type, "s": subject, "g": target, "r": relation,
            "p": phase, "c": sorted(conditions),
            "sc": {k: scope.get(k) for k in ("patch_from", "patch_to", "rank", "region")},
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(payload.encode()).hexdigest()[:20]
