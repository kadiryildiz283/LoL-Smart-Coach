"""Panel worker lifecycle regressions (offscreen).

Reproduces the user-reported crash: change champion after a previous worker
finished and was retired (deleteLater) -> recalc touched a deleted QThread.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture()
def fast_llm(monkeypatch):
    from engine.llm import coach
    monkeypatch.setattr(coach, "explain_recommendation",
                        lambda cfg, ds, rec: {"llm_status": "test_stub"})


def _drain(app, ms=400):
    """Let finished signals + deleteLater run."""
    loop = QTimer()
    loop.setSingleShot(True)
    loop.timeout.connect(app.quit)
    loop.start(ms)
    app.exec()


def test_recalc_after_retired_worker(qapp, fast_llm, mini_ds, mini_cfg, monkeypatch):
    from core import draft_panel
    monkeypatch.setattr(draft_panel, "DEFAULT_CONFIG", mini_cfg)
    p = draft_panel.DraftPanel()
    p.recalc()
    assert p._worker is not None
    p._worker.wait(5000)
    _drain(qapp)          # finished -> _retire -> deleteLater executes
    # the user action that crashed: change a champion and recalc again
    p.ally_combos[0].setCurrentText("Malphite")
    p.recalc()            # must not raise RuntimeError on deleted QThread
    p._worker.wait(5000)
    _drain(qapp)
    p.recalc()            # third cycle after another retire
    p._worker.wait(5000)
    _drain(qapp)
    p.close()
    _drain(qapp, 100)


def test_supersede_while_running(qapp, fast_llm, mini_ds, mini_cfg, monkeypatch):
    from core import draft_panel
    monkeypatch.setattr(draft_panel, "DEFAULT_CONFIG", mini_cfg)
    p = draft_panel.DraftPanel()
    p.recalc()
    p.recalc()            # supersede before first finishes
    p._worker.wait(5000)
    _drain(qapp)
    p.close()
    _drain(qapp, 100)
