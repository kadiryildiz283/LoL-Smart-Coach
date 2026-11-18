<img width="1341" height="843" alt="image" src="https://github.com/user-attachments/assets/44fdae23-3ed5-4bd2-b979-002b430e4bbb" />

<div align="center">
  <h1>🎮 LoL AI Draft Coach</h1>
  <p><b>Draft ekranını şansa bırakma; veri ve stratejiyle kazan!</b></p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" alt="Python">
    <img src="https://img.shields.io/badge/PyQt6-UI-orange?style=for-the-badge&logo=qt" alt="PyQt6">
    <img src="https://img.shields.io/badge/Status-In--Development-green?style=for-the-badge" alt="Status">
  </p>
</div>

<hr>

## 🌟 Proje Hakkında
Bu proje, League of Legends seçim ekranında (Champ Select) size gerçek zamanlı ve veri odaklı öneriler sunan bir **Draft Asistanıdır**. Sadece kazanma oranlarına bakmak yerine; takım sinerjisi, counter pick durumu, hasar dengesi (AP/AD) ve uzman görüşlerini harmanlayarak en mantıklı seçimi yapmanıza yardımcı olur.

> [!IMPORTANT]
> Bu bir "hile" yazılımı değildir. Sadece halka açık istatistikleri ve sizin belirlediğiniz stratejileri kullanarak analiz yapan bir karar destek mekanizmasıdır.

## ✨ Öne Çıkan Özellikler

* **Canlı Bağlantı (LCU):** League of Legends istemcisine doğrudan bağlanarak seçim ekranındaki şampiyonları anlık olarak algılar.
* **Akıllı Puanlama Motoru:** Şampiyonları şu kriterlere göre puanlar:
    * **Meta Gücü:** Güncel kazanma oranları (Win Rate).
    * **Sinerji:** Takım arkadaşlarınızla ne kadar uyumlusunuz?
    * **Matchup Analizi:** Rakibinize karşı koridor ve genel oyun avantajınız.
    * **Kompozisyon Dengesi:** Takımın hasar türü ve sınıf (Tank, Assassin vb.) ihtiyaçları.
* **Görsel Analiz:** Önerilen şampiyonların neden seçilmesi gerektiğini gösteren **animasyonlu kartlar** ve güç grafikleri.
* **Tamamen Özelleştirilebilir Veri:** AI'nın beynini JSON dosyaları üzerinden kendiniz eğitebilirsiniz!

## 🛠️ Kurulum

1.  **Depoyu Klonlayın:**
    ```bash
    git clone [https://github.com/kullaniciadin/lol-ai-coach.git](https://github.com/kadiryildiz283/lol-ai-coach.git)
    cd lol-ai-coach
    ```

2.  **Gerekli Kütüphaneleri Yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Uygulamayı Çalıştırın:**
    ```bash
    python main.py
    ```

## 🧠 Verileri Kendinize Göre Düzenleyin (Özelleştirme)
Bu projenin en güçlü yanı, "sabit" bir algoritma olmamasıdır. `data/` klasöründeki dosyalarla asistanınızı kişiselleştirebilirsiniz:

* **`config.json`:** Hangi kriterin ne kadar önemli olduğunu (weights) belirleyin. (Örn: "Benim için counter pick, win rate'den %20 daha önemli olsun").
* **`output/{Champion}.json`:** Her şampiyonun özel eşleşme verileri burada tutulur. `export_veri_cekici.py` ile otomatik güncellenir.
* **`champion_damage_scores.json`:** Şampiyonların hasar profillerini güncel tutun.

## 🧠 Draft Intelligence Engine (yeni çekirdek)

Eski puanlama motorunun yanında, şartnameye (`kutsal_amac.md`) göre inşa edilmiş
olasılıksal karar motoru: `engine/`.

* **Tipli veri sözleşmeleri + JSON Schema kapısı** — geçersiz veri asla yayımlanmaz.
* **Çok kaynaklı veri hattı:** Data Dragon (resmî), League of Graphs (izinli, brute-force,
  resume'lu), Riot Match-v5 (anahtar bekliyor), legacy migrasyon.
* **Matematiksel birlik:** tüm kanıtlar log-odds; matchup = gözlenen − beklenen (double-counting yok);
  shrinkage + Wilson belirsizlik; eksik veri `null + missing_reason`.
* **Joint rol çıkarımı** (flex pick'ler birlikte çözülür), **Monte Carlo gelecek draft**
  simülasyonu (seed'li, bütçeli), CVaR downside risk.
* **Oyun Kanunları Bilgi Tabanı:** Data Dragon'dan doğrulanmış mekanik gerçekler +
  LLM önerileri (bağımsız doğrulama kapıları, semantik dedup, lifecycle).
* **Yerel Qwen koç** (`qwen3.8:27b`): kararı değiştirmez, sadece açıklar; kapalıysa motor tam çalışır.
* **HEURISTIC mod dürüstlüğü:** kalibre model eğitilene kadar `predicted_win_probability=null`.

```bash
.venv/bin/python -m engine.cli ingest --providers dd,legacy,log,riot
.venv/bin/python -m engine.cli recommend --role MIDDLE --ally "Malphite,Amumu" --enemy "Zed,Caitlyn" --llm
.venv/bin/python -m pytest tests/ -m "not integration"   # 45 test
```

Ayrıntı: `ARCHITECTURE.md`, `DATA_SOURCES.md`. UI'da **Engine Coach** butonu.

## 🚀 Kullanılan Teknolojiler
* **Backend:** Python
* **UI:** PyQt6 (Modern Frameless Window with Gaming Aesthetics)
* **Visualization:** Pyqtgraph
* **Connection:** LCU-Driver (League Client Update API)
* **Engine:** jsonschema, numpy, curl_cffi, Playwright (yalnızca non-interaktif challenge)

## 🤝 Katkıda Bulunma
Her türlü feedback, veri güncellemesi veya kod geliştirmesine açığız! 
- Veri setindeki (JSON) hataları düzeltebilirsiniz.
- Yeni UI bileşenleri ekleyebilirsiniz.
- Algoritmayı daha hassas hale getirecek fikirler sunabilirsiniz.

---
<div align="center">
  <p><i>"GL & HF in your games!"</i></p>
</div>
