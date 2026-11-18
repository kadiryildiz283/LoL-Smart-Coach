# Veri Kaynakları ve Kapsam Raporu

## Sağlayıcı matrisi

| Sağlayıcı | Erişim | İzin | Kapsam | Durum |
|---|---|---|---|---|
| **Data Dragon** (ddragon.leagueoflegends.com) | Resmî, anahtarsız | Kamuya açık | 173 şampiyon: kimlik, tags, base stats (menzil dahil), yetenekler, item/rün | ✅ Tam |
| **League of Graphs** | curl_cffi + cf_clearance (gerçek tarayıcı challenge) | `user_granted_2026-11-18` (proje sahibi; kutsal_amac.md §3 amendment) | Rol bazlı WR/pick/ban + örneklem; counters (ham WR, vs-avg, Games, rakip rol); vs sayfaları (matchup WR, gold@15, örneklem) | 🔄 Brute-force koşu sürüyor (resume'lu) |
| **Riot Match-v5** | Resmî API | `RIOT_API_KEY` gerekli | Maç-seviyesi sonuçlar → kalibrasyon | ⛔ Anahtar yok (dış bağımlılık) |
| **Legacy repo JSON** | Yerel dosya | — | 172 şampiyon, 18k matchup (normalize skor, ham WR kayıp), 7k sinerji | ✅ Migre edildi (kalite bayraklı) |

## LoG erişim mekanizması ve sınırlar

1. Headed Chromium (Playwright) Cloudflare **non-interaktif JS challenge**'ı çözer.
2. `cf_clearance` cookie + UA paylaşılır → bulk fetch curl_cffi ile (penceresiz, hızlı).
3. **İnteraktif CAPTCHA/Turnstile kalıcıysa DURULUR** (`ChallengeBlocked`); solving servis yok.
4. 429 → 60s soğuma; 403 → session yenileme; istek arası 1.2s.
5. Cookie süresi dolarsa tek tarayıcı re-resolution (masaüstünde kısa pencere).

## Legacy kusurların sözleşme düzeyinde düzeltilmesi (denetim bulguları)

| Kusur (eski kod) | Yeni davranış |
|---|---|
| Başarısız indirmede `0.0` WR yazılırdı | `null + missing_reason`; publish kapısı geçersiz veriyi karantinaya alır |
| Ham WR normalizasyonda silinirdi (`del raw_wr`) | Ham WR korunur; legacy skor ayrı alanda (`legacy_derived_score`, unit=SCORE) |
| Eski dosyalar güncel sayılırdı (resume patch kör) | Dataset patch kaynaktan doğrulanır (LoG "Patch: 16.22", DD versions.json); içerik-adresli versiyon |
| Tekrar eden eşleşmeler (Kennen ×2) | Doğal anahtar dedup + görünür `dedup_actions` |
| `region:"iron"` (lig/sunucu karışması) | `rank_scope=IRON_PLUS`, `region=ALL` ayrı alanlar |
| Genel WR rol-bazlı gibi kullanılırdı | `overall_win_rate` champions.json'da; rol stats ayrı; fallback açık bayraklı |
| Test kaydı production'da | `TestChampionPipeline` karantinaya alındı (`data/quarantine/`) |

## Build / Rune ve "varsa" alanları (§3.1)

- **Items:** LoG `/champions/items/{slug}/{rank}` — Starting/Core/Boots/Final bölümleri,
  resmî item ID'leri (`tooltip-var="item-XXXX"`), ham popularity/WR fraction'ları
  (`data-sort-*`). Örneklem sayfada yok → `sample_size=null + missing_reason`.
- **Runes:** `/champions/runes/{slug}/{rank}` — 5 rune seti, perk ID'leri, popularity/WR.
- **Duration curve / side WR / XP performansı:** endpoint'ler henüz map edilmedi →
  `null + explicit missing_reason` (uydurma yok). Stats sayfasındaki graphDD dizileri
  tarihsel trend (2014+ timestamp), duration bucket DEĞİL — doğrulandı.
- **role_play_rate / flex_pick_rate:** rol pick oranlarından türetilir, `derived` bayraklı.
- **Coverage dürüstlüğü:** manifest `matchup_pair_coverage_ratio` = gözlenen çift /
  rol-kesişimli mümkün çift; counters top-N'dir, tam kapsama vs fazıyla hedeflenir.

## Mevcut kapsam (son publish)

- champions: 173 (172 legacy + DD'den yeni şampiyon "Locke" — otomatik kimlik eşleme)
- champion_role_stats: 211 (legacy, örneklem yok) → LoG faz 1 ile örneklemli rol stats geliyor
- matchups: 18.293 legacy (derived) → LoG faz 2/3 ile ham WR + örneklem + gold@15 geliyor
- synergies: 7.292 legacy → LoG partner tabloları ile gözlemsel geliyor
- mechanics: 173 şampiyon, 1.211 doğrulanmış mekanik özellik (menzil/base stats)
- game_rules: 1.813 kural (173 menzil gerçeği + ~1.634 koşullu menzil-baskı kuralı + 6 hipotez ailesi)

## Kalibrasyon dürüstlük kapısı (§23.11)

Toplulaştırılmış WR verisiyle maç-seviyesi P(win) modeli **eğitilmez**.
`RIOT_API_KEY` gelene kadar mod **HEURISTIC**; `predicted_win_probability=null`.
Protokol hazır: zaman-bazlı split, gelecek-seçim sızıntı koruması, Brier/log-loss/ECE,
baseline'ı geçme kapısı (`engine/evaluation/backtest.py`).
