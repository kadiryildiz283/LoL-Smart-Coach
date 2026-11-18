"""Canonical Evidence Schema (kutsal_amac.md §23.2).

Every signal produced by every engine carries: what it measures, its unit,
context, raw value, sample size, uncertainty, source and validation status.
Different units never hide in one field.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any

from engine import SCHEMA_VERSION
from engine.contracts.types import SignalType, QualityStatus


@dataclass
class Evidence:
    signal_type: SignalType
    subject: dict                      # {"champion_id": int, "role": str|None}
    target: dict | None                # {"champion_id": int, "role": str|None} | {"team": ...}
    metric: str                        # e.g. WIN_RATE, MATCHUP_DELTA_LOGODDS, GOLD_DIFFERENCE_AT_15
    raw_value: float | None
    unit: str                          # FRACTION | LOG_ODDS | GOLD | GAME_UNITS | COUNT | SCORE
    context: dict = field(default_factory=dict)  # patch, rank_scope, region, game_phase, perspective
    sample_size: int | None = None
    uncertainty: dict = field(default_factory=lambda: {
        "standard_error": None, "lower_bound": None, "upper_bound": None})
    source: dict = field(default_factory=dict)   # provider, dataset_id, source_url
    validation_status: QualityStatus = QualityStatus.MISSING
    model_version: str | None = None
    derived_from: list[str] = field(default_factory=list)  # evidence ids (double-counting guard)
    signal_id: str = ""

    def __post_init__(self):
        if not self.signal_id:
            payload = json.dumps({
                "t": self.signal_type.value, "s": self.subject, "g": self.target,
                "m": self.metric, "c": self.context, "v": self.raw_value,
            }, sort_keys=True, default=str)
            self.signal_id = f"{self.signal_type.value.lower()}-{hashlib.sha1(payload.encode()).hexdigest()[:14]}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signal_type"] = self.signal_type.value
        d["validation_status"] = self.validation_status.value
        d["schema_version"] = SCHEMA_VERSION
        return d
