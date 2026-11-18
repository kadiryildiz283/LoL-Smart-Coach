"""Rule Discovery Pipeline (kutsal_amac.md §22.3, §22.6, §22.12).

Validated Data -> Evidence Collection -> LLM Rule Proposal -> Schema Validation
-> Mechanic Verification -> Statistical Validation -> Conflict Detection ->
Rule Registry. Idempotent: pairs whose evidence hash is unchanged are skipped.
Unverified LLM proposals stay in the review queue, never auto-active.
"""
from __future__ import annotations

import hashlib
import json

from engine.config import Config
from engine.contracts.records import Rule, utcnow
from engine.contracts.types import RuleType, RuleStatus, GamePhase, VerificationStatus
from engine.data.store import Dataset
from engine.knowledge.rules.registry import RuleRegistry
from engine.knowledge.rules.validators import mechanical_validate, statistical_validate
from engine.llm.client import LLMClient, LLMUnavailable

SYSTEM = (
    "Sen bir LoL oyun mekanikleri analistisin. Verilen kanıtlardan YENİ stratejik veya "
    "ampirik kural adayları öner. Kurallar: (1) Kanıtta olmayan istatistik uydurma. "
    "(2) Mekanik avantajı maç galibiyeti garantisi olarak yazma; koşullu ifade kullan. "
    "(3) Mevcut kurallarla aynı bilgiyi tekrar önerme. (4) SADECE geçerli bir JSON dizisi üret. "
    "Alan değerleri TEK bir seçenek olmalı (boru işaretiyle listeleme YAPMA). Örnek çıktı:\n"
    '[{"rule_type":"strategic","title":"Caitlyn menzil baskısı",'
    '"subject":{"champion":"Caitlyn","role":"BOTTOM"},'
    '"target":{"champion":"Vayne","role":"BOTTOM"},'
    '"relation":"LANE_PRESSURE_ADVANTAGE","game_phase":"EARLY",'
    '"claim":"Caitlyn 650 menziliyle Vayne 550 menziline karşı erken koridorda baskı kurabilir.",'
    '"conditions":["Her ikisi BOTTOM","Güvenli pozisyon"],"exceptions":["Rakip all-in"],'
    '"impact_category":"LANING"}]\n'
    'İzinli değerler: rule_type=strategic veya empirical; relation=LANE_PRESSURE_ADVANTAGE, '
    'HARD_COUNTERED_BY, EASY_MATCHUP_VS veya SYNERGY_WITH; game_phase=EARLY, MID, LATE veya ALL; '
    'impact_category=LANING, MATCH_WIN veya TEAMFIGHT. Yeni bilgi yoksa boş dizi [] üret.'
)


def _evidence_hash(packet: dict) -> str:
    return hashlib.sha1(json.dumps(packet, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _pair_packet(ds: Dataset, a: int, b: int) -> dict:
    ca, cb = ds.champions.get(a, {}), ds.champions.get(b, {})
    fa = ds.mechanics.get(a, {}).get("features", {})
    fb = ds.mechanics.get(b, {}).get("features", {})

    def feats(f):
        return {k: f.get(k, {}).get("value") for k in
                ("attack_range", "mobility", "hard_cc", "sustain", "poke", "engage",
                 "frontline", "damage_ap", "damage_ad", "waveclear")}

    matchups = [m for m in ds.matchups
                if m["champion_id"] == a and m["opponent_id"] == b
                and m.get("observed_win_rate") is not None][:4]
    return {
        "champion_a": {"name": ca.get("name"), "tags": ca.get("tags"), "features": feats(fa)},
        "champion_b": {"name": cb.get("name"), "tags": cb.get("tags"), "features": feats(fb)},
        "observed_matchups": [{"role": m["champion_role"], "opponent_role": m["opponent_role"],
                               "relation": m["relation_type"], "win_rate": m["observed_win_rate"],
                               "sample": m.get("sample_size"), "gold15": m.get("lane_gold_diff_15")}
                              for m in matchups],
        "patch": ds.manifest.get("patch"),
    }


def discover_rules(cfg: Config, ds: Dataset, registry: RuleRegistry,
                   limit: int = 10, pairs: list[tuple[int, int]] | None = None) -> dict:
    report = {"llm_status": None, "pairs_examined": 0, "proposals": 0,
              "created": 0, "updated": 0, "dedup_skipped": 0, "verified": 0,
              "rejected": 0, "skipped_unchanged": 0, "errors": []}
    state_path = cfg.game_rules_dir / "_discovery_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}

    client = LLMClient(cfg.llm)
    status = client.status()
    report["llm_status"] = status
    if not status["available"]:
        report["errors"].append("LLM unavailable; discovery skipped (no fabrication)")
        return report

    if pairs is None:
        # default: notable range-advantage pairs sharing a role (evidence-rich)
        ranges = {cid: m.get("features", {}).get("attack_range", {}).get("value")
                  for cid, m in ds.mechanics.items()}
        pairs = []
        ids = sorted(ranges, key=lambda c: ds.champions.get(c, {}).get("name", ""))
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                ra, rb = ranges.get(a), ranges.get(b)
                if ra and rb and abs(ra - rb) >= 100:
                    pairs.append((a, b) if ra > rb else (b, a))
        pairs = pairs[:limit]

    for a, b in pairs:
        packet = _pair_packet(ds, a, b)
        eh = _evidence_hash(packet)
        key = f"{a}-{b}"
        if state.get(key) == eh:
            report["skipped_unchanged"] += 1
            continue
        report["pairs_examined"] += 1
        existing = [r for r in registry.all()
                    if r.get("subject", {}).get("champion_id") in (a, b)
                    and r.get("target", {}).get("champion_id") in (a, b)]
        prompt = ("KANIT:\n" + json.dumps(packet, ensure_ascii=False)
                  + "\n\nMEVCUT KURALLAR (tekrar önerme):\n"
                  + json.dumps([{"title": r["title"], "relation": r["relation"],
                                 "claim": r["claim"]} for r in existing][:12], ensure_ascii=False)
                  + "\n\nBu kanıtlardan en fazla 2 yeni kural adayı üret.")
        try:
            # proposals come as a JSON list; handle both OpenAI and Ollama shapes
            from engine.llm.client import _post_json
            ep = client.endpoint
            if ep.kind == "openai":
                resp = _post_json(ep.base_url + "/chat/completions", {
                    "model": ep.model,
                    "messages": [{"role": "system", "content": SYSTEM},
                                 {"role": "user", "content": prompt}],
                    "temperature": 0.3, "max_tokens": 1200}, timeout=cfg.llm.timeout_s)
                raw = resp["choices"][0]["message"]["content"]
            else:
                resp = _post_json(ep.base_url + "/api/chat", {
                    "model": ep.model,
                    "messages": [{"role": "system", "content": SYSTEM},
                                 {"role": "user", "content": prompt}],
                    "stream": False, "options": {"temperature": 0.3}},
                    timeout=cfg.llm.timeout_s)
                raw = resp["message"]["content"]
            import re
            m = re.search(r"\[.*\]", raw, re.S)
            if m:
                proposals = json.loads(m.group(0))
            elif raw.strip() in ("[]", ""):
                proposals = []
            else:
                report["errors"].append(f"LLM output parse failed: {raw[:80]!r}")
                continue
            if isinstance(proposals, dict):
                proposals = [proposals]
        except LLMUnavailable as e:
            report["errors"].append(str(e))
            break
        except Exception as e:
            report["errors"].append(f"{type(e).__name__}: {e}")
            continue

        from engine.contracts.schema import validate_record, SchemaError
        for p in proposals[:2]:
            try:
                validate_record("llm_rule_proposal", p)
            except SchemaError as e:
                report["errors"].append(f"proposal schema: {e}")
                continue
            report["proposals"] += 1
            sa = ds.resolve_id(p["subject"].get("champion", "")) or a
            tb = ds.resolve_id(p["target"].get("champion", "")) or b
            rule = Rule(
                rule_id="", rule_type=RuleType(p["rule_type"]), status=RuleStatus.PROPOSED,
                title=p["title"],
                subject={"champion_id": sa, **p["subject"]},
                target={"champion_id": tb, **p["target"]},
                relation=p["relation"], game_phase=GamePhase(p.get("game_phase", "ALL")),
                claim=p["claim"], conditions=p.get("conditions", []),
                exceptions=p.get("exceptions", []),
                confidence={"mechanical": None, "strategic": None, "empirical": None},
                scope={"patch_from": ds.manifest.get("patch"), "patch_to": None,
                       "rank": cfg.engine.rank_scope, "region": "ALL"},
                impact={"category": p.get("impact_category", "LANING"),
                        "estimated_effect": None, "calibration_status": "not_calibrated"},
                provenance={"generated_by": status["model"], "generation_type": "llm_proposal",
                            "created_at": utcnow(), "evidence_hash": eh},
                review={"verification_status": VerificationStatus.LLM_HYPOTHESIS_ONLY.value,
                        "contradictions": [], "last_reviewed_patch": None},
            ).to_dict()
            rid, action = registry.upsert(rule, "llm_discovery")
            report[{"created": "created", "updated": "updated",
                    "dedup_skipped": "dedup_skipped"}[action]] += 1
            if action == "dedup_skipped":
                continue
            # independent validation gates
            mv = mechanical_validate(rule, ds)
            sv = statistical_validate(rule, ds)
            if mv["passed"] is True:
                rule["review"]["verification_status"] = mv["verification"]
                rule["confidence"]["mechanical"] = mv["confidence_mechanical"]
                rule["status"] = RuleStatus.VERIFIED.value
                report["verified"] += 1
            elif mv["passed"] is False:
                rule["status"] = RuleStatus.REJECTED.value
                report["rejected"] += 1
            if sv.get("confidence_empirical") is not None:
                rule["confidence"]["empirical"] = sv["confidence_empirical"]
                rule["evidence"]["sample_size"] = sv.get("sample_size")
            registry.upsert(rule, "post_proposal_validation")
        state[key] = eh
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return report
