"""Adapter: Draft Intelligence Engine -> PyQt6 UI (kutsal_amac.md §16).

Numeric recommendation arrives FIRST (fast, cached); the Qwen explanation is
produced asynchronously afterwards and never blocks the decision. The legacy
UI keeps working; this adapter is additive.
"""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from engine.config import DEFAULT_CONFIG
from engine.contracts.types import normalize_role, Role
from engine.data.store import DatasetStore
from engine.engines.decision import DecisionEngine
from engine.engines.draft import build_draft, DraftError


class EngineWorker(QThread):
    numeric_ready = pyqtSignal(dict)   # Recommendation.to_dict()
    llm_ready = pyqtSignal(dict)       # coach output (or offline fallback)
    failed = pyqtSignal(str)

    def __init__(self, ally_names, enemy_names, ban_names, role_str,
                 user_team="BLUE", with_llm=True, parent=None):
        super().__init__(parent)
        self.ally_names = ally_names
        self.enemy_names = enemy_names
        self.ban_names = ban_names
        self.role_str = role_str
        self.user_team = user_team
        self.with_llm = with_llm

    def run(self):
        try:
            cfg = DEFAULT_CONFIG
            ds = DatasetStore(cfg.datasets_dir).latest()
            if ds is None:
                self.failed.emit("Veri seti yok. Önce: python -m engine.cli ingest")
                return
            role = normalize_role(self.role_str) or Role.MIDDLE

            def resolve(names):
                out = []
                for n in names:
                    if n in ("Picking...", "Unknown", "...", "None", "", None):
                        continue
                    cid = ds.resolve_id(n)
                    if cid is not None:
                        out.append(cid)
                return out

            draft = build_draft(ds, role, resolve(self.ally_names),
                                resolve(self.enemy_names), resolve(self.ban_names),
                                self.user_team)
            eng = DecisionEngine(cfg, ds)
            rec = eng.recommend(draft)
            self.numeric_ready.emit(rec.to_dict())
            if self.with_llm:
                from engine.llm.coach import explain_recommendation
                out = explain_recommendation(cfg, ds, rec)
                self.llm_ready.emit(out)
        except DraftError as e:
            self.failed.emit(f"Draft hatası: {e}")
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


def format_numeric(rec: dict, ds_champions: dict) -> str:
    """Human-readable numeric summary for the UI panel."""
    cid = rec.get("recommended_champion_id")
    name = ds_champions.get(cid, {}).get("name", str(cid))
    lines = [
        f"ÖNERİ: {name}  ({rec.get('recommended_role')})",
        f"Mod: {rec.get('evaluation_mode')} | Skor: {rec.get('ranking_score')} (log-odds)",
        f"Güven: {rec.get('confidence')} | Durum: {rec.get('status')}",
    ]
    if rec.get("predicted_win_probability") is not None:
        lines.append(f"Kalibre kazanma olasılığı: %{rec['predicted_win_probability']*100:.1f}")
    for alt in rec.get("alternatives", [])[:2]:
        lines.append(f"  Alternatif: {alt.get('name')} (skor {alt.get('ranking_score')}, "
                     f"fark {alt.get('delta_vs_best')})")
    risk = rec.get("risk", {})
    lines.append(f"Risk: counter=%{risk.get('counterpick_exposure') or 0:.1f} "
                 f"rol-belirsizliği={risk.get('role_uncertainty')} "
                 f"veri-belirsizliği={risk.get('data_uncertainty')}")
    for ex in rec.get("explanations", []):
        lines.append("• " + ex)
    for lim in rec.get("limitations", []):
        lines.append("⚠ " + lim)
    return "\n".join(lines)
