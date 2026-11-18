"""Local LLM Coach (kutsal_amac.md §14): explains computed decisions in Turkish.

The LLM receives ONLY the compact evidence packet of the top candidates —
never the raw archive. It cannot change ranking, invent statistics, or suggest
banned/picked champions. Output is schema-validated; on any failure a
deterministic template explanation is used (llm_status marked).
"""
from __future__ import annotations

import json

from engine.config import Config
from engine.contracts.records import Recommendation
from engine.data.store import Dataset
from engine.llm.client import LLMClient, LLMUnavailable

SYSTEM = (
    "Sen bir League of Legends draft koçusun. Sana bir karar motorunun hesapladığı "
    "kanıt paketi verilecek. Kurallar: (1) Sayısal sıralamayı DEĞİŞTİREMEZSİN, sadece açıklarsın. "
    "(2) Verilmeyen istatistik/oran UYDURAMAZSIN; eksik veri için 'veri yok' dersin. "
    "(3) Yasaklı/seçilmiş şampiyon öneremezsin. (4) Mekanik avantajı maç galibiyeti garantisi "
    "gibi sunamazsın. (5) Türkçe, net ve stratejik yaz. (6) SADECE istenen JSON şemasında çıktı ver."
)


def build_evidence_packet(ds: Dataset, rec: Recommendation, budget: int) -> dict:
    def champ(cid):
        c = ds.champions.get(cid, {})
        return {"name": c.get("name"), "tags": c.get("tags"),
                "overall_win_rate": c.get("overall_win_rate")}

    best = rec.candidates[0] if rec.candidates else None
    packet = {
        "patch": ds.manifest.get("patch"),
        "dataset_id": ds.dataset_id,
        "evaluation_mode": rec.evaluation_mode.value,
        "role": rec.recommended_role.value if rec.recommended_role else None,
        "recommended": champ(rec.recommended_champion_id) if rec.recommended_champion_id else None,
        "ranking_score": rec.ranking_score,
        "ranking_scale": "log_odds (kalibre olasılık DEĞİL)",
        "confidence": rec.confidence,
        "risk": rec.risk,
        "limitations": rec.limitations,
        "feature_contributions": best.feature_contributions if best else [],
        "alternatives": [
            {**champ(a["champion_id"]), "ranking_score": a["ranking_score"],
             "delta_vs_best": a.get("delta_vs_best")}
            for a in rec.alternatives
        ],
        "future_draft": {
            "expected": best.expected_future_draft_value if best else None,
            "downside": best.downside_risk if best else None,
            "mc_standard_error": best.mc_standard_error if best else None,
        },
    }
    text = json.dumps(packet, ensure_ascii=False)
    if len(text) > budget:
        packet["feature_contributions"] = packet["feature_contributions"][:4]
        packet["limitations"] = packet["limitations"][:3]
    return packet


def _fallback(rec: Recommendation, ds: Dataset) -> dict:
    name = ds.champions.get(rec.recommended_champion_id, {}).get("name", "?")
    return {
        "summary": f"Karar motoru {name} öneriyor (skor {rec.ranking_score}, log-odds ölçeği). "
                   f"LLM servisi kullanılamadı; bu açıklama deterministik şablondur.",
        "lane_plan": "Koridor planı için LLM servisi gerekli; sayısal kanıtlar feature_contributions alanındadır.",
        "teamfight_plan": "Takım savaşı planı için LLM servisi gerekli.",
        "risks": [f"Veri belirsizliği: {rec.risk.get('data_uncertainty')}",
                  f"Rol belirsizliği: {rec.risk.get('role_uncertainty')}"],
        "alternatives_rationale": [f"{a.get('name')}: skor farkı {a.get('delta_vs_best')}"
                                   for a in rec.alternatives],
        "data_caveats": rec.limitations[:4],
        "llm_status": "offline_fallback",
    }


def explain_recommendation(cfg: Config, ds: Dataset, rec: Recommendation) -> dict:
    client = LLMClient(cfg.llm)
    status = client.status()
    if not status["available"]:
        out = _fallback(rec, ds)
        out["llm_error"] = status.get("error")
        return out
    packet = build_evidence_packet(ds, rec, cfg.llm.context_budget_chars)
    prompt = (
        "Aşağıdaki kanıt paketini kullanarak öneriyi Türkçe açıkla. JSON alanları: "
        "summary (öneri ve neden), lane_plan (koridor planı), teamfight_plan (takım savaşı planı), "
        "risks (liste), alternatives_rationale (liste, her alternatifin neden farklı olduğu), "
        "data_caveats (liste, veri eksikleri/belirsizlikler).\n\nKANIT PAKETİ:\n"
        + json.dumps(packet, ensure_ascii=False)
    )
    try:
        out = client.generate_json(SYSTEM, prompt, "llm_coach_output")
        out["llm_status"] = "ok"
        out["model"] = status["model"]
        return out
    except LLMUnavailable as e:
        out = _fallback(rec, ds)
        out["llm_error"] = str(e)
        return out
