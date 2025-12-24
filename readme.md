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

## 🚀 Kullanılan Teknolojiler
* **Backend:** Python
* **UI:** PyQt6 (Modern Frameless Window with Gaming Aesthetics)
* **Visualization:** Pyqtgraph
* **Connection:** LCU-Driver (League Client Update API)

## 🤝 Katkıda Bulunma
Her türlü feedback, veri güncellemesi veya kod geliştirmesine açığız! 
- Veri setindeki (JSON) hataları düzeltebilirsiniz.
- Yeni UI bileşenleri ekleyebilirsiniz.
- Algoritmayı daha hassas hale getirecek fikirler sunabilirsiniz.

---
<div align="center">
  <p><i>"GL & HF in your games!"</i></p>
</div>
