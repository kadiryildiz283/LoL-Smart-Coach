"""Modern single-window Draft Intelligence GUI (default entry point).

One frameless glassmorphism window: team slots with champion icons, role
selectors, bans, pick order, hero recommendation + two alternatives, evidence
contribution bars, risk chips, limitations, and an async Qwen coach panel.
Live LCU feed recalculates on every champ-select change. Legacy UI remains
available via `python main.py --legacy`.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import QPixmap, QFont, QPainter, QColor
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel,
    QComboBox, QLineEdit, QProgressBar, QPlainTextEdit, QScrollArea, QWidget,
)

from core.modern_window import ModernWindow
from core.draft_panel import PanelWorker
from core.lcu_connector import LCUWorker
from engine.config import DEFAULT_CONFIG
from engine.contracts.types import Role, ALL_ROLES, normalize_role
from engine.data.store import DatasetStore

ACCENT = "#22d3ee"
GREEN = "#34d399"
RED = "#f87171"
AMBER = "#fbbf24"
MUTED = "#8b949e"
CARD = "#10161f"
BORDER = "#1f2937"

QSS = f"""
QWidget {{ font-family: 'Segoe UI', 'Inter', sans-serif; color: #e6edf3; }}
QFrame#Card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#Hero {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
    stop:0 #0e1a24, stop:1 #10161f); border: 1px solid #164e63; border-radius: 12px; }}
QLabel#H1 {{ font-size: 17px; font-weight: 700; color: #e6edf3; }}
QLabel#H2 {{ font-size: 12px; font-weight: 700; color: {MUTED}; letter-spacing: 1px; }}
QLabel#Chip {{ background: #161b22; border: 1px solid {BORDER}; border-radius: 9px;
    padding: 2px 9px; font-size: 10px; color: {MUTED}; }}
QLabel#RiskChip {{ background: #1c1210; border: 1px solid #7f1d1d; border-radius: 9px;
    padding: 2px 9px; font-size: 10px; color: {RED}; }}
QLabel#Warn {{ color: {AMBER}; font-size: 10px; }}
QComboBox {{ background: #161b22; border: 1px solid {BORDER}; border-radius: 7px;
    padding: 4px 8px; color: #e6edf3; font-size: 11px; }}
QComboBox:hover {{ border-color: #3b82f6; }}
QComboBox QAbstractItemView {{ background: #161b22; border: 1px solid {BORDER};
    selection-background-color: #1f6feb; color: #e6edf3; }}
QLineEdit {{ background: #161b22; border: 1px solid {BORDER}; border-radius: 7px;
    padding: 4px 8px; color: #e6edf3; font-size: 11px; }}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QProgressBar {{ background: #161b22; border: 1px solid {BORDER}; border-radius: 6px;
    height: 14px; text-align: center; color: #c9d1d9; font-size: 9px; }}
QProgressBar::chunk {{ border-radius: 5px; background: {ACCENT}; }}
QPlainTextEdit {{ background: #0a0e14; border: 1px solid {BORDER}; border-radius: 8px;
    color: #c9d1d9; font-family: 'Consolas', monospace; font-size: 11px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: #0d1117; width: 8px; border-radius: 4px; }}
QScrollBar::handle:vertical {{ background: #30363d; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def _dd_key_map() -> tuple[dict[int, str], str]:
    """champion_id -> Data Dragon image key + cdn version, from raw cache."""
    root = DEFAULT_CONFIG.datasets_dir / "_staging"
    keymap: dict[int, str] = {}
    version = "16.23.1"
    for d in sorted(root.glob("data_dragon-*")):
        for f in d.glob("*.json"):
            try:
                body = json.loads(f.read_text(encoding="utf-8")).get("body", {})
            except Exception:
                continue
            if isinstance(body, list) and body and isinstance(body[0], str):
                version = body[0]
            data = body.get("data") if isinstance(body, dict) else None
            if isinstance(data, dict) and len(data) > 100:
                for k, v in data.items():
                    try:
                        keymap[int(v["key"])] = k
                    except Exception:
                        pass
    return keymap, version


class ContributionBar(QWidget):
    """Center-zero log-odds bar: green right of zero, red left, value at right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0.0
        self.missing = False
        self.setMinimumHeight(16)

    def set_value(self, lo: float, missing: bool = False):
        self.value = lo
        self.missing = missing
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        mid = r.center().x()
        p.setPen(QColor("#30363d"))
        p.drawLine(mid, r.top() + 2, mid, r.bottom() - 2)
        frac = min(1.0, abs(self.value) / 0.3)
        w = (r.width() / 2 - 46) * frac
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#30363d" if self.missing else (GREEN if self.value >= 0 else RED)))
        if self.value >= 0:
            p.drawRoundedRect(QRectF(mid, r.top() + 3, w, r.height() - 6), 3, 3)
        else:
            p.drawRoundedRect(QRectF(mid - w, r.top() + 3, w, r.height() - 6), 3, 3)
        p.setPen(QColor("#c9d1d9"))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(r.adjusted(0, 0, -4, 0),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   "veri yok" if self.missing else f"{self.value:+.3f}")


class IconWorker(QThread):
    icon_ready = pyqtSignal(int, str)

    def __init__(self, ids, parent=None):
        super().__init__(parent)
        self.ids = list(ids)
        self.keymap, self.version = _dd_key_map()
        self.cache = DEFAULT_CONFIG.datasets_dir / "_icons"
        self.cache.mkdir(parents=True, exist_ok=True)

    def run(self):
        for cid in self.ids:
            path = self.cache / f"{cid}.png"
            if not path.exists():
                key = self.keymap.get(cid)
                if not key:
                    continue
                url = f"https://ddragon.leagueoflegends.com/cdn/{self.version}/img/champion/{key}.png"
                try:
                    with urllib.request.urlopen(url, timeout=15) as r:
                        path.write_bytes(r.read())
                except Exception:
                    continue
            self.icon_ready.emit(cid, str(path))


class ModernApp(ModernWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DRAFT INTELLIGENCE ENGINE")
        self.resize(1420, 900)
        self.cfg = DEFAULT_CONFIG
        self.ds = DatasetStore(self.cfg.datasets_dir).latest()
        self.champ_names = sorted(c["name"] for c in self.ds.champions.values()) if self.ds else []
        self.setStyleSheet(QSS)
        self._worker = None
        self._icon_workers = []
        self._icon_labels: dict[int, list[QLabel]] = {}
        self._prev_score = None
        self.eng = None
        if self.ds:
            from engine.engines.decision import DecisionEngine
            self.eng = DecisionEngine(self.cfg, self.ds)
        self._build_ui()
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(450)
        self._debounce.timeout.connect(self.recalc)
        self._start_lcu()
        QTimer.singleShot(200, self.recalc)

    # ---------------- UI ----------------
    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)
        h = QLabel(title)
        h.setObjectName("H2")
        lay.addWidget(h)
        return card, lay

    def _champ_combo(self) -> QComboBox:
        cb = QComboBox()
        cb.addItem("(empty)")
        cb.addItems(self.champ_names)
        cb.currentIndexChanged.connect(lambda _: self._debounce.start())
        return cb

    def _icon_label(self, size: int) -> QLabel:
        lbl = QLabel()
        lbl.setFixedSize(size, size)
        lbl.setStyleSheet(f"background:#161b22; border-radius:{size//5}px; border:1px solid {BORDER};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    def _build_ui(self):
        root = self.content_layout
        root.setContentsMargins(16, 8, 16, 14)
        root.setSpacing(10)

        # header
        head = QHBoxLayout()
        t = QLabel("⬡ DRAFT INTELLIGENCE")
        t.setObjectName("H1")
        head.addWidget(t)
        self.chips = {}
        for key in ("patch", "rank", "dataset", "mode"):
            c = QLabel("—")
            c.setObjectName("Chip")
            self.chips[key] = c
            head.addWidget(c)
        head.addStretch()
        self.lcu_pill = QLabel("● LCU: aranıyor")
        self.lcu_pill.setObjectName("Chip")
        head.addWidget(self.lcu_pill)
        root.addLayout(head)
        self._refresh_chips()

        body = QHBoxLayout()
        body.setSpacing(10)

        # my team
        my_card, my_lay = self._card("MY TEAM")
        self.ally_rows = []
        for i in range(5):
            row = QHBoxLayout()
            icon = self._icon_label(38)
            cb = self._champ_combo()
            rl = QLabel("—")
            rl.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            rl.setFixedWidth(58)
            row.addWidget(icon)
            row.addWidget(cb, 1)
            row.addWidget(rl)
            my_lay.addLayout(row)
            self.ally_rows.append((icon, cb, rl))
        my_lay.addStretch()
        body.addWidget(my_card, 2)

        # center
        center = QVBoxLayout()
        center.setSpacing(10)
        ctrl = QFrame()
        ctrl.setObjectName("Card")
        cl = QHBoxLayout(ctrl)
        cl.setContentsMargins(12, 8, 12, 8)
        cl.addWidget(QLabel("Role"))
        self.role_cb = QComboBox()
        self.role_cb.addItems([r.value for r in ALL_ROLES])
        self.role_cb.setCurrentText("MIDDLE")
        self.role_cb.currentIndexChanged.connect(lambda _: self._debounce.start())
        cl.addWidget(self.role_cb)
        cl.addWidget(QLabel("Side"))
        self.side_cb = QComboBox()
        self.side_cb.addItems(["BLUE", "RED"])
        self.side_cb.currentIndexChanged.connect(lambda _: self._debounce.start())
        cl.addWidget(self.side_cb)
        cl.addWidget(QLabel("Bans"))
        self.bans_edit = QLineEdit()
        self.bans_edit.setPlaceholderText("Yasuo, Yone")
        self.bans_edit.textChanged.connect(lambda _: self._debounce.start())
        cl.addWidget(self.bans_edit, 1)
        self.order_lbl = QLabel("—")
        self.order_lbl.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        cl.addWidget(self.order_lbl)
        center.addWidget(ctrl)

        hero = QFrame()
        hero.setObjectName("Hero")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(16, 14, 16, 14)
        hl.setSpacing(14)
        self.hero_icon = self._icon_label(86)
        hl.addWidget(self.hero_icon)
        hv = QVBoxLayout()
        self.hero_name = QLabel("—")
        self.hero_name.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.hero_tag = QLabel("")
        self.hero_tag.setStyleSheet(f"color:{ACCENT}; font-size:11px;")
        self.hero_why = QLabel("")
        self.hero_why.setWordWrap(True)
        self.hero_why.setStyleSheet("color:#c9d1d9; font-size:11px;")
        hv.addWidget(self.hero_name)
        hv.addWidget(self.hero_tag)
        hv.addWidget(self.hero_why)
        hl.addLayout(hv, 1)
        sv = QVBoxLayout()
        self.hero_score = QLabel("—")
        self.hero_score.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self.hero_score.setStyleSheet(f"color:{GREEN};")
        self.hero_score.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 100)
        self.conf_bar.setFormat("%p%")
        self.conf_bar.setFixedWidth(150)
        conf_row = QHBoxLayout()
        conf_lbl = QLabel("confidence")
        conf_lbl.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        conf_row.addWidget(conf_lbl)
        conf_row.addWidget(self.conf_bar)
        sv.addWidget(self.hero_score)
        sv.addLayout(conf_row)
        sv.addStretch()
        hl.addLayout(sv)
        center.addWidget(hero)

        alt_row = QHBoxLayout()
        self.alt_cards = []
        for i in range(2):
            ac = QFrame()
            ac.setObjectName("Card")
            al = QHBoxLayout(ac)
            al.setContentsMargins(10, 8, 10, 8)
            ai = self._icon_label(40)
            av = QVBoxLayout()
            an = QLabel("—")
            an.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            asc = QLabel("")
            asc.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            av.addWidget(an)
            av.addWidget(asc)
            al.addWidget(ai)
            al.addLayout(av, 1)
            alt_row.addWidget(ac)
            self.alt_cards.append((ai, an, asc))
        center.addLayout(alt_row)

        ev_card, ev_lay = self._card("EVIDENCE (log-odds contributions)")
        self.ev_bars: list[tuple[QLabel, ContributionBar]] = []
        for i in range(6):
            row = QHBoxLayout()
            lb = QLabel("")
            lb.setFixedWidth(150)
            lb.setStyleSheet("font-size:10px; color:#c9d1d9;")
            bar = ContributionBar()
            row.addWidget(lb)
            row.addWidget(bar, 1)
            ev_lay.addLayout(row)
            self.ev_bars.append((lb, bar))
        self.enemy_impact_lbl = QLabel("KARŞI ETKİSİ (aday vs her rakip, log-odds)")
        self.enemy_impact_lbl.setObjectName("H2")
        ev_lay.addWidget(self.enemy_impact_lbl)
        self.enemy_bars: list[tuple[QLabel, ContributionBar]] = []
        for i in range(5):
            row = QHBoxLayout()
            lb = QLabel("")
            lb.setFixedWidth(150)
            lb.setStyleSheet("font-size:10px; color:#c9d1d9;")
            bar = ContributionBar()
            row.addWidget(lb)
            row.addWidget(bar, 1)
            ev_lay.addLayout(row)
            self.enemy_bars.append((lb, bar))
        self.risk_row = QHBoxLayout()
        ev_lay.addLayout(self.risk_row)
        self.warn_lbl = QLabel("")
        self.warn_lbl.setObjectName("Warn")
        self.warn_lbl.setWordWrap(True)
        ev_lay.addWidget(self.warn_lbl)
        center.addWidget(ev_card, 1)
        body.addLayout(center, 5)

        # enemy team
        en_card, en_lay = self._card("ENEMY TEAM")
        self.enemy_rows = []
        for i in range(5):
            row = QHBoxLayout()
            icon = self._icon_label(38)
            cb = self._champ_combo()
            rc = QComboBox()
            rc.addItems(["Unknown"] + [r.value for r in ALL_ROLES])
            rc.setFixedWidth(92)
            rc.currentIndexChanged.connect(lambda _: self._debounce.start())
            row.addWidget(icon)
            row.addWidget(cb, 1)
            row.addWidget(rc)
            en_lay.addLayout(row)
            self.enemy_rows.append((icon, cb, rc))
        en_lay.addStretch()
        body.addWidget(en_card, 2)
        root.addLayout(body, 1)

        # coach
        coach_card, coach_lay = self._card("QWEN COACH — async explanation (never re-ranks)")
        self.coach = QPlainTextEdit()
        self.coach.setReadOnly(True)
        self.coach.setPlaceholderText("Qwen açıklaması sayısal karardan sonra gelir…")
        coach_lay.addWidget(self.coach)
        root.addWidget(coach_card, 1)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        root.addWidget(self.status_lbl)

    def _refresh_chips(self):
        if not self.ds:
            return
        m = self.ds.manifest
        self.chips["patch"].setText(f"PATCH {m.get('patch')}")
        self.chips["rank"].setText(self.cfg.engine.rank_scope)
        self.chips["dataset"].setText(m.get("dataset_id", "")[-12:])
        self.chips["mode"].setText("HEURISTIC")

    # ---------------- live LCU ----------------
    def _start_lcu(self):
        try:
            self.lcu = LCUWorker()
            self.lcu.connection_status.connect(self._lcu_status)
            self.lcu.champ_select_update.connect(self._lcu_update)
            self.lcu.start()
        except Exception as e:
            self.lcu_pill.setText(f"● LCU: {type(e).__name__}")

    def _lcu_status(self, msg):
        ok = "Bağlandı" in msg or "Connected" in msg
        self.lcu_pill.setText(("● " if ok else "○ ") + msg)
        self.lcu_pill.setStyleSheet(
            f"background:#161b22; border:1px solid {'#14532d' if ok else '#7f1d1d'};"
            f"border-radius:9px; padding:2px 9px; font-size:10px; color:{GREEN if ok else RED};")

    def _lcu_update(self, data):
        self.seed_state(data.get("my_team", []), data.get("enemy_team", []),
                        data.get("my_role", "Unknown"), data.get("bans", []),
                        data.get("enemy_team_roles", []))

    def seed_state(self, my_team, enemy_team, my_role, bans=None, enemy_roles=None):
        for i, (icon, cb, rl) in enumerate(self.ally_rows):
            name = my_team[i] if i < len(my_team) else "..."
            cb.blockSignals(True)
            cb.setCurrentText(name if name in self.champ_names else "(empty)")
            cb.blockSignals(False)
        for i, (icon, cb, rc) in enumerate(self.enemy_rows):
            name = enemy_team[i] if i < len(enemy_team) else "..."
            cb.blockSignals(True)
            cb.setCurrentText(name if name in self.champ_names else "(empty)")
            cb.blockSignals(False)
            r = enemy_roles[i] if enemy_roles and i < len(enemy_roles) else None
            nr = normalize_role(r)
            rc.blockSignals(True)
            rc.setCurrentText(nr.value if nr else "Unknown")
            rc.blockSignals(False)
        nr = normalize_role(my_role)
        if nr:
            self.role_cb.blockSignals(True)
            self.role_cb.setCurrentText(nr.value)
            self.role_cb.blockSignals(False)
        if bans:
            self.bans_edit.blockSignals(True)
            self.bans_edit.setText(", ".join(b for b in bans if b not in ("Picking...", "Unknown")))
            self.bans_edit.blockSignals(False)
        self._debounce.start()

    # ---------------- recalc ----------------
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

    def recalc(self):
        if not self.ds:
            self.status_lbl.setText("Dataset yok — python -m engine.cli ingest")
            return
        # pick up newly published datasets without restarting the window
        try:
            latest_id = json.loads(
                (self.cfg.datasets_dir / "index.json").read_text(encoding="utf-8")).get("latest")
        except Exception:
            latest_id = None
        if latest_id and latest_id != self.ds.dataset_id:
            self.ds = DatasetStore(self.cfg.datasets_dir).load(latest_id)
            from engine.engines.decision import DecisionEngine
            self.eng = DecisionEngine(self.cfg, self.ds)
            self._refresh_chips()
        ally = self._ids([cb for _, cb, _ in self.ally_rows])
        enemy = self._ids([cb for _, cb, _ in self.enemy_rows])
        eroles = []
        for _, _, rc in self.enemy_rows:
            txt = rc.currentText()
            eroles.append(normalize_role(txt) if txt != "Unknown" else None)
        bans = []
        for part in self.bans_edit.text().split(","):
            cid = self.ds.resolve_id(part.strip())
            if cid is not None:
                bans.append(cid)
        role = Role(self.role_cb.currentText())
        team = self.side_cb.currentText()
        from engine.engines.draft import build_draft, future_steps, DraftError
        try:
            draft = build_draft(self.ds, role, ally, enemy, bans, team, enemy_roles=eroles)
            self.order_lbl.setText(f"pick: now +{len(future_steps(draft))} future | pool {len(draft.available_ids)}")
        except DraftError as e:
            self.status_lbl.setText(f"Draft: {e}")
            return
        prev = self._worker
        if prev is not None:
            try:
                if prev.isRunning():
                    prev.requestInterruption()
            except RuntimeError:
                pass
        # visible feedback: the user must SEE that a recalculation is running
        self.chips["mode"].setText("COMPUTING…")
        self.hero_score.setStyleSheet(f"color:{AMBER};")
        self.status_lbl.setText("yeniden hesaplanıyor…")
        w = PanelWorker(ally, enemy, eroles, bans, role, team, parent=self)
        self._worker = w
        w.numeric_ready.connect(self._render)
        w.llm_ready.connect(self._render_llm)
        w.failed.connect(lambda m: self.status_lbl.setText("HATA: " + m))
        w.finished.connect(lambda w=w: self._retire(w))
        w.start()

    def _retire(self, w):
        if self._worker is w:
            self._worker = None
        w.deleteLater()

    # ---------------- render ----------------
    def _set_icon(self, lbl: QLabel, cid: int, size: int):
        path = self.cfg.datasets_dir / "_icons" / f"{cid}.png"
        if path.exists():
            pm = QPixmap(str(path)).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
            lbl.setPixmap(pm)
        else:
            lbl.setText("?")

    def _request_icons(self, ids):
        for cid in ids:
            self._set_icon_for(cid)
        missing = [cid for cid in ids
                   if not (self.cfg.datasets_dir / "_icons" / f"{cid}.png").exists()]
        if missing:
            iw = IconWorker(missing, parent=self)
            iw.icon_ready.connect(lambda cid, path: self._set_icon_for(cid))
            iw.finished.connect(lambda iw=iw: iw.deleteLater())
            self._icon_workers.append(iw)
            iw.start()

    def _set_icon_for(self, cid):
        for lbl, size in self._icon_labels.get(cid, []):
            self._set_icon(lbl, cid, size)

    def _register_icon(self, cid, lbl, size):
        self._icon_labels.setdefault(cid, []).append((lbl, size))
        self._set_icon(lbl, cid, size)

    def _render(self, rec):
        cid = rec.get("recommended_champion_id")
        champ = self.ds.champions.get(cid, {})
        score = rec.get("ranking_score")
        delta = None if self._prev_score is None or score is None else score - self._prev_score
        self._prev_score = score
        self.hero_score.setStyleSheet(f"color:{GREEN};")
        self.hero_name.setText(champ.get("name", "—"))
        self.hero_tag.setText(f"{rec.get('recommended_role')}  ·  {', '.join(champ.get('tags', []))}")
        self.hero_score.setText(f"{score:+.3f}" if score is not None else "—")
        conf = rec.get("confidence") or 0
        self.conf_bar.setValue(int(conf * 100))
        best = rec.get("candidates", [{}])[0]
        terms = sorted(best.get("feature_contributions", []),
                       key=lambda c: -abs(c.get("logodds", 0)))[:3]
        self.hero_why.setText(" · ".join(f"{t['component']} {t['logodds']:+.3f}" for t in terms))
        self.chips["mode"].setText(rec.get("evaluation_mode", "HEURISTIC"))
        # alternatives
        for i, (ai, an, asc) in enumerate(self.alt_cards):
            alts = rec.get("alternatives", [])
            if i < len(alts):
                a = alts[i]
                acid = a["champion_id"]
                an.setText(self.ds.champions.get(acid, {}).get("name", "—"))
                asc.setText(f"{a.get('ranking_score'):+.3f}  (Δ {a.get('delta_vs_best'):+.3f})")
                self._register_icon(acid, ai, 40)
            else:
                an.setText("—")
                asc.setText("")
        # evidence bars
        contribs = best.get("feature_contributions", [])[:6]
        for i, (lb, bar) in enumerate(self.ev_bars):
            if i < len(contribs):
                c = contribs[i]
                lb.setText(c["component"])
                bar.set_value(c.get("logodds", 0))
            else:
                lb.setText("")
                bar.set_value(0.0)
        # risk chips
        while self.risk_row.count():
            item = self.risk_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        risk = rec.get("risk", {})
        for key, label in (("counterpick_exposure", "counter"),
                           ("role_uncertainty", "rol belirsizliği"),
                           ("data_uncertainty", "veri belirsizliği")):
            v = risk.get(key)
            chip = QLabel(f"{label}: {v if v is not None else '—'}")
            chip.setObjectName("RiskChip")
            self.risk_row.addWidget(chip)
        self.risk_row.addStretch()
        self.warn_lbl.setText("\n".join(rec.get("limitations", [])[:4]))
        # team icons + row role labels (user occupies the first empty ally slot)
        n_ally = len(self._ids([cb for _, cb, _ in self.ally_rows]))
        for i, (icon, cb, rl) in enumerate(self.ally_rows):
            name = cb.currentText()
            acid = self.ds.resolve_id(name) if name != "(empty)" else None
            if acid:
                self._register_icon(acid, icon, 38)
            rl.setText(self.role_cb.currentText() if i == n_ally else "")
        for i, (icon, cb, rc) in enumerate(self.enemy_rows):
            name = cb.currentText()
            ecid = self.ds.resolve_id(name) if name != "(empty)" else None
            if ecid:
                self._register_icon(ecid, icon, 38)
        self._register_icon(cid, self.hero_icon, 86)
        team_ids = self._ids([cb for _, cb, _ in self.ally_rows]) + \
            self._ids([cb for _, cb, _ in self.enemy_rows])
        self._request_icons([cid] + [a["champion_id"] for a in rec.get("alternatives", [])] + team_ids)
        # per-enemy impact: makes enemy swaps visible even when the top pick stays
        from engine.contracts.types import RelationType
        role = Role(self.role_cb.currentText())
        for i, (lb, bar) in enumerate(self.enemy_bars):
            icon, cb, rc = self.enemy_rows[i]
            name = cb.currentText()
            ecid = self.ds.resolve_id(name) if name != "(empty)" else None
            if ecid is None or self.eng is None or cid is None:
                lb.setText("—")
                bar.set_value(0.0)
                continue
            erole = normalize_role(rc.currentText()) if rc.currentText() != "Unknown" else None
            rel = RelationType.SAME_LANE if erole == role else RelationType.CROSS_TEAM
            d = self.eng.matchup.delta(cid, role, ecid, erole or role, rel)
            w = 1.0 if rel == RelationType.SAME_LANE else 0.25
            lb.setText(f"vs {name} · {erole.value if erole else '?'}")
            bar.set_value(w * d["logodds"] * d["confidence"], missing=(d["kind"] == "missing"))
        delta_txt = f" · Δ skor {delta:+.4f} (önceki draft)" if delta is not None else ""
        self.status_lbl.setText(
            f"dataset {self.ds.dataset_id} · patch {self.ds.manifest.get('patch')} · "
            f"{len(rec.get('candidates', []))} aday · {rec.get('status')}{delta_txt}")

    def _render_llm(self, out):
        if out.get("llm_status") == "ok":
            parts = [out.get("summary", ""), "", "KORİDOR: " + out.get("lane_plan", ""),
                     "", "TAKIM SAVAŞI: " + out.get("teamfight_plan", ""), "", "RİSKLER:"]
            parts += ["• " + r for r in out.get("risks", [])]
            parts += ["", "ALTERNATİFLER:"]
            parts += ["• " + r for r in out.get("alternatives_rationale", [])]
            parts += ["", "VERİ NOTLARI:"]
            parts += ["• " + r for r in out.get("data_caveats", [])]
            self.coach.setPlainText("\n".join(parts))
        else:
            self.coach.setPlainText(json.dumps(out, ensure_ascii=False, indent=2))

    def closeEvent(self, event):
        try:
            self.lcu.stop()
        except Exception:
            pass
        w = self._worker
        if w is not None:
            try:
                w.requestInterruption()
                w.wait(1500)
                if w.isRunning():
                    w.terminate()
                    w.wait(300)
            except RuntimeError:
                pass
        super().closeEvent(event)
