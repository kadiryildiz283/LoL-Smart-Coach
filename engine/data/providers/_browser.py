"""LoG access layer: real-browser challenge resolution + fast HTTP reuse.

Boundary (kutsal_amac.md §3 amendment): only NON-INTERACTIVE Cloudflare JS
challenges are awaited. If an interactive CAPTCHA/Turnstile persists, we raise
ChallengeBlocked and stop — no solving services, no clicking.

Flow: headed Chromium resolves challenge once -> cf_clearance cookies + UA are
persisted -> bulk fetching runs over curl_cffi with the same UA (verified
working 2026-11-18). Cookies are re-validated lazily; expired clearance
triggers one browser re-resolution.
"""
from __future__ import annotations

import glob
import json
import time
from pathlib import Path

from curl_cffi import requests as creq

from engine.config import LoGConfig


class ChallengeBlocked(RuntimeError):
    """Interactive CAPTCHA or persistent block — provider must stop cleanly."""


def _find_chromium() -> str:
    cached = sorted(glob.glob(str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux64/chrome")))
    if cached:
        return cached[-1]
    for p in ("/usr/bin/chromium", "/usr/bin/google-chrome-stable", "/usr/bin/chromium-browser"):
        if Path(p).exists():
            return p
    raise ChallengeBlocked("no chromium executable found for challenge resolution")


class LoGAccess:
    def __init__(self, cfg: LoGConfig, staging: Path):
        self.cfg = cfg
        self.staging = Path(staging)
        self.staging.mkdir(parents=True, exist_ok=True)
        # clearance cookies are site-wide: share across provider staging dirs
        shared = self.staging.parent / "_shared"
        shared.mkdir(parents=True, exist_ok=True)
        self.cookie_file = shared / "cf_session.json"
        self._session: creq.Session | None = None
        self._ua: str | None = None
        self.last_challenge_resolution: float | None = None

    # ---------- session management ----------
    def _build_session(self, cookies: dict, ua: str) -> creq.Session:
        s = creq.Session(impersonate=self.cfg.impersonate)
        s.headers.update({"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"})
        for k, v in cookies.items():
            s.cookies.set(k, v, domain=".leagueofgraphs.com")
        return s

    def _probe(self, session: creq.Session) -> bool:
        try:
            r = session.get(f"{self.cfg.base_url}/champions/tier-list/ahri/iron",
                            timeout=self.cfg.timeout_s)
            return r.status_code == 200 and len(r.content) > 50000 \
                and "Just a moment" not in r.text[:2000]
        except Exception:
            return False

    def _resolve_via_browser(self) -> tuple[dict, str]:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=_find_chromium(), headless=False,
                args=["--disable-blink-features=AutomationControlled"])
            try:
                ctx = browser.new_context(locale="en-US", viewport={"width": 1366, "height": 900})
                page = ctx.new_page()
                page.goto(self.cfg.base_url + "/", timeout=45000, wait_until="domcontentloaded")
                time.sleep(3)
                page.goto(f"{self.cfg.base_url}/champions/tier-list/ahri/iron",
                          timeout=45000, wait_until="domcontentloaded")
                resolved = False
                for _ in range(14):  # ~35s for non-interactive JS challenge
                    title = page.title()
                    if "Just a moment" not in title and "Attention" not in title:
                        resolved = True
                        break
                    time.sleep(2.5)
                html = page.content()
                # Resolved = real site content rendered. Leftover challenge SCRIPT
                # references in a resolved DOM are normal and NOT an interactive CAPTCHA.
                has_content = ("lolg-stat-tile" in html or "graphDD2" in html
                               or "lolg-table" in html or len(html) > 100000)
                if not resolved or not has_content:
                    raise ChallengeBlocked(
                        "interactive CAPTCHA/Turnstile persisted; stopping per spec boundary")
                cookies = {c["name"]: c["value"] for c in ctx.cookies()}
                ua = page.evaluate("navigator.userAgent")
                if "cf_clearance" not in cookies:
                    raise ChallengeBlocked("cf_clearance cookie not obtained")
                self.last_challenge_resolution = time.time()
                return cookies, ua
            finally:
                browser.close()

    def session(self) -> creq.Session:
        if self._session is not None and self._probe(self._session):
            return self._session
        if self.cookie_file.exists():
            try:
                saved = json.loads(self.cookie_file.read_text(encoding="utf-8"))
                s = self._build_session(saved["cookies"], saved["ua"])
                if self._probe(s):
                    self._session, self._ua = s, saved["ua"]
                    return s
            except Exception:
                pass
        cookies, ua = self._resolve_via_browser()
        self.cookie_file.write_text(json.dumps({"cookies": cookies, "ua": ua,
                                                "resolved_at": time.time()}), encoding="utf-8")
        self._session = self._build_session(cookies, ua)
        self._ua = ua
        return self._session

    # ---------- fetching ----------
    def get_html(self, url: str) -> str | None:
        """Polite GET with backoff. Returns HTML or None (404/empty).
        Raises ChallengeBlocked when access cannot be obtained."""
        for attempt in range(self.cfg.max_retries):
            try:
                s = self.session()
                r = s.get(url, timeout=self.cfg.timeout_s)
                if r.status_code == 200:
                    if "Just a moment" in r.text[:2000]:
                        self._session = None  # force re-resolution
                        continue
                    return r.text
                if r.status_code == 404:
                    return None
                if r.status_code == 429:
                    time.sleep(self.cfg.cooldown_429_s)
                    continue
                if r.status_code == 403:
                    self._session = None
                    time.sleep(self.cfg.cooldown_403_s)
                    continue
                time.sleep(3)
            except ChallengeBlocked:
                raise
            except Exception:
                time.sleep(3)
        return None
