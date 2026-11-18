"""Professional Draft Panel (kutsal_amac.md §16).

Editable team slots, bans, role selector, patch/rank/dataset info, known/unknown
enemy role indicators, pick-order display, main recommendation + two
alternatives + evidence + reliability + counter risk, and an async Qwen area.
Every change triggers a debounced recalculation; numeric results arrive first,
the LLM explanation never blocks them.
"""
from __future__ import annotations

import json

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPlainTextEdit, QLineEdit, QGroupBox,
)

from engine.config import DEFAULT_CONFIG
from engine.contracts.types import Role, ALL_ROLES, normalize_role
from engine.data.store import DatasetStore
from engine.engines.decision import DecisionEngine
from engine.engines.draft import build_draft, future_steps, DraftError

ROLE_CHOICES = ["Unknown"] + [r.value for r in ALL_ROLES]


class PanelWorker(QThread):
    numeric_ready = pyqtSignal(dict)
    llm_ready = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, ally_ids, enemy_ids, enemy_roles, ban_ids, role, user_team,
                 with_llm=True, parent=None):
        super().__init__(parent)
        self.args = (ally_ids, enemy_ids, enemy_roles, ban_ids, role, user_team)
        self.with_llm = with_llm

    def run(self):
        try:
            cfg = DEFAULT_CONFIG
            ds = DatasetStore(cfg.datasets_dir).latest()
            if ds is None:
                self.failed.emit("Veri seti yok: python -m engine.cli ingest")
                return
            ally, enemy, eroles, bans, role, team = self.args
            draft = build_draft(ds, role, ally, enemy, bans, team,
                                enemy_roles=eroles)
            eng = DecisionEngine(cfg, ds)
            rec = eng.recommend(draft)
            self.numeric_ready.emit(rec.to_dict())
            if self.with_llm and not self.isInterruptionRequested():
                from engine.llm.coach import explain_recommendation
                self.llm_ready.emit(explain_recommendation(cfg, ds, rec))
        except DraftError as e:
            self.failed.emit(f"Draft: {e}")
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


class DraftPanel(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Draft Intelligence Engine — Professional Panel")
        self.resize(1050, 760)
        self.cfg = DEFAULT_CONFIG
        self.ds = DatasetStore(self.cfg.datasets_dir).latest()
        self.champ_names = sorted(
            [c["name"] for c in self.ds.champions.values()]) if self.ds else []
        self._worker = None
        self._workers = []
        self._build_ui()
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(500)
        self._debounce.timeout.connect(self.recalc)

    # ---------- UI ----------
    def _champ_combo(self):
        cb = QComboBox()
        cb.addItem("(empty)")
        cb.addItems(self.champ_names)
        cb.currentIndexChanged.connect(lambda _: self._debounce.start())
        return cb

    def _build_ui(self):
        root = QVBoxLayout(self)
        info = QLabel(self._info_text())
        info.setStyleSheet("color:#8b949e;")
        root.addWidget(info)
        self.info_label = info

        grid = QGridLayout()
        # ally column
        ally_box = QGroupBox("My Team (BLUE)")
        al = QVBoxLayout(ally_box)
        self.ally_combos = []
        for i in range(5):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"Slot {i+1}"))
            cb = self._champ_combo()
            self.ally_combos.append(cb)
            row.addWidget(cb)
            al.addLayout(row)
        grid.addWidget(ally_box, 0, 0)

        # center controls
        center = QGroupBox("Draft Controls")
        cl = QVBoxLayout(center)
        self.user_team = QComboBox()
        self.user_team.addItems(["BLUE", "RED"])
        self.user_team.currentIndexChanged.connect(lambda _: self._debounce.start())
        self.user_role = QComboBox()
        self.user_role.addItems([r.value for r in ALL_ROLES])
        self.user_role.setCurrentText("MIDDLE")
        self.user_role.currentIndexChanged.connect(lambda _: self._debounce.start())
        cl.addWidget(QLabel("My team:"))
        cl.addWidget(self.user_team)
        cl.addWidget(QLabel("My role:"))
        cl.addWidget(self.user_role)
        cl.addWidget(QLabel("Bans (comma separated):"))
        self.bans_edit = QLineEdit()
        self.bans_edit.setPlaceholderText("Yasuo, Yone")
        self.bans_edit.textChanged.connect(lambda _: self._debounce.start())
        cl.addWidget(self.bans_edit)
        self.order_label = QLabel("Pick order: —")
        self.order_label.setStyleSheet("color:#8b949e;")
        cl.addWidget(self.order_label)
        self.mode_label = QLabel("")
        cl.addWidget(self.mode_label)
        grid.addWidget(center, 0, 1)

        # enemy column with role indicators
        enemy_box = QGroupBox("Enemy Team (RED)")
        el = QVBoxLayout(enemy_box)
        self.enemy_combos = []
        self.enemy_role_combos = []
        for i in range(5):
            row = QHBoxLayout()
            cb = self._champ_combo()
            rc = QComboBox()
            rc.addItems(ROLE_CHOICES)
            rc.setFixedWidth(110)
            rc.currentIndexChanged.connect(lambda _: self._debounce.start())
            self.enemy_combos.append(cb)
            self.enemy_role_combos.append(rc)
            row.addWidget(cb)
            row.addWidget(rc)
            el.addLayout(row)
        grid.addWidget(enemy_box, 0, 2)
        root.addLayout(grid)

        root.addWidget(QLabel("Numeric recommendation (decision engine):"))
        self.numeric = QPlainTextEdit()
        self.numeric.setReadOnly(True)
        self.numeric.setStyleSheet("background:#0d1117;color:#e6edf3;font-family:Consolas;")
        root.addWidget(self.numeric, stretch=2)
        root.addWidget(QLabel("Qwen explanation (async, never re-ranks):"))
        self.llm = QPlainTextEdit()
        self.llm.setReadOnly(True)
        self.llm.setStyleSheet("background:#0d1117;color:#c9d1d9;font-family:Consolas;")
        root.addWidget(self.llm, stretch=2)

    def _info_text(self) -> str:
        if not self.ds:
            return "Dataset yok — ingest çalıştırın."
        m = self.ds.manifest
        return (f"Patch: {m.get('patch')} | Rank: {self.cfg.engine.rank_scope} | "
                f"Dataset: {m.get('dataset_id')} | Sources: "
                f"{', '.join(s['provider'] for s in m.get('sources', []))}")

    # ---------- state ----------
    def _ids(self, combos):
        out = []
        for cb in combos:
            name = cb.currentText()
            if name == "(empty)" or not self.ds:
                continue
            cid = self.ds.resolve_id(name)
            if cid is not None:
                out.append(cid)
        return out

    def apply_lcu_state(self, my_team, enemy_team, my_role, bans=None, enemy_roles=None):
        """Live champ-select feed (§16: recalc on every pick change)."""
        for i, cb in enumerate(self.ally_combos):
            name = my_team[i] if i < len(my_team) else "..."
            cb.setCurrentText(name if name in self.champ_names else "(empty)")
        for i, cb in enumerate(self.enemy_combos):
            name = enemy_team[i] if i < len(enemy_team) else "..."
            cb.setCurrentText(name if name in self.champ_names else "(empty)")
        for i, rc in enumerate(self.enemy_role_combos):
            r = enemy_roles[i] if enemy_roles and i < len(enemy_roles) else None
            nr = normalize_role(r)  # LCU "Top"/"ADC" -> canonical TOP/BOTTOM
            rc.setCurrentText(nr.value if nr else "Unknown")
        role = normalize_role(my_role)
        if role:
            self.user_role.setCurrentText(role.value)
        if bans:
            self.bans_edit.setText(", ".join(b for b in bans if b not in ("Picking...", "Unknown")))
        self._debounce.start()

    # ---------- recalc ----------
    def recalc(self):
        if not self.ds:
            self.numeric.setPlainText("Dataset yok.")
            return
        ally = self._ids(self.ally_combos)
        enemy = self._ids(self.enemy_combos)
        eroles = []
        for i, rc in enumerate(self.enemy_role_combos):
            txt = rc.currentText()
            eroles.append(normalize_role(txt) if txt != "Unknown" else None)
        bans = []
        for part in self.bans_edit.text().split(","):
            cid = self.ds.resolve_id(part.strip())
            if cid is not None:
                bans.append(cid)
        role = Role(self.user_role.currentText())
        team = self.user_team.currentText()
        try:
            draft = build_draft(self.ds, role, ally, enemy, bans, team, enemy_roles=eroles)
            steps = future_steps(draft)
            self.order_label.setText(
                f"Pick order: user now, {len(steps)} future pick(s) | "
                f"available: {len(draft.available_ids)}")
        except DraftError as e:
            self.numeric.setPlainText(f"Draft hatası: {e}")
            return
        self.mode_label.setText("Computing…")
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()  # skip pending LLM work of superseded run
        self._worker = PanelWorker(ally, enemy, eroles, bans, role, team, parent=self)
        self._workers.append(self._worker)
        self._worker.numeric_ready.connect(self._show_numeric)
        self._worker.llm_ready.connect(self._show_llm)
        self._worker.failed.connect(lambda m: self.numeric.setPlainText("HATA: " + m))
        self._worker.finished.connect(lambda: self._retire(self._worker))
        self._worker.start()

    def _retire(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()

    def closeEvent(self, event):
        for w in list(self._workers):
            w.requestInterruption()
            w.wait(2000)
            if w.isRunning():
                w.terminate()
                w.wait(500)
        super().closeEvent(event)

    def _show_numeric(self, rec):
        from core.engine_adapter import format_numeric
        self.numeric.setPlainText(format_numeric(rec, self.ds.champions))
        self.mode_label.setText(f"Mode: {rec.get('evaluation_mode')} | status: {rec.get('status')}")

    def _show_llm(self, out):
        self.llm.setPlainText(json.dumps(out, ensure_ascii=False, indent=2))
