"""League of Graphs provider — ENABLED under project-owner authorization.

Permission: user_granted_2026-11-18 (kutsal_amac.md §3 amendment).
Access: real-browser non-interactive challenge resolution, then fast HTTP with
cf_clearance (see _browser.py). Interactive CAPTCHA => clean stop, no solving.

Three phases, all resume-safe via content-addressed raw HTML cache:
  1. meta: overall + per-role WR/pick/ban/sample (role tabs discovered live)
  2. counters: raw WR + "vs avg" delta + Games + opponent role + patch
  3. vs brute force: every role-intersecting pair not covered by counters,
     raw matchup WR + gold diff @15 + sample; reverse perspective derived.

Parsing is fully isolated here; the pipeline only sees normalized records.
Missing values are null + missing_reason, never zero.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from engine.config import LoGConfig
from engine.contracts.records import (
    ChampionRoleStats, Matchup, Synergy, Provenance, Quality, utcnow,
)
from engine.contracts.types import QualityStatus, RelationType, Role, normalize_role
from engine.data.providers.base import (
    Provider, ProviderResult, ProviderDisabled, cache_get, cache_put,
)
from engine.data.providers._browser import LoGAccess, ChallengeBlocked

RANK_SCOPE_BY_SLUG = {
    "iron": "IRON_PLUS", "bronze": "BRONZE_PLUS", "silver": "SILVER_PLUS",
    "gold": "GOLD_PLUS", "platinum": "PLATINUM_PLUS", "emerald": "EMERALD_PLUS",
    "diamond": "DIAMOND_PLUS", "master": "MASTER_PLUS",
    "grandmaster": "GRANDMASTER_PLUS", "challenger": "CHALLENGER", "all": "ALL",
}
ROLE_SLUGS = {"top": Role.TOP, "jungle": Role.JUNGLE, "middle": Role.MIDDLE,
              "bottom": Role.BOTTOM, "support": Role.UTILITY}
URL_FIXES = {
    "nunu & willump": "nunu", "renata glasc": "renata", "dr. mundo": "drmundo",
    "bel'veth": "belveth", "kai'sa": "kaisa", "kha'zix": "khazix",
    "kog'maw": "kogmaw", "k'sante": "ksante", "leblanc": "leblanc",
    "lee sin": "leesin", "master yi": "masteryi", "miss fortune": "missfortune",
    "tahm kench": "tahmkench", "twisted fate": "twistedfate", "xin zhao": "xinzhao",
    "rek'sai": "reksai", "jarvan iv": "jarvaniv", "aurelion sol": "aurelionsol",
    "wukong": "monkeyking",
}


def log_slug(name: str) -> str:
    n = name.lower()
    if n in URL_FIXES:
        return URL_FIXES[n]
    return n.replace(".", "").replace("'", "").replace(" ", "").replace("&", "")


def _pct(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"(-?\d+(?:\.\d+)?)", text.replace(",", ""))
    return round(float(m.group(1)) / 100.0, 5) if m else None


def _count(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"([\d,]+)", text)
    return int(m.group(1).replace(",", "")) if m else None


def parse_tiles(html: str) -> list[tuple[str, str, str | None]]:
    return [(m.group(1), m.group(2), m.group(3)) for m in re.finditer(
        r'lolg-stat-tile__label">([^<]+)</div>\s*'
        r'<div class="lolg-stat-tile__value[^"]*">([^<]+)</div>'
        r'(?:\s*<div class="lolg-stat-tile__sub">([^<]*)</div>)?', html)]


def parse_patch(html: str) -> str | None:
    m = re.search(r"Patch[:\s]*(\d+\.\d+)", html)
    return m.group(1) if m else None


def parse_meta(html: str) -> dict:
    tiles = parse_tiles(html)
    out = {"win_rate": None, "pick_rate": None, "ban_rate": None, "sample_size": None}
    for label, value, sub in tiles:
        if label == "Winrate" and out["win_rate"] is None:
            out["win_rate"] = _pct(value)
        elif label == "Popularity":
            out["pick_rate"] = _pct(value)
            out["sample_size"] = _count(sub)
        elif label == "Ban Rate":
            out["ban_rate"] = _pct(value)
    return out


def parse_role_tabs(html: str, slug: str, rank: str) -> list[Role]:
    roles = []
    for rs in re.findall(rf'/champions/tier-list/{re.escape(slug)}/([a-z]+)/{re.escape(rank)}', html):
        r = ROLE_SLUGS.get(rs)
        if r and r not in roles:
            roles.append(r)
    return roles


def parse_counters(html: str) -> dict:
    """Returns {'patch':..., 'advantage': [rows], 'disadvantage': [rows], 'partners': [rows]}
    row = {name, role|None, win_rate, vs_avg_pp, games}"""
    out = {"patch": parse_patch(html), "advantage": [], "disadvantage": [], "partners": []}
    sections = [
        ("is best against", "advantage"),
        ("is countered by", "disadvantage"),
        ("Best partner", "partners"),
    ]
    positions = []
    for marker, key in sections:
        i = html.find(marker)
        if i >= 0:
            positions.append((i, key))
    positions.sort()
    for idx, (start, key) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(html)
        seg = html[start:end]
        for row in re.findall(r'<a class="lolg-table__row".*?</a>', seg, re.S):
            name_m = re.search(r'lolg-matchup__name">([^<]+)', row)
            if not name_m:
                continue
            role_m = re.search(r'lolg-matchup__role">([^<]+)', row)
            figs = re.findall(r'lolg-table__cell--figure[^>]*>\s*([^<]+?)\s*<', row)
            out[key].append({
                "name": name_m.group(1).strip(),
                "role": normalize_role(role_m.group(1)) if role_m else None,
                "win_rate": _pct(figs[0]) if len(figs) > 0 else None,
                "vs_avg_pp": float(figs[1].replace("+", "")) if len(figs) > 1 and re.search(r'-?\d', figs[1]) else None,
                "games": _count(figs[2]) if len(figs) > 2 else None,
            })
    return out


def parse_vs(html: str, enemy_name: str) -> dict:
    tiles = parse_tiles(html)
    out = {"observed_win_rate": None, "lane_gold_diff_15": None,
           "sample_size": None, "period_note": None}
    for label, value, sub in tiles:
        if label == "Winrate" and sub and sub.lower().startswith("vs "):
            out["observed_win_rate"] = _pct(value)
        elif label == "Gold diff @15":
            m = re.search(r"([+-]?\d+)", value.replace(",", ""))
            out["lane_gold_diff_15"] = float(m.group(1)) if m else None
        elif label == "Popularity" and sub:
            out["sample_size"] = _count(sub)
    if out["sample_size"] is None:
        m = re.search(r'id="matchesCountNumber">([\d,]+)<', html)
        out["sample_size"] = _count(m.group(1)) if m else None
    m = re.search(r'id="matchesCountTimeframe">([^<]+)<', html)
    out["period_note"] = m.group(1) if m else None
    return out


def parse_items(html: str) -> list[dict]:
    """Item rows are DIVs with raw fraction data-sort attributes + official item ids."""
    out = []
    markers = [("Starting Build", "starting"), ("Core Build", "core"),
               ("Boots", "boots"), ("Final Item Options", "final")]
    positions = sorted([(html.find(m), key) for m, key in markers if html.find(m) >= 0])
    for idx, (start, key) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(html)
        seg = html[start:end]
        for ch in re.split(r'class="lolg-table__row"', seg)[1:]:
            attrs = dict(re.findall(r'data-sort-(\w+)="([^"]+)"', ch[:300]))
            item_ids = [int(x) for x in re.findall(r'tooltip-var="item-(\d+)"', ch[:1500])]
            if not item_ids:
                continue
            out.append({
                "section": key, "items": item_ids,
                "popularity": float(attrs["popularity"]) if "popularity" in attrs else None,
                "win_rate": float(attrs["winrate"]) if "winrate" in attrs else None,
            })
    return out


def parse_runes(html: str) -> list[dict]:
    out = []
    markers = ["Best runes", "Runes #2", "Runes #3", "Runes #4", "Runes #5"]
    positions = sorted([(html.find(m), m) for m in markers if html.find(m) >= 0])
    for idx, (start, name) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(html)
        seg = html[start:end]
        pop = re.search(r'lolg-meter__label">Popularity</span>\s*<span[^>]*>([\d.]+)%', seg)
        wr = re.search(r'lolg-meter__label">Winrate</span>\s*<span[^>]*>([\d.]+)%', seg)
        perks = [int(x) for x in dict.fromkeys(re.findall(r'perk-(\d+)', seg))]
        out.append({
            "section": name, "perks": perks,
            "popularity": round(float(pop.group(1)) / 100, 5) if pop else None,
            "win_rate": round(float(wr.group(1)) / 100, 5) if wr else None,
        })
    return out


class LeagueOfGraphsProvider(Provider):
    name = "leagueofgraphs"

    def __init__(self, cfg: LoGConfig):
        self.cfg = cfg
        self.champions: list[dict] = []  # [{id, name, slug, roles:[Role]}] set by pipeline

    def set_champions(self, champions: list[dict]) -> None:
        self.champions = champions

    def _html(self, access: LoGAccess, staging: Path, url: str, res: ProviderResult,
              resume: bool) -> str | None:
        if resume:
            cached = cache_get(staging, url)
            if cached is not None:
                res.cached += 1
                return cached["body"]
        html = access.get_html(url)
        res.fetched += 1
        if html is not None:
            cache_put(staging, url, html)
        time.sleep(self.cfg.request_delay_s)
        return html

    def collect(self, staging: Path, resume: bool = True) -> ProviderResult:
        if not self.cfg.enabled:
            raise ProviderDisabled("LeagueOfGraphsProvider disabled by config")
        res = ProviderResult(provider=self.name)
        access = LoGAccess(self.cfg, staging)
        rank = self.cfg.rank_slug
        rank_scope = RANK_SCOPE_BY_SLUG.get(rank, "ALL")
        base = self.cfg.base_url
        patch = None
        by_name = {c["name"].lower(): c for c in self.champions}
        primary_role: dict[int, Role] = {}
        plausible: dict[int, list[Role]] = {}
        covered_pairs: set[tuple[int, int]] = set()

        def prov(url):
            return Provenance(provider=self.name, source_url=url, collected_at=utcnow(),
                              permission=self.cfg.permission,
                              period_end=utcnow())

        # ---------- Phase 1: meta ----------
        for c in self.champions:
            slug = log_slug(c["name"])
            url = f"{base}/champions/tier-list/{slug}/{rank}"
            html = self._html(access, staging, url, res, resume)
            if not html:
                res.warnings.append(f"meta 404/empty: {c['name']} ({slug})")
                continue
            patch = parse_patch(html) or patch
            meta = parse_meta(html)
            fallback_roles = [Role(r) if isinstance(r, str) else r for r in c.get("roles", [])]
            roles = parse_role_tabs(html, slug, rank) or fallback_roles
            plausible[c["id"]] = roles
            if roles:
                primary_role[c["id"]] = roles[0]
            # overall WR is NOT role-specific (spec §3.2): it goes to champions.json
            res.extra.setdefault("overall_wr", {})[str(c["id"])] = {
                "win_rate": meta["win_rate"], "sample_size": meta["sample_size"],
                "pick_rate": meta["pick_rate"], "ban_rate": meta["ban_rate"],
                "patch": patch, "source_url": url, "rank_scope": rank_scope}

            for role in roles:
                rslug = next(k for k, v in ROLE_SLUGS.items() if v == role)
                rurl = f"{base}/champions/tier-list/{slug}/{rslug}/{rank}"
                rhtml = self._html(access, staging, rurl, res, resume)
                if not rhtml:
                    continue
                rmeta = parse_meta(rhtml)
                rpatch = parse_patch(rhtml) or patch
                rq = Quality(status=QualityStatus.OBSERVED if rmeta["sample_size"] else QualityStatus.MISSING,
                             confidence=0.7 if rmeta["sample_size"] else None,
                             missing_reason=None if rmeta["win_rate"] is not None else "role_page_parse_failed")
                rrs = ChampionRoleStats(
                    champion_id=c["id"], role=role, patch=rpatch or "unknown",
                    rank_scope=rank_scope, region=self.cfg.region,
                    win_rate=rmeta["win_rate"], pick_rate=rmeta["pick_rate"],
                    ban_rate=rmeta["ban_rate"], sample_size=rmeta["sample_size"],
                    provenance=prov(rurl), quality=rq,
                ).to_dict()
                rrs["metric_scope"] = "ROLE_SPECIFIC"
                res.add("champion_role_stats", rrs)
            # refine primary role = highest role pick rate
            best, best_pick = None, -1.0
            for rec in res.records.get("champion_role_stats", []):
                if rec["champion_id"] == c["id"] and rec.get("metric_scope") == "ROLE_SPECIFIC":
                    pr = rec["stats"]["pick_rate"] or 0
                    if pr > best_pick:
                        best, best_pick = rec["role"], pr
            if best:
                primary_role[c["id"]] = Role(best)
            print(f"[LoG meta] {c['name']}: WR={meta['win_rate']} roles={[r.value for r in roles]}", flush=True)

        res.patch = patch
        # ---------- Phase 2: counters ----------
        for c in self.champions:
            slug = log_slug(c["name"])
            cid = c["id"]
            crole = primary_role.get(cid, (plausible.get(cid) or [Role.MIDDLE])[0])
            url = f"{base}/champions/counters/{slug}/{rank}"
            html = self._html(access, staging, url, res, resume)
            if not html:
                continue
            parsed = parse_counters(html)
            cpatch = parsed["patch"] or patch or "unknown"
            for key, direction, relation in (("advantage", "ADVANTAGE", RelationType.SAME_LANE),
                                             ("disadvantage", "DISADVANTAGE", RelationType.SAME_LANE)):
                for row in parsed[key]:
                    opp = by_name.get(row["name"].lower())
                    if not opp:
                        res.warnings.append(f"counters: unknown champion {row['name']}")
                        continue
                    orole = row["role"] or primary_role.get(opp["id"], Role.MIDDLE)
                    m = Matchup(
                        champion_id=cid, champion_role=crole,
                        opponent_id=opp["id"], opponent_role=orole,
                        relation_type=relation, patch=cpatch,
                        rank_scope=rank_scope, region=self.cfg.region,
                        sample_size=row["games"], observed_win_rate=row["win_rate"],
                        provenance=prov(url),
                        quality=Quality(status=QualityStatus.OBSERVED if row["games"] else QualityStatus.MISSING,
                                        confidence=0.7 if row["games"] else None,
                                        missing_reason=None if row["win_rate"] is not None else "row_parse_failed"),
                    ).to_dict()
                    m["legacy_direction"] = direction
                    m["source_vs_avg_pp"] = row["vs_avg_pp"]
                    res.add("matchups", m)
                    covered_pairs.add((cid, opp["id"]))
            for row in parsed["partners"]:
                ally = by_name.get(row["name"].lower())
                if not ally:
                    continue
                s = Synergy(
                    champion_id=cid, champion_role=crole, ally_id=ally["id"],
                    ally_role=row["role"], patch=cpatch,
                    rank_scope=rank_scope, region=self.cfg.region,
                    sample_size=row["games"], observed_win_rate=row["win_rate"],
                    provenance=prov(url),
                    quality=Quality(status=QualityStatus.OBSERVED if row["games"] else QualityStatus.MISSING,
                                    confidence=0.7 if row["games"] else None,
                                    missing_reason=None if row["win_rate"] is not None else "row_parse_failed"),
                ).to_dict()
                s["source_vs_avg_pp"] = row["vs_avg_pp"]
                res.add("synergies", s)
            print(f"[LoG counters] {c['name']}: +{len(parsed['advantage'])} -{len(parsed['disadvantage'])} p{len(parsed['partners'])}", flush=True)

        # ---------- Phase 3: vs brute force ----------
        names = sorted(self.champions, key=lambda c: c["name"].lower())
        vs_done = 0
        for i, a in enumerate(names):
            aslug = log_slug(a["name"])
            aroles = set(plausible.get(a["id"], []))
            arole = primary_role.get(a["id"], Role.MIDDLE)
            per_champ = 0
            for b in names[i + 1:]:
                if (a["id"], b["id"]) in covered_pairs or (b["id"], a["id"]) in covered_pairs:
                    continue
                broles = set(plausible.get(b["id"], []))
                if not (aroles & broles):
                    continue
                if self.cfg.max_vs_pages_per_champion and per_champ >= self.cfg.max_vs_pages_per_champion:
                    break
                bslug = log_slug(b["name"])
                brole = primary_role.get(b["id"], Role.MIDDLE)
                relation = RelationType.SAME_LANE if arole == brole else RelationType.CROSS_TEAM
                url = f"{base}/champions/tier-list/{aslug}/vs-{bslug}/{rank}"
                html = self._html(access, staging, url, res, resume)
                per_champ += 1
                vs_done += 1
                if not html:
                    continue
                v = parse_vs(html, b["name"])
                vpatch = parse_patch(html) or patch or "unknown"
                if v["observed_win_rate"] is None:
                    res.warnings.append(f"vs parse failed: {a['name']} vs {b['name']}")
                    continue
                for (cid, crole, oid, orole, wr, gold, derived) in (
                    (a["id"], arole, b["id"], brole, v["observed_win_rate"], v["lane_gold_diff_15"], False),
                    (b["id"], brole, a["id"], arole,
                     round(1.0 - v["observed_win_rate"], 5),
                     -v["lane_gold_diff_15"] if v["lane_gold_diff_15"] is not None else None, True),
                ):
                    m = Matchup(
                        champion_id=cid, champion_role=crole, opponent_id=oid,
                        opponent_role=orole, relation_type=relation, patch=vpatch,
                        rank_scope=rank_scope, region=self.cfg.region,
                        sample_size=v["sample_size"], observed_win_rate=wr,
                        lane_gold_diff_15=gold, provenance=prov(url),
                        quality=Quality(
                            status=QualityStatus.DERIVED if derived else QualityStatus.OBSERVED,
                            confidence=0.6 if v["sample_size"] else 0.3,
                            missing_reason=None if v["sample_size"] else "sample_not_exposed"),
                    ).to_dict()
                    m["period_note"] = v["period_note"]
                    m["roles_assumed_primary"] = True
                    res.add("matchups", m)
                covered_pairs.add((a["id"], b["id"]))
            if vs_done and vs_done % 50 == 0:
                print(f"[LoG vs] ilerleme: {vs_done} sayfa", flush=True)

        # ---------- Phase 4: builds (items + runes) ----------
        from engine.contracts.records import Build
        for c in self.champions:
            slug = log_slug(c["name"])
            cid = c["id"]
            crole = primary_role.get(cid, (plausible.get(cid) or [Role.MIDDLE])[0])
            iurl = f"{base}/champions/items/{slug}/{rank}"
            ih = self._html(access, staging, iurl, res, resume)
            if ih:
                ipatch = parse_patch(ih) or patch or "unknown"
                for row in parse_items(ih):
                    b = Build(
                        champion_id=cid, role=crole, patch=ipatch, items=row["items"],
                        win_rate=row["win_rate"], popularity=row["popularity"],
                        section=row["section"], sample_size=None,
                        provenance=prov(iurl),
                        quality=Quality(
                            status=QualityStatus.OBSERVED if row["win_rate"] is not None
                            else QualityStatus.MISSING,
                            confidence=0.5 if row["win_rate"] is not None else None,
                            missing_reason="sample_not_exposed_by_source"),
                    ).to_dict()
                    res.add("builds", b)
            rurl = f"{base}/champions/runes/{slug}/{rank}"
            rh = self._html(access, staging, rurl, res, resume)
            if rh:
                rpatch = parse_patch(rh) or patch or "unknown"
                for row in parse_runes(rh):
                    b = Build(
                        champion_id=cid, role=crole, patch=rpatch,
                        runes={"perks": row["perks"]},
                        win_rate=row["win_rate"], popularity=row["popularity"],
                        section="runes:" + row["section"], sample_size=None,
                        provenance=prov(rurl),
                        quality=Quality(
                            status=QualityStatus.OBSERVED if row["win_rate"] is not None
                            else QualityStatus.MISSING,
                            confidence=0.5 if row["win_rate"] is not None else None,
                            missing_reason="sample_not_exposed_by_source"),
                    ).to_dict()
                    res.add("builds", b)
            # §3.1 "varsa" fields: endpoints not mapped yet -> explicit nulls, never invented
            res.extra.setdefault("champion_extras", {})[str(cid)] = {
                "win_rate_by_duration": None,
                "win_rate_by_duration_missing_reason": "duration_filter_endpoint_not_mapped",
                "side_win_rates": None,
                "side_win_rates_missing_reason": "side_split_not_exposed_on_parsed_pages",
                "win_rate_by_experience": None,
                "win_rate_by_experience_missing_reason": "progressions_endpoint_not_mapped",
            }
            print(f"[LoG builds] {c['name']}", flush=True)

        res.coverage = {
            "meta_champions": len({r["champion_id"] for r in res.records.get("champion_role_stats", [])}),
            "matchups": len(res.records.get("matchups", [])),
            "synergies": len(res.records.get("synergies", [])),
            "builds": len(res.records.get("builds", [])),
            "vs_pages": vs_done, "patch": patch,
        }
        res.status = "ok" if not res.errors else "partial"
        return res
