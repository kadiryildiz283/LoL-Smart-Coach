# Draft Intelligence Engine — Mimari

Ana hedef dokümanı: `kutsal_amac.md` (şartname). Bu dosya kodun haritasıdır.

## Katmanlar

```
engine/
├── contracts/          # Tipli, versiyonlanmış veri sözleşmeleri + JSON Schema kapısı
│   ├── types.py        # Role, RelationType, QualityStatus, EvalMode, RuleStatus...
│   ├── records.py      # Champion, ChampionRoleStats, Matchup, Synergy, DraftState,
│   │                   # Recommendation, CandidateEvaluation, Rule...
│   ├── evidence.py     # Canonical Evidence Schema (§23.2): birim, bağlam, belirsizlik
│   └── schema.py       # jsonschema doğrulama; publish/LLM/kural kapıları
├── stats.py            # Ortak matematik: logit/sigmoid, Wilson, shrinkage, CVaR, ECE
├── data/
│   ├── store.py        # Versiyonlu dataset store: atomik publish, rollback, immutable
│   ├── pipeline.py     # Acquisition→Staging→Parse→Normalize→VALIDATE→DEDUP→Quality→Publish
│   └── providers/
│       ├── data_dragon.py    # Resmî Riot statik veri (anahtarsız). Kimlik/menzil/yetenek.
│       ├── leagueofgraphs.py # İZİNLİ (user_granted_2026-11-18). 3 faz: meta→counters→vs
│       ├── _browser.py       # Cloudflare: gerçek tarayıcı, sadece non-interaktif challenge
│       ├── riot_api.py       # Match-v5 türetimi; RIOT_API_KEY yoksa missing_credentials
│       └── legacy.py         # Eski repo JSON migrasyonu; kusurlar sözleşme düzeyinde düzeltilir
├── knowledge/
│   ├── mechanics.py    # Menzil (verified), hasar (curated), CC/mobility (keyword heuristic)
│   └── rules/          # Oyun Kanunları Bilgi Tabanı (§22)
│       ├── registry.py     # Semantik dedup, versiyon, lifecycle, conflict kayıtları
│       ├── validators.py   # Mekanik doğrulama (game data), istatistiksel, ConflictResolver
│       ├── seed.py         # Doğrulanmış menzil gerçekleri + stratejik hipotez aileleri
│       └── discovery.py    # LLM öneri hattı: evidence→proposal→schema→verify→registry
├── engines/
│   ├── meta.py         # Rol bazlı güç, shrinkage, açık fallback (§7)
│   ├── matchup.py      # Gözlenen vs beklenen (main effects), adjusted delta (§8)
│   ├── synergy.py      # Çiftli sinerji: beklenen üstü sapma (§10)
│   ├── composition.py  # Bütüncül takım işlevi, AZALAN MARJİNAL KATKI (§10)
│   ├── threat.py       # Rakip takım tehdidi vs aday savunması (§11)
│   ├── role_inference.py # JOINT rol atama dağılımı (5! enumerasyon) (§9)
│   ├── draft.py        # DraftState, pick/ban sırası, geçerlilik (§12.1)
│   ├── future.py       # Monte Carlo gelecek draft, koşullu seçim modeli (§12, §23.8)
│   └── decision.py     # Kanıt birleştirme, HEURISTIC/PROVISIONAL/CALIBRATED (§13, §23)
├── llm/
│   ├── client.py       # Keşif (Ollama/OpenAI), birebir model doğrulama, timeout/retry
│   └── coach.py        # Türkçe açıklama; şema kapısı; offline şablon fallback (§14)
├── evaluation/
│   ├── benchmarks.py   # p95 gecikme ölçümü (§16)
│   ├── backtest.py     # Kalibrasyon protokolü + legacy-vs-observed doğrulama (§17)
│   ├── baselines.py    # Aşamalı baseline karşılaştırması (meta→+matchup→+synergy→full) (§17)
│   └── ablation.py     # Bileşen katkısı ölçümü (§22.8, §23.5)
├── model.py            # L2 logistic trainer, time-split, calibration gate (§23.3)
├── logging.py          # Yapılandırılmış JSONL log + hata sınıflandırma (§19)
└── cli.py              # ingest | recommend | datasets | rules | benchmark | evaluate | train
```

UI: `core/draft_panel.py` — §16 profesyonel panel (editable slot/ban/rol, patch/rank
bilgisi, rol göstergeleri, pick sırası, debounce otomatik yeniden hesap, sayısal önce
+ async Qwen). `core/lcu_connector.py` banları ve tüm oyuncu `assignedPosition`
bilgisini yakalar; panel açıkken her champ-select değişiminde canlı güncellenir.

Audit: `engine/data/audit.py` — her öneri `draft_snapshot.json` + `recommendation.json`
(+ JSONL tarihçe) olarak persist edilir; sıralama sonradan yeniden üretilebilir (§4).

Tip gate: `mypy.ini` — veri çekirdeği (contracts, stats, model, audit, logging,
mechanics) temiz; engines/UI kademeli anotasyonlu.

## Matematiksel sözleşme (§23)

- Tüm oranlar **fraction** (0.508), tüm katkılar **log-odds**. Birimler tipli (`Evidence.unit`).
- `expected_matchup_wr = sigmoid(logit(wr_A) - logit(wr_B))` — main-effect baseline.
- Matchup katkısı = `logit(observed) - logit(expected)` → main effect ile **double-counting yok**.
- Düşük örneklem → empirical-Bayes shrinkage (pseudo-count 30) + Wilson aralığı.
- Veri yoksa `null + missing_reason`; asla 0 doldurma; fallback açıkça işaretli.
- `predicted_win_probability` **yalnızca CALIBRATED** modda (maç-seviyesi veri + backtest kapısı).
  Şu an HEURISTIC: `ranking_score` log-odds ölçeğinde, kalibre olasılık DEĞİL.
- Gelecek draft: `Q(candidate) = Σ P(future, roles | draft, candidate) × P(win | completed)`,
  Monte Carlo (seed'li, bütçeli, cache'li), CVaR downside, MC stderr ayrı raporlanır.

## Kural motorunun karara etkisi (§22.8)

- Yalnızca `verified/active` kurallar otomatik sıralamayı etkiler.
- Etki **yalnızca gözlemsel matchup verisi YOKSA** devreye girer (double-counting guard).
- Doğrulanmamış LLM önerileri inceleme kuyruğunda kalır; asla otomatik aktif olmaz.
- Mekanik kural (koridor baskısı) ile amprik gözlem (maç WR) **farklı hedef değişkenlerdir**;
  çelişki değil, birlikte var olurlar (ConflictResolver `cross_target_coexistence`).

## Çalıştırma

```bash
python -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

.venv/bin/python -m engine.cli ingest --providers dd,legacy,log,riot   # veri hattı (resume'lu)
.venv/bin/python -m engine.cli recommend --role MIDDLE --ally "Malphite,Amumu" --enemy "Zed,Caitlyn" --json
.venv/bin/python -m engine.cli recommend ... --llm                     # Qwen açıklamalı
.venv/bin/python -m engine.cli rules seed|validate|discover|list
.venv/bin/python -m engine.cli benchmark --n 30 --samples 128
.venv/bin/python -m engine.cli evaluate --baselines
.venv/bin/python -m engine.cli train --synthetic    # kod yolu doğrulama (üretim DEĞİL)
.venv/bin/python -m engine.cli train                # gerçek: RIOT_API_KEY + matches.jsonl
.venv/bin/python -m engine.cli rules discover --changed   # §22.10 incremental
.venv/bin/python -m engine.cli datasets list|rollback <id>
.venv/bin/python -m pytest tests/ -m "not integration"                 # 52 test
.venv/bin/python -m pytest tests/ -m integration                       # canlı Qwen
.venv/bin/mypy engine/contracts engine/stats.py engine/model.py engine/data/audit.py engine/logging.py engine/knowledge/mechanics.py
python main.py                                                         # PyQt6 UI + Engine Coach panel
```

## Dış bağımlılıklar (açıkça işaretli)

| Bağımlılık | Durum | Etki |
|---|---|---|
| `RIOT_API_KEY` | YOK | Maç-seviyesi kalibrasyon verisi üretilemez; CALIBRATED moda geçilemez |
| LoG yazılı izin | Kullanıcı yetkilendirmesi (2026-11-18) | Site ToS riski kullanıcıda; nazik rate, CAPTCHA kırma yok |
| Yerel Qwen `172.16.10.142` | ERİŞİLEBİLİR (vLLM :8000, Ollama :11434) | Açıklama + kural keşfi; kapalıysa motor tam çalışır |
