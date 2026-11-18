"""Champion Knowledge Engine — mechanical feature derivation (kutsal_amac.md §6).

Sources, in order of trust:
1. Data Dragon base stats (attack range, HP, armor, MR) -> mechanically_verified
2. Expert-curated damage profiles (legacy repo data)    -> expert_curated, pending
3. Keyword heuristics over spell text                   -> derived_heuristic, pending

Nothing here is an LLM opinion. Every feature carries source + validation
status + derivation references. Missing sources stay null (never invented).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from engine.contracts.records import ChampionMechanics, Feature, Provenance, utcnow
from engine.contracts.types import VerificationStatus

HARD_CC = ["stun", "root", "snare", "knock up", "knockup", "knocks up", "airborne",
           "suppression", "suppress", "charm", "fear", "taunt", "sleep", "polymorph"]
SOFT_CC = ["slow", "silence", "blind", "ground", "cripple", "nearsight"]
MOBILITY = ["dash", "blink", "leap", "jump", "teleport", "vault", "rolls", "charges"]
SUSTAIN = ["heal", "shield", "restores health", "life steal", "lifesteal", "regenerat"]
WAVECLEAR = ["area of effect", "surrounding enemies", "nearby enemies", "all enemies in",
             "enemies in a line", "damage to all"]
POKE = ["skill shot", "skillshot", "in a line", "missile", "bolt", "orb"]
ANTI_MOBILITY = ["grounding", "grounded", "polymorph", "cannot dash", "disables dash"]
ANTI_HEAL = ["grievous wounds", "healing reduction", "reduced healing"]
TRUE_DAMAGE = ["true damage"]


def _count_keywords(texts: list[str], keywords: list[str]) -> tuple[int, list[str]]:
    hits = []
    for t in texts:
        tl = t.lower()
        for kw in keywords:
            if kw in tl:
                hits.append(kw)
    return len(set(hits)), sorted(set(hits))


def _score(count: int, scale: float = 2.0) -> float:
    return min(10.0, round(count * scale, 1))


def _load_dd_raw(dd_staging: Path) -> dict[int, dict]:
    """Map champion_id -> full Data Dragon champion payload from raw cache."""
    out = {}
    if not dd_staging.exists():
        return out
    for p in dd_staging.glob("*.json"):
        try:
            cached = json.loads(p.read_text(encoding="utf-8"))
            body = cached.get("body", {})
            data = body.get("data")
            if isinstance(data, dict) and len(data) == 1:
                champ = next(iter(data.values()))
                if isinstance(champ, dict) and "key" in champ and "spells" in champ:
                    out[int(champ["key"])] = champ
        except Exception:
            continue
    return out


def derive_features(champ_record: dict, dd_raw: dict | None, patch: str) -> dict[str, dict]:
    features: dict[str, Feature] = {}
    base = champ_record.get("base_stats") or (dd_raw or {}).get("stats", {})

    def verified(name, value, unit, ref):
        features[name] = Feature(value=value, unit=unit, source="data_dragon",
                                 validation_status=VerificationStatus.MECHANICALLY_VERIFIED,
                                 derived_from=[ref]).to_dict()

    if base.get("attackrange") is not None:
        verified("attack_range", float(base["attackrange"]), "GAME_UNITS", "stats.attackrange")
    for stat in ("hp", "armor", "spellblock", "attackdamage", "attackspeed"):
        if base.get(stat) is not None:
            verified(f"base_{stat}", float(base[stat]), "GAME_UNITS", f"stats.{stat}")

    # damage profile: curated first, tag heuristic fallback
    curated = champ_record.get("damage_profile_curated")
    if curated and "ap" in curated and "ad" in curated:
        features["damage_ap"] = Feature(value=curated["ap"], unit="SCORE_0_10",
                                        source="expert_curated",
                                        validation_status=VerificationStatus.PENDING,
                                        derived_from=["legacy:champion_damage_scores.json"]).to_dict()
        features["damage_ad"] = Feature(value=curated["ad"], unit="SCORE_0_10",
                                        source="expert_curated",
                                        validation_status=VerificationStatus.PENDING,
                                        derived_from=["legacy:champion_damage_scores.json"]).to_dict()
    else:
        tags = champ_record.get("tags", [])
        ap, ad = 5.0, 5.0
        if "Marksman" in tags:
            ad, ap = 8.0, 2.0
        elif "Mage" in tags:
            ap, ad = 8.0, 2.0
        elif "Assassin" in tags:
            ad, ap = 7.0, 3.0
        elif "Tank" in tags:
            ad, ap = 4.0, 4.0
        elif "Fighter" in tags:
            ad, ap = 7.0, 3.0
        elif "Support" in tags:
            ap, ad = 5.0, 3.0
        for name, val in (("damage_ap", ap), ("damage_ad", ad)):
            features[name] = Feature(value=val, unit="SCORE_0_10", source="tag_heuristic",
                                     validation_status=VerificationStatus.PENDING,
                                     derived_from=["data_dragon:tags"]).to_dict()

    # spell-text heuristics
    texts = []
    spell_refs = []
    if dd_raw:
        passive = dd_raw.get("passive", {})
        texts.append(passive.get("description", ""))
        spell_refs.append("passive:" + passive.get("name", "?"))
        for sp in dd_raw.get("spells", []):
            texts.append(sp.get("description", "") + " " + sp.get("tooltip", ""))
            spell_refs.append("spell:" + sp.get("name", "?"))
    if texts:
        for fname, kws, scale in (
            ("hard_cc", HARD_CC, 2.0), ("soft_cc", SOFT_CC, 1.5),
            ("mobility", MOBILITY, 2.0), ("sustain", SUSTAIN, 2.0),
            ("waveclear", WAVECLEAR, 2.5), ("poke", POKE, 1.5),
            ("anti_mobility", ANTI_MOBILITY, 3.0), ("anti_heal", ANTI_HEAL, 3.0),
            ("true_damage", TRUE_DAMAGE, 3.0),
        ):
            count, hits = _count_keywords(texts, kws)
            features[fname] = Feature(value=_score(count, scale), unit="SCORE_0_10",
                                      source="keyword_heuristic",
                                      validation_status=VerificationStatus.PENDING,
                                      derived_from=[f"{r} ({','.join(hits)})"
                                                    for r, h in zip(spell_refs, hits)][:8]
                                      if hits else spell_refs[:1]).to_dict()
        # engage = hard CC + mobility; frontline = tank tag + durability stats
        hard = features.get("hard_cc", {}).get("value", 0)
        mob = features.get("mobility", {}).get("value", 0)
        features["engage"] = Feature(value=min(10.0, round(hard * 0.6 + mob * 0.4, 1)),
                                     unit="SCORE_0_10", source="derived_composite",
                                     validation_status=VerificationStatus.PENDING,
                                     derived_from=["hard_cc", "mobility"]).to_dict()
        tags = champ_record.get("tags", [])
        dur = 0.0
        if "Tank" in tags:
            dur += 5.0
        if base.get("hp", 0) >= 600:
            dur += 2.0
        if base.get("armor", 0) >= 30:
            dur += 1.5
        if base.get("spellblock", 0) >= 32:
            dur += 1.5
        features["frontline"] = Feature(value=min(10.0, dur), unit="SCORE_0_10",
                                        source="derived_composite",
                                        validation_status=VerificationStatus.PENDING,
                                        derived_from=["tags", "base_hp", "base_armor", "base_spellblock"]).to_dict()
        rng = features.get("attack_range", {}).get("value", 0)
        features["range_class"] = Feature(
            value="MELEE" if rng < 300 else ("SHORT" if rng < 500 else ("MEDIUM" if rng < 600 else "LONG")),
            unit="CLASS", source="derived_from_verified",
            validation_status=VerificationStatus.MECHANICALLY_VERIFIED,
            derived_from=["attack_range"]).to_dict()

    # honest gaps: no verified source yet
    for fname, reason in (("early_power", "no_phase_stats_source"),
                          ("late_power", "no_phase_stats_source"),
                          ("mechanical_difficulty", "no_difficulty_source"),
                          ("split_push", "no_splitpush_metric")):
        features[fname] = Feature(value=None, unit="SCORE_0_10", source="none",
                                  validation_status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                                  derived_from=[]).to_dict()
        features[fname]["missing_reason"] = reason
    return features


def derive_mechanics_for_dataset(champions: dict, dd_staging: Path, patch: str,
                                 legacy_dir: Path | None = None) -> dict:
    dd_raws = _load_dd_raw(Path(dd_staging))
    out = {}
    for cid, champ in champions.items():
        feats = derive_features(champ, dd_raws.get(int(cid)), patch)
        rec = ChampionMechanics(
            champion_id=int(cid), patch=patch,
            features=feats,
            provenance=Provenance(provider="knowledge_engine", collected_at=utcnow(),
                                  source_url="data_dragon+curated+heuristics"),
        ).to_dict()
        out[int(cid)] = rec
    return out
