"""Draft Intelligence Engine CLI.

  python -m engine.cli ingest --providers dd,legacy,log,riot
  python -m engine.cli recommend --role MIDDLE --ally Ahri,"Lee Sin" --enemy Zed --json
  python -m engine.cli datasets list
  python -m engine.cli rules seed|discover|list
  python -m engine.cli benchmark --n 20
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.config import Config, DEFAULT_CONFIG
from engine.data.store import DatasetStore
from engine.data.pipeline import IngestionPipeline
from engine.data.providers import (
    DataDragonProvider, LegacyProvider, LeagueOfGraphsProvider, RiotApiProvider,
)


def _store(cfg: Config) -> DatasetStore:
    return DatasetStore(cfg.datasets_dir)


def cmd_ingest(args, cfg: Config) -> int:
    if args.rank:
        cfg.log.rank_slug = args.rank
        cfg.engine.rank_scope = {"iron": "IRON_PLUS", "emerald": "EMERALD_PLUS",
                                 "diamond": "DIAMOND_PLUS", "master": "MASTER_PLUS",
                                 "all": "ALL"}.get(args.rank, args.rank.upper())
    if args.max_vs is not None:
        cfg.log.max_vs_pages_per_champion = args.max_vs
    if args.patch:
        cfg.ddragon.patch = args.patch
    selected = set(args.providers.split(","))
    providers = []
    if "dd" in selected:
        providers.append(DataDragonProvider(cfg.ddragon))
    if "legacy" in selected:
        providers.append(LegacyProvider(cfg.legacy_data_dir))
    if "log" in selected:
        providers.append(LeagueOfGraphsProvider(cfg.log))
    if "riot" in selected:
        providers.append(RiotApiProvider(cfg.riot))
    pipeline = IngestionPipeline(cfg, _store(cfg), providers)
    report = pipeline.run(resume=not args.no_resume)
    print(json.dumps({k: report[k] for k in
                      ("run_id", "coverage", "errors", "carried_forward",
                       "published_dataset_id") if k in report}, indent=2, ensure_ascii=False))
    for p in report["providers"]:
        print(f"  {p['provider']}: {p['status']} fetched={p['fetched']} cached={p['cached']} "
              f"records={p['records']}")
        for e in p["errors"][:3]:
            print(f"    ! {e}")
    return 0 if report.get("published_dataset_id") else 1


def cmd_datasets(args, cfg: Config) -> int:
    store = _store(cfg)
    if args.action == "list":
        idx = store._read_index()
        print("latest:", idx.get("latest"))
        for d in idx.get("history", []):
            print(" ", d)
    elif args.action == "rollback":
        store.rollback(args.dataset_id)
        print("rolled back to", args.dataset_id)
    return 0


def cmd_recommend(args, cfg: Config) -> int:
    from engine.contracts.types import normalize_role, Role
    from engine.engines.decision import DecisionEngine
    from engine.engines.draft import build_draft_from_args
    store = _store(cfg)
    ds = store.latest()
    if ds is None:
        print("no dataset published yet; run: python -m engine.cli ingest", file=sys.stderr)
        return 1
    role = normalize_role(args.role) or Role.MIDDLE
    draft = build_draft_from_args(ds, role, args.ally, args.enemy, args.bans,
                                  args.user_team, args.side_known)
    engine = DecisionEngine(cfg, ds)
    rec = engine.recommend(draft, mc_samples=args.samples, seed=args.seed)
    if args.llm:
        from engine.llm.coach import explain_recommendation
        rec.llm_explanation = explain_recommendation(cfg, ds, rec)
    out = rec.to_dict()
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        champ = ds.champions.get(rec.recommended_champion_id, {})
        print(f"Öneri: {champ.get('name', '?')} ({rec.recommended_role}) "
              f"| mod: {rec.evaluation_mode.value} | ranking_score: {rec.ranking_score}")
        print(f"güven: {rec.confidence} | durum: {rec.status}")
        for alt in rec.alternatives[:2]:
            ac = ds.champions.get(alt["champion_id"], {})
            print(f"  alternatif: {ac.get('name', '?')} score={alt.get('ranking_score')}")
        for ex in rec.explanations:
            print(" •", ex)
        for lim in rec.limitations:
            print(" ⚠", lim)
        if rec.llm_explanation:
            print("\nQwen yorumu:", json.dumps(rec.llm_explanation, ensure_ascii=False, indent=2))
    return 0


def cmd_rules(args, cfg: Config) -> int:
    from engine.knowledge.rules.registry import RuleRegistry
    from engine.knowledge.rules.seed import seed_rules
    store = _store(cfg)
    ds = store.latest()
    registry = RuleRegistry(cfg.game_rules_dir)
    if args.action == "seed":
        if ds is None:
            print("no dataset", file=sys.stderr)
            return 1
        added = seed_rules(registry, ds)
        print(f"seed: {added} kural eklendi/güncellendi")
    elif args.action == "discover":
        from engine.knowledge.rules.discovery import discover_rules
        if ds is None:
            print("no dataset", file=sys.stderr)
            return 1
        pairs = None
        if args.changed:
            # §22.10: only re-examine pairs whose evidence changed in the last publish
            pairs = [tuple(p) for p in ds.report.get("changed_segments", {}).get("matchup_pairs", [])]
            if not pairs:
                print("no changed matchup pairs in latest ingestion report")
                return 0
        report = discover_rules(cfg, ds, registry, limit=args.limit, pairs=pairs)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.action == "list":
        for r in registry.all():
            print(f"{r['rule_id']} [{r['rule_type']}/{r['status']}] {r['title']}")
    elif args.action == "validate":
        from engine.knowledge.rules.validators import validate_all
        report = validate_all(registry, ds)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_benchmark(args, cfg: Config) -> int:
    from engine.evaluation.benchmarks import run_benchmark
    store = _store(cfg)
    ds = store.latest()
    if ds is None:
        print("no dataset", file=sys.stderr)
        return 1
    report = run_benchmark(cfg, ds, n=args.n, samples=args.samples)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cmd_evaluate(args, cfg: Config) -> int:
    from engine.evaluation.backtest import run_evaluation
    store = _store(cfg)
    ds = store.latest()
    if ds is None:
        print("no dataset", file=sys.stderr)
        return 1
    report = run_evaluation(cfg, ds)
    if args.baselines:
        from engine.evaluation.baselines import run_baselines
        report["baselines"] = run_baselines(cfg, ds)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cmd_train(args, cfg: Config) -> int:
    """Train the calibrated win model. Real training needs match-level data
    (Riot Match-v5 -> datasets/matches.jsonl). --synthetic runs a labeled
    fixture to verify the training/gate code paths (never production)."""
    import numpy as np
    from engine.model import (train_logistic, predict_proba, time_split,
                              calibration_gate, draft_features, save_model)
    from engine.engines.decision import DecisionEngine
    from engine.stats import logit, sigmoid
    store = _store(cfg)
    ds = store.latest()
    if ds is None:
        print("no dataset", file=sys.stderr)
        return 1
    matches_path = cfg.datasets_dir / "matches.jsonl"
    if args.synthetic:
        import random
        from engine.contracts.types import ALL_ROLES
        rng = random.Random(3)
        ids = [cid for cid, c in ds.champions.items() if c.get("overall_win_rate")]
        matches = []
        for i in range(300):
            pool = rng.sample(ids, 10)
            blue = [(c, ALL_ROLES[j]) for j, c in enumerate(pool[:5])]
            red = [(c, ALL_ROLES[j]) for j, c in enumerate(pool[5:])]
            lo = sum(logit(ds.champions[c]["overall_win_rate"]) for c, _ in blue) - \
                sum(logit(ds.champions[c]["overall_win_rate"]) for c, _ in red)
            matches.append({"match_id": f"SYN-{i}", "patch": f"16.{10 + i // 100}",
                            "timestamp": f"2026-{1 + i // 100:02d}-01",
                            "teams": {"BLUE": blue, "RED": red},
                            "win_blue": int(rng.random() < sigmoid(lo)),
                            "quality": "synthetic"})
        print("UYARI: synthetic fixture — üretim kalibrasyonu DEĞİL")
    elif matches_path.exists():
        matches = [json.loads(l) for l in matches_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        print(json.dumps({"status": "external_dependency",
                          "need": "RIOT_API_KEY -> match-v5 -> datasets/matches.jsonl",
                          "hint": "python -m engine.cli train --synthetic (code-path verification only)"}))
        return 1
    eng = DecisionEngine(cfg, ds)
    train, test = time_split(matches)

    def xy(ms):
        X, y = [], []
        for m in ms:
            X.append(draft_features(eng, m["teams"]["BLUE"], m["teams"]["RED"]))
            y.append(m["win_blue"])
        return np.array(X), np.array(y)

    Xtr, ytr = xy(train)
    Xte, yte = xy(test)
    model = train_logistic(Xtr, ytr)
    base = predict_proba(train_logistic(Xtr[:, [0]], ytr), Xte[:, [0]])
    gate = calibration_gate(model, Xte, yte, base)
    print(json.dumps(gate, indent=2))
    if gate["calibration_gate_passed"] and not args.synthetic:
        save_model(cfg.datasets_dir / "calibrated_model.json", model, gate, ds.dataset_id)
        print("model saved; decision engine switches to CALIBRATED on next run")
    elif gate["calibration_gate_passed"]:
        print("synthetic gate passed (code path OK); model NOT saved for production")
    else:
        print("gate FAILED — model not saved; engine stays HEURISTIC")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="engine.cli", description="Draft Intelligence Engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest")
    p.add_argument("--providers", default="dd,legacy,log,riot")
    p.add_argument("--rank", default=None)
    p.add_argument("--patch", default=None)
    p.add_argument("--max-vs", type=int, default=None)
    p.add_argument("--no-resume", action="store_true")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("datasets")
    p.add_argument("action", choices=["list", "rollback"])
    p.add_argument("dataset_id", nargs="?", default=None)
    p.set_defaults(fn=cmd_datasets)

    p = sub.add_parser("recommend")
    p.add_argument("--role", default="MIDDLE")
    p.add_argument("--ally", default="")
    p.add_argument("--enemy", default="")
    p.add_argument("--bans", default="")
    p.add_argument("--user-team", default="BLUE", choices=["BLUE", "RED"])
    p.add_argument("--side-known", action="store_true",
                   help="treat listed enemy roles as known (ordered TOP..UTILITY)")
    p.add_argument("--samples", type=int, default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--llm", action="store_true")
    p.set_defaults(fn=cmd_recommend)

    p = sub.add_parser("rules")
    p.add_argument("action", choices=["seed", "discover", "list", "validate"])
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--changed", action="store_true",
                   help="incremental: only pairs changed in the latest dataset (§22.10)")
    p.set_defaults(fn=cmd_rules)

    p = sub.add_parser("benchmark")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--samples", type=int, default=128)
    p.set_defaults(fn=cmd_benchmark)

    p = sub.add_parser("evaluate")
    p.add_argument("--baselines", action="store_true")
    p.set_defaults(fn=cmd_evaluate)

    p = sub.add_parser("train")
    p.add_argument("--synthetic", action="store_true")
    p.set_defaults(fn=cmd_train)

    args = parser.parse_args(argv)
    cfg = DEFAULT_CONFIG
    return args.fn(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
