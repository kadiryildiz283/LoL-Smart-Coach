🧠 LoL Smart Coach - AI Powered Draft Assistant

LoL Smart Coach, League of Legends şampiyon seçim ekranında (Champion Select) size gerçek zamanlı ve stratejik tavsiyeler veren, Python tabanlı gelişmiş bir asistan uygulamasıdır.

Sadece istatistiklere (Win Rate) bakmaz; takım kompozisyonu (AD/AP dengesi), sinerji, hard-counter mekanikleri ve uzman görüşlerini harmanlayarak bir Challenger koç gibi düşünür.
✨ Özellikler

    🔌 Otomatik LCU Bağlantısı: Oyun istemcisini (Client) otomatik algılar, seçim ekranına girildiğinde takımları ve rolünüzü anlık çeker.

    🧠 Hibrit Yapay Zeka Algoritması:

        İstatistiksel Analiz: LeagueOfGraphs üzerinden güncel kazanma oranları ve koridor istatistikleri.

        Uzman Görüşü (Expert Insight): İstatistiklerin yanıldığı durumlarda (Örn: Düşük eloda Zed vs Ziggs) devreye giren kural tabanlı "Hard Counter" sistemi.

        Sınıf Mantığı (Rock-Paper-Scissors): Suikastçi > Büyücü > Nişancı gibi temel oyun dinamiklerini uygular.

    ⚖️ Takım Dengesi Analizi: Takımınız "Full AD" mi oldu? Yapay zeka bunu fark eder ve size ısrarla AP (Büyü Hasarı) vuran şampiyonlar önerir.

    🔮 Maç Sonucu Tahmini: İki takımın kompozisyonunu analiz ederek maç başlamadan kazanma olasılıklarını hesaplar.

    🎨 Modern Arayüz: PyQt6 ile geliştirilmiş, neon detaylı modern "Dark Mode" arayüz.

    🔄 Veri Yönetimi: Uygulama içinden tek tuşla veritabanını güncelleyebilir ve birleştirebilirsiniz.

🛠️ Kurulum

Projeyi yerel makinenizde çalıştırmak için aşağıdaki adımları izleyin.
Gereksinimler

    Python 3.9 veya üzeri

    Git

1. Projeyi Klonlayın
Bash

git clone https://github.com/KULLANICI_ADINIZ/LoL-Smart-Coach.git
cd LoL-Smart-Coach

2. Sanal Ortam Oluşturun (Önerilen)
Bash

# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate

3. Kütüphaneleri Yükleyin
Bash

pip install -r requirements.txt

(Eğer requirements.txt yoksa şu komutu kullanın: pip install PyQt6 pyqtdarktheme lcu-driver cloudscraper beautifulsoup4 requests)
4. Uygulamayı Başlatın

League of Legends istemcisi açıkken veya kapalıyken çalıştırabilirsiniz.
Bash

python main.py

🏗️ Proje Mimarisi

Bu proje modüler bir yapıda tasarlanmıştır. Katkıda bulunmak isteyenler için dosya yapısı şöyledir:

LoL_Smart_Coach/
│
├── core/                       # 🧠 Backend (Beyin)
│   ├── lcu_connector.py        # LoL Client ile WebSocket bağlantısını kurar.
│   ├── ai_recommendation_final.py # Puanlama algoritmasının çalıştığı yer.
│   └── match_predictor.py      # Maç sonucu tahmin motoru.
│
├── data/                       # 💾 Veritabanı (JSON)
│   ├── tum_sampiyonlar_verisi_full.json # Ana veri dosyası.
│   ├── expert_knowledge.json   # Uzman analizlerinin işlenmiş hali.
│   ├── champion_damage_scores.json # Şampiyonların AD/AP puanları.
│   └── url_mappings.json       # URL düzeltme haritası.
│
├── assets/                     # 🖼️ Görseller ve stil dosyaları.
│
├── main.py                     # 🖥️ Arayüz (GUI) ve ana giriş noktası.
├── list_update.py              # Güncel şampiyon listesini çeker.
├── veri_cekici_main.py         # Detaylı istatistikleri (Scraping) çeker.
├── expert_parser.py            # Text formatındaki uzman raporunu JSON'a çevirir.
├── merge_expert_data.py        # İstatistik ve Uzman verisini birleştirir.
└── merge_damage_stats.py       # Hasar profillerini ana veriye ekler.

🧮 Algoritma Nasıl Çalışıyor?

Sistem, her şampiyona bir "Skor" verir. Bu skor şu faktörlerin ağırlıklı toplamıdır:

    Genel Kazanma Oranı (Win Rate): Temel güç göstergesi.

    Koridor Eşleşmesi (Lane Matchup): Rakibi istatistiksel olarak ne kadar yendiği.

    Uzman Vetosu (Expert Veto): Eğer veritabanında "Bu şampiyon buna karşı oynayamaz" (Hard Counter) bilgisi varsa, istatistik ne derse desin o şampiyona devlet cezası kesilir (-1000 Puan).

    Takım İhtiyacı: Takımda 3 tane AD karakter varsa, AP karakterlere +100 Puan bonus verilir.

    Sinerji: Takım arkadaşlarıyla uyumlu olanlara ufak bir bonus eklenir.

Formül Özeti:
Python

Total_Score = (WinRate * 20) + (Counter_Score * 15) + (Expert_Bonus) + (Team_Need_Bonus)

📦 Windows İçin Derleme (.exe)

Bu projeyi bir .exe dosyasına dönüştürüp arkadaşlarınızla paylaşmak isterseniz:

    PyInstaller yükleyin:
    Bash

pip install pyinstaller

Şu komutu çalıştırın (Tüm veri ve çekirdek dosyalarını içine gömer):
Bash

    pyinstaller --noconsole --onefile --name "LoL_Smart_Coach" --add-data "data;data" --add-data "core;core" main.py

    (Not: Linux/Mac kullanıyorsanız ; yerine : kullanın)

🤝 Katkıda Bulunma (Contributing)

Bu proje açık kaynaktır ve geliştirmelere açıktır!

    Bu repoyu Fork edin.

    Yeni bir özellik için dal (branch) oluşturun (git checkout -b yeni-ozellik).

    Değişikliklerinizi yapın ve Commit atın (git commit -m 'Yeni özellik eklendi').

    Dalı Pushlayın (git push origin yeni-ozellik).

    Bir Pull Request açın.

⚠️ Yasal Uyarı (Disclaimer)

LoL Smart Coach, Riot Games tarafından onaylanmamıştır ve Riot Games'in veya League of Legends'ın yapımında veya yönetiminde yer alan herhangi birinin görüşlerini veya fikirlerini yansıtmaz. League of Legends ve Riot Games, Riot Games, Inc. şirketinin ticari markaları veya tescilli ticari markalarıdır. League of Legends © Riot Games, Inc.

Bu proje tamamen eğitim ve analiz amaçlıdır. Oyun dosyalarına müdahale etmez, sadece istemci (LCU) tarafından sunulan yerel API'yi dinler (Read-Only).
📄 Lisans

Bu proje MIT Lisansı altında lisanslanmıştır. Dilediğiniz gibi kullanabilir, değiştirebilir ve dağıtabilirsiniz.
