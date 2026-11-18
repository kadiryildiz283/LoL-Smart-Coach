"""Decision & Calibration Engine (kutsal_amac.md §13, §23).

HEURISTIC mode: every contribution is an explicit log-odds term with a
documented baseline weight; ranking_score is NOT a win probability.
predicted_win_probability stays null until a CALIBRATED model passes the
backtest gate. Evidence ids make every ranking auditable.
"""
from __future__ import annotations

import time

from engine.config import Config
from engine.contracts.records import (
    DraftState, Recommendation, CandidateEvaluation,
)
from engine.contracts.types import (
    Role, RelationType, EvalMode, QualityStatus, ALL_ROLES,
)
from engine.data.store import Dataset
from engine.engines.meta import MetaEngine
from engine.engines.matchup import MatchupEngine
from engine.engines.synergy import SynergyEngine
from engine.engines.composition import CompositionEngine
from engine.engines.threat import ThreatEngine
from engine.engines.role_inference import RoleInferenceEngine
from engine.engines.future import FutureDraftEngine
from engine.engines.draft import enemy_known, ally_known, future_steps
from engine.stats import sigmoid, logit

MODEL_VERSION = "heuristic-baseline-0.1"
# Documented baseline weights (log-odds scale). To be learned in CALIBRATED mode.
W_MAIN = 1.0
W_LANE = 1.0
W_CROSS = 0.25
W_SYNERGY = 0.5
W_COMPOSITION = 1.0
W_THREAT = 0.5


class DecisionEngine:
    def __init__(self, config: Config, dataset: Dataset):
        self.cfg = config
        self.ds = dataset
        self.meta = MetaEngine(config, dataset)
        self.matchup = MatchupEngine(config, dataset, self.meta)
        self.synergy = SynergyEngine(config, dataset, self.meta)
        self.composition = CompositionEngine(config, dataset)
        self.threat = ThreatEngine(config, dataset)
        self.role_inf = RoleInferenceEngine(config, dataset, self.meta)
        self.future = FutureDraftEngine(config, dataset, self.meta, self.matchup, self.role_inf)
        self.future._synergy = self.synergy
        self.mode = self._detect_mode()
        self._rule_registry = None
        try:
            from engine.knowledge.rules.registry import RuleRegistry
            reg = RuleRegistry(config.game_rules_dir)
            if reg.all():
                self._rule_registry = reg
        except Exception:
            pass

    def _detect_mode(self) -> EvalMode:
        model_file = self.cfg.datasets_dir / "calibrated_model.json"
        if model_file.exists():
            import json
            meta = json.loads(model_file.read_text(encoding="utf-8"))
            if meta.get("calibration_gate_passed"):
                return EvalMode.CALIBRATED
            return EvalMode.PROVISIONAL
        return EvalMode.HEURISTIC

    # ---------- completed-draft win model (heuristic baseline) ----------
    def completed_draft_logodds(self, ally: list[tuple[int, Role]],
                                enemy: list[tuple[int, Role]]) -> float:
        lo = 0.0
        for cid, role in ally:
            lo += W_MAIN * self.meta.logodds(cid, role)
        for cid, role in enemy:
            lo -= W_MAIN * self.meta.logodds(cid, role)
        for acid, arole in ally:
            for ecid, erole in enemy:
                rel = RelationType.SAME_LANE if arole == erole else RelationType.CROSS_TEAM
                d = self.matchup.delta(acid, arole, ecid, erole, rel)
                w = W_LANE if rel == RelationType.SAME_LANE else W_CROSS
                lo += w * d["logodds"] * d["confidence"]
        for team, sign in ((ally, 1.0), (enemy, -1.0)):
            for i in range(len(team)):
                for j in range(i + 1, len(team)):
                    s = self.synergy.pair(team[i][0], team[i][1], team[j][0], team[j][1])
                    lo += sign * W_SYNERGY * s["logodds"] * s["confidence"]
        lo += W_COMPOSITION * (self.composition.team_power_terms(ally)
                               - self.composition.team_power_terms(enemy))
        for cid, role in ally:
            lo += W_THREAT * self.threat.exposure(cid, enemy)["logodds"]
        for cid, role in enemy:
            lo -= W_THREAT * self.threat.exposure(cid, ally)["logodds"]
        return lo

    def win_model(self, ally, enemy) -> float:
        return sigmoid(self.completed_draft_logodds(ally, enemy))

    # ---------- candidate evaluation ----------
    def _plausible_for_role(self, cid: int, role: Role) -> bool:
        return role in self.role_inf.plausible_roles(cid)

    def _fast_evaluate(self, draft: DraftState, cid: int, role: Role,
                       enemies: list[tuple[int, Role]], allies: list[tuple[int, Role]],
                       role_dist) -> CandidateEvaluation:
        contributions = []
        evidence_ids = []
        confidences = []

        meta_ev = self.meta.signal(cid, role)
        meta_lo = self.meta.logodds(cid, role)
        contributions.append({"component": "meta_main_effect", "logodds": round(meta_lo, 5),
                              "weight": W_MAIN, "unit": "LOG_ODDS"})
        evidence_ids.append(meta_ev.signal_id)
        confidences.append(self.meta.role_strength(cid, role)["confidence"])

        # lane + cross matchup vs known enemies (role uncertainty handled via marginals)
        matchup_lo = 0.0
        for ecid, erole in enemies:
            if erole is not None:
                rel = RelationType.SAME_LANE if erole == role else RelationType.CROSS_TEAM
                d = self.matchup.delta(cid, role, ecid, erole, rel)
                w = W_LANE if rel == RelationType.SAME_LANE else W_CROSS
                matchup_lo += w * d["logodds"] * d["confidence"]
                if d["evidence"]:
                    evidence_ids.append(d["evidence"].signal_id)
                    confidences.append(d["confidence"])
            else:
                # uncertain enemy role: expectation over marginal distribution
                for r in ALL_ROLES:
                    p = role_dist.role_prob(ecid, r)
                    if p <= 0.01:
                        continue
                    rel = RelationType.SAME_LANE if r == role else RelationType.CROSS_TEAM
                    d = self.matchup.delta(cid, role, ecid, r, rel)
                    w = W_LANE if rel == RelationType.SAME_LANE else W_CROSS
                    matchup_lo += p * w * d["logodds"] * d["confidence"]
                    if d["evidence"]:
                        evidence_ids.append(d["evidence"].signal_id)
        contributions.append({"component": "matchup_effects", "logodds": round(matchup_lo, 5),
                              "weight": 1.0, "unit": "LOG_ODDS"})

        synergy_lo = 0.0
        for aid, arole in allies:
            s = self.synergy.pair(cid, role, aid, arole)
            synergy_lo += W_SYNERGY * s["logodds"] * s["confidence"]
            if s["evidence"]:
                evidence_ids.append(s["evidence"].signal_id)
                confidences.append(s["confidence"])
        contributions.append({"component": "ally_synergy", "logodds": round(synergy_lo, 5),
                              "weight": W_SYNERGY, "unit": "LOG_ODDS"})

        comp = self.composition.marginal_fit(cid, allies)
        contributions.append({"component": "composition_fit", "logodds": comp["logodds"],
                              "weight": W_COMPOSITION, "unit": "LOG_ODDS",
                              "detail": comp["contributions"]})
        evidence_ids.append(comp["evidence"].signal_id)

        thr = self.threat.exposure(cid, enemies)
        contributions.append({"component": "enemy_threat", "logodds": thr["logodds"],
                              "weight": W_THREAT, "unit": "LOG_ODDS",
                              "detail": {k: round(v, 4) for k, v in thr["components"].items()}})
        if thr["evidence"]:
            evidence_ids.append(thr["evidence"].signal_id)

        # Verified game rules (§22.8): ONLY verified/active rules, ONLY where
        # observed matchup data is missing (double-counting guard §23.5).
        rule_lo = 0.0
        rule_ids = []
        if self._rule_registry is not None:
            for ecid, erole in enemies:
                if erole is not None and erole != role:
                    continue
                d = self.matchup.delta(cid, role, ecid, erole or role, RelationType.SAME_LANE)
                if d["kind"] != "missing":
                    continue  # observed/legacy data already carries this information
                for r in self._rule_registry.active_rules():
                    if (r.get("relation") == "LANE_PRESSURE_ADVANTAGE"
                            and r.get("subject", {}).get("champion_id") == cid
                            and r.get("target", {}).get("champion_id") == ecid):
                        rule_lo += 0.05  # documented small prior; not a win guarantee
                        rule_ids.append(r["rule_id"])
        if rule_ids:
            contributions.append({"component": "rule_effects", "logodds": round(rule_lo, 5),
                                  "unit": "LOG_ODDS", "rule_ids": rule_ids,
                                  "note": "verified rules, data-missing fallback only"})

        total = meta_lo + matchup_lo + synergy_lo + comp["logodds"] + thr["logodds"] + rule_lo
        data_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return CandidateEvaluation(
            champion_id=cid, role=role, evaluation_mode=self.mode,
            ranking_score=round(total, 5),
            confidence=round(min(1.0, data_conf), 4),
            feature_contributions=contributions,
            evidence_ids=evidence_ids,
            model_version=MODEL_VERSION, dataset_id=self.ds.dataset_id,
        )

    def recommend(self, draft: DraftState, mc_samples: int | None = None,
                  seed: int | None = None) -> Recommendation:
        t0 = time.monotonic()
        role = draft.user_role
        enemies = enemy_known(draft)
        allies = ally_known(draft)
        role_dist = self.role_inf.infer(enemies)
        has_future = bool(future_steps(draft))

        candidates = [cid for cid in draft.available_ids if self._plausible_for_role(cid, role)]
        if not candidates:
            candidates = list(draft.available_ids)  # no role evidence: evaluate all, flag it

        fast = [self._fast_evaluate(draft, cid, role, enemies, allies, role_dist)
                for cid in candidates]
        fast.sort(key=lambda e: (-e.ranking_score, e.champion_id))
        beam = fast[:self.cfg.engine.beam_candidates]

        # future draft evaluation for the beam (GLOBAL time budget, §16).
        # 85% allocated to MC; remainder covers fast-path + schema validation overhead.
        if has_future:
            deadline = t0 + 0.85 * self.cfg.engine.time_budget_s
            for ev in beam:
                fut = self.future.evaluate(draft, ev.champion_id, role_dist,
                                           self.win_model, mc_samples, seed,
                                           deadline=deadline)
                ev.expected_future_draft_value = fut["expected"]
                ev.downside_risk = fut["downside"]
                ev.mc_standard_error = fut["mc_se"]
                ev.draft_uncertainty = fut["draft_uncertainty"]
                if fut["expected"] is not None:
                    # blend current-draft log-odds with simulated future expectation
                    future_lo = logit(fut["expected"])
                    ra = self.cfg.engine.risk_aversion
                    risk_penalty = ra * max(0.0, future_lo - logit(fut["downside"] or fut["expected"]))
                    ev.ranking_score = round(future_lo - risk_penalty, 5)
                    ev.ranking_scale = "log_odds_future_expected"
                    ev.feature_contributions.append(
                        {"component": "future_draft_expectation", "logodds": round(future_lo, 5),
                         "unit": "LOG_ODDS", "n_samples": fut["n_actual"],
                         "mc_standard_error": fut["mc_se"]})
            beam.sort(key=lambda e: (-e.ranking_score, e.champion_id))

        best = beam[0] if beam else None
        limitations = []
        if self.mode == EvalMode.HEURISTIC:
            limitations.append("HEURISTIC mod: ranking_score kalibre edilmiş kazanma olasılığı DEĞİLDİR; "
                               "maç-seviyesi eğitim verisi (Riot API) olmadan predicted_win_probability üretilmez.")
        if best and self.ds.champions.get(best.champion_id, {}).get(
                "overall_win_rate_quality", {}).get("status") == "legacy_unverified":
            limitations.append("Öneri kısmen legacy (iron, ham WR'si kayıp) verilere dayanıyor; LoG emerald+ verisi geldikçe güncellenir.")
        if best is None:
            limitations.append("Geçerli aday bulunamadı (tüm şampiyonlar seçilmiş/yasaklı veya rol verisi yok).")
        if role_dist.uncertainty > 0.3:
            limitations.append(f"Rakip rol belirsizliği yüksek (entropy={role_dist.uncertainty}); sıralama buna göre hassas.")
        if not has_future:
            limitations.append("Draft tamamlanmış: gelecek seçim simülasyonu gerekmedi.")
        missing_role_data = [cid for cid in candidates if not self.ds.champions.get(cid, {}).get("roles")
                             and not any(r["champion_id"] == cid for r in self.ds.role_stats)]
        if missing_role_data:
            limitations.append(f"{len(missing_role_data)} şampiyonun rol verisi yok (yeni şampiyon); tüm roller değerlendirildi.")

        explanations = []
        if best:
            name = self.ds.champions.get(best.champion_id, {}).get("name", str(best.champion_id))
            top_terms = sorted(best.feature_contributions,
                               key=lambda c: -abs(c.get("logodds", 0)))[:3]
            explanations.append(
                f"{name} ({role.value}): toplam {best.ranking_score} log-odds. "
                + "; ".join(f"{t['component']}={t['logodds']:+.3f}" for t in top_terms))
            if best.expected_future_draft_value is not None:
                explanations.append(
                    f"Gelecek draft simülasyonu: beklenen kazanma oranı %{best.expected_future_draft_value*100:.1f} "
                    f"(MC ±{best.mc_standard_error*100:.1f}pp, kötü senaryo %{(best.downside_risk or 0)*100:.1f}).")

        alternatives = []
        for ev in beam[1:3]:
            alternatives.append({
                "champion_id": ev.champion_id,
                "name": self.ds.champions.get(ev.champion_id, {}).get("name"),
                "ranking_score": ev.ranking_score,
                "delta_vs_best": round(ev.ranking_score - best.ranking_score, 5) if best else None,
                "confidence": ev.confidence,
                "expected_future_draft_value": ev.expected_future_draft_value,
            })

        rec = Recommendation(
            draft_id=draft.draft_id, model_version=MODEL_VERSION,
            dataset_id=self.ds.dataset_id,
            recommended_champion_id=best.champion_id if best else None,
            recommended_role=role if best else None,
            predicted_win_probability=None,  # ONLY in CALIBRATED mode
            ranking_score=best.ranking_score if best else None,
            confidence=best.confidence if best else None,
            evaluation_mode=self.mode,
            evidence={
                "meta": {"signal_ids": [i for i in (best.evidence_ids if best else [])][:1]},
                "lane_matchup": {"enemy_role_uncertainty": role_dist.uncertainty},
                "team_synergy": {"ally_count": len(allies)},
                "enemy_threat": {"known_enemies": len(enemies)},
                "future_draft": {"simulated": has_future,
                                 "samples": (best.expected_future_draft_value is not None)},
            },
            risk={
                "counterpick_exposure": round((best.downside_risk or 0), 5) if best else None,
                "role_uncertainty": role_dist.uncertainty,
                "data_uncertainty": round(1.0 - (best.confidence or 0), 4) if best else None,
            },
            alternatives=alternatives,
            explanations=explanations,
            source_references=[{"dataset_id": self.ds.dataset_id,
                                "patch": self.ds.manifest["patch"],
                                "providers": [s["provider"] for s in self.ds.manifest.get("sources", [])]}],
            limitations=limitations,
            candidates=beam,
            status="evaluated_heuristic" if self.mode == EvalMode.HEURISTIC else "evaluated",
        )
        rec.explanations.append(f"Hesap süresi: {time.monotonic()-t0:.2f}s")
        rec_dict = rec.to_dict()
        from engine.contracts.schema import validate_record
        validate_record("recommendation", rec_dict)
        for ev in beam:
            validate_record("candidate_evaluation", ev.to_dict())
        # audit trail (§4): every ranking reproducible from draft + dataset + model
        try:
            from engine.data.audit import AuditLog
            AuditLog(self.cfg.datasets_dir / "audit").record(rec_dict, draft.to_dict())
        except Exception:
            pass  # audit failure must never break the decision path
        return rec
