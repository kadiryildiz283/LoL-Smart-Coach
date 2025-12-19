<img width="1920" height="1080" alt="ai" src="https://github.com/user-attachments/assets/bc623cc1-1d6a-4a38-86bc-a48a5c6af99a" />

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
* **Görsel Analiz:** Önerilen şampiyonların neden seçilmesi gerektiğini gösteren detaylı grafikler ve açıklamalar.
* **Tamamen Özelleştirilebilir Veri:** AI'nın beynini JSON dosyaları üzerinden kendiniz eğitebilirsiniz!

## 🛠️ Kurulum

1.  **Depoyu Klonlayın:**
    ```bash
    git clone [https://github.com/kullaniciadin/lol-ai-coach.git](https://github.com/kullaniciadin/lol-ai-coach.git)
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

* **`ai_config.json`:** Hangi kriterin ne kadar önemli olduğunu (weights) belirleyin. (Örn: "Benim için counter pick, win rate'den %20 daha önemli olsun").
* **`expert_knowledge.json`:** Kendi tecrübelerinize göre özel eşleşmeler ekleyin. "Bu şampiyon bu rakibe karşı aslında çok güçlü" dediğiniz her şeyi buraya işleyebilirsiniz.
* **`champion_damage_scores.json`:** Şampiyonların hasar profillerini güncel tutun.

## 🚀 Kullanılan Teknolojiler
* **Backend:** Python
* **UI:** PyQt6 (Modern Dark Theme)
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
