<div align="center">
exe linki = https://drive.google.com/file/d/1g7ZAUk021o9pxbJXtVkPUFCVPUbFyOMl/view?usp=sharing
  <img src="assets/logo.png" alt="LoL Smart Coach Logo" width="120" height="120">
  
  <h1>🧠 LoL Smart Coach</h1>
  <h3>AI Powered Draft Assistant for League of Legends</h3>
  <p>
    <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/GUI-PyQt6-41CD52?style=for-the-badge&logo=qt&logoColor=white" alt="PyQt6">
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge" alt="License">
    <img src="https://img.shields.io/badge/Status-Active-success?style=for-the-badge" alt="Status">
    <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey?style=for-the-badge" alt="Platform">
  </p>

  <p>
    <b>LoL Smart Coach</b>, League of Legends şampiyon seçim ekranında (Champion Select) size gerçek zamanlı ve stratejik tavsiyeler veren gelişmiş bir yapay zeka asistanıdır.
  </p>
  
  <p>
    Sadece "Kazanma Oranı"na bakmaz; <b>Takım Dengesi</b>, <b>Uzman Görüşü</b>, <b>Counter Mekanikleri</b> ve <b>Sınıf Avantajlarını</b> harmanlayarak bir Challenger koç gibi düşünür.
  </p>

  <p>
    <a href="#-kurulum">📥 Kurulum</a> •
    <a href="#-özellikler">✨ Özellikler</a> •
    <a href="#-nasıl-çalışır">⚙️ Algoritma</a> •
    <a href="#-katkıda-bulunma">🤝 Katkıda Bulunma</a>
  </p>

</div>

<hr>

<h2 id="-özellikler">✨ Özellikler</h2>

<table>
  <tr>
    <td width="200"><b>🔌 LCU Entegrasyonu</b></td>
    <td>Oyun istemcisini (Client) otomatik algılar. Seçim ekranına girildiğinde takımları, yasaklamaları ve rolünüzü anlık çeker.</td>
  </tr>
  <tr>
    <td><b>🧠 Hibrit Yapay Zeka</b></td>
    <td>İstatistiksel verileri (LeagueOfGraphs) ve <b>Uzman Bilgisini (Expert Knowledge)</b> harmanlayarak karar verir.</td>
  </tr>
  <tr>
    <td><b>⚖️ Takım Dengesi</b></td>
    <td>Takımınız "Full AD" mi oldu? Yapay zeka bunu fark eder ve ısrarla AP (Büyü Hasarı) vuran şampiyonlar önerir.</td>
  </tr>
  <tr>
    <td><b>🛡️ Hard Counter</b></td>
    <td>İstatistikler yanılsa bile (Örn: Düşük eloda Zed vs Ziggs), uzman modülü devreye girer ve <i>"Bunu alma, yok olursun"</i> der.</td>
  </tr>
  <tr>
    <td><b>🔮 Maç Tahmini</b></td>
    <td>5v5 seçim tamamlandığında, iki takımın kompozisyonunu analiz ederek kazanma olasılıklarını hesaplar.</td>
  </tr>
  <tr>
    <td><b>🎨 Modern UI</b></td>
    <td>PyQt6 ile geliştirilmiş, Neon detaylı, Hacker/Cyberpunk temalı modern arayüz.</td>
  </tr>
</table>

<hr>

<h2 id="-ekran-görüntüleri">📸 Ekran Görüntüleri</h2>

<div align="center">
  <img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/bcab3116-5b62-4fa1-a8a3-80ff3c5b0df8" />
  <br>
  <em>Seçim ekranı analizi ve yapay zeka önerileri.</em>
</div>

<hr>

<h2 id="-kurulum">🚀 Kurulum</h2>

<p>Projeyi yerel makinenizde çalıştırmak için aşağıdaki adımları izleyin.</p>

<h3>1. Gereksinimler</h3>
<ul>
  <li>Python 3.9 veya üzeri</li>
  <li>Git</li>
</ul>

<h3>2. Projeyi Klonlayın</h3>
<pre><code>git clone https://github.com/KULLANICI_ADINIZ/LoL-Smart-Coach.git
cd LoL-Smart-Coach</code></pre>

<h3>3. Sanal Ortam (Önerilen)</h3>
<details>
  <summary><b>Sanal Ortam Kurulum Detayları (Tıkla ve Genişlet)</b></summary>
  
  <br><b>Windows:</b>
  <pre><code>python -m venv venv
venv\Scripts\activate</code></pre>

  <b>Linux / Mac:</b>
  <pre><code>python3 -m venv venv
source venv/bin/activate</code></pre>
</details>

<h3>4. Kütüphaneleri Yükleyin</h3>
<pre><code>pip install -r requirements.txt</code></pre>

<h3>5. Uygulamayı Başlatın</h3>
<p>League of Legends istemcisi açıkken veya kapalıyken çalıştırabilirsiniz.</p>
<pre><code>python main.py</code></pre>

<hr>

<h2 id="-nasıl-çalışır">🧮 Algoritma Mantığı (The Brain)</h2>

<p>Sistem, her şampiyon için dinamik bir <b>Skor</b> hesaplar. Bu skor aşağıdaki formül ile elde edilir:</p>

<pre>
Total Score = (WinRate * 20) + (Synergy * 2) + (LaneAdv * 15) + (ExpertBonus) + (TeamNeed)
</pre>

<ul>
  <li><b>Win Rate (WR):</b> %50'nin üzerindeki her puan için +20 Puan.</li>
  <li><b>Expert Veto:</b> Eğer uzman veritabanında "Bu şampiyon rakibe ezilir" yazıyorsa <b>-2000 Puan</b> ceza kesilir.</li>
  <li><b>Expert Bonus:</b> Eğer uzman veritabanında "Bu şampiyon rakibi ezer" yazıyorsa <b>+600 Puan</b> bonus verilir.</li>
  <li><b>Takım İhtiyacı:</b> Takımda 3+ AD karakter varsa, AP karakterlere <b>+100 Puan</b> bonus verilir.</li>
  <li><b>Sınıf Avantajı:</b> Taş-Kağıt-Makas mantığı uygulanır (Suikastçi > Büyücü, Tank > Suikastçi vb.).</li>
</ul>

<hr>

<h2>🏗️ Proje Yapısı</h2>

<pre>
LoL_Smart_Coach/
├── core/                       # 🧠 Backend (Beyin)
│   ├── lcu_connector.py        # LoL Client WebSocket bağlantısı
│   ├── ai_recommendation_final.py # Ana Puanlama Algoritması
│   └── match_predictor.py      # Maç Sonucu Tahmin Motoru
│
├── data/                       # 💾 Veritabanı (JSON)
│   ├── tum_sampiyonlar_verisi_full.json # Ana Veri (Stat + Expert)
│   ├── expert_knowledge.json   # İşlenmiş Uzman Görüşleri
│   ├── champion_damage_scores.json # Şampiyonların AD/AP puanları
│   └── url_mappings.json       # URL düzeltme haritası
│
├── assets/                     # 🖼️ Görseller ve stil dosyaları
│
├── main.py                     # 🖥️ Arayüz (GUI) ve Başlatıcı
├── requirements.txt            # Bağımlılıklar
└── (Yardımcı Scriptler)        # Veri çekme ve işleme araçları
</pre>

<hr>

<h2>📦 Windows İçin Derleme (.exe)</h2>

<p>Bu projeyi bir <code>.exe</code> dosyasına dönüştürmek için:</p>

<ol>
  <li>PyInstaller yükleyin: <code>pip install pyinstaller</code></li>
  <li>Aşağıdaki komutu çalıştırın:</li>
</ol>

<pre><code>pyinstaller --noconsole --onefile --name "LoL_Smart_Coach" --add-data "data;data" --add-data "core;core" --icon=assets/logo.ico main.py</code></pre>

<small><i>Not: Linux/Mac kullanıyorsanız noktalı virgül (;) yerine iki nokta üst üste (:) kullanın.</i></small>

<hr>

<h2 id="-katkıda-bulunma">🤝 Katkıda Bulunma</h2>

<p>Bu proje açık kaynaktır! Geliştirmeye katkıda bulunmak isterseniz:</p>
<ol>
  <li>Bu repoyu <b>Fork</b> edin.</li>
  <li>Yeni bir özellik için dal oluşturun (<code>git checkout -b feature/YeniOzellik</code>).</li>
  <li>Değişikliklerinizi yapın ve <b>Commit</b> atın.</li>
  <li>Dalı <b>Push</b>layın ve bir <b>Pull Request</b> açın.</li>
</ol>

<hr>

<h2>⚠️ Yasal Uyarı</h2>

<p>
  <i>LoL Smart Coach</i>, Riot Games tarafından onaylanmamıştır ve Riot Games'in veya League of Legends'ın yapımında veya yönetiminde yer alan herhangi birinin görüşlerini yansıtmaz. League of Legends ve Riot Games, Riot Games, Inc. şirketinin ticari markaları veya tescilli ticari markalarıdır.
</p>

<p>
  Bu proje <b>"Adil Oyun"</b> kurallarına uygundur. Oyun dosyalarına müdahale etmez, hile (script) içermez; sadece istemcinin (LCU) sunduğu yerel API'yi "Okuma" (Read-Only) amaçlı kullanır.
</p>

<div align="center">
  <sub>Developed with ❤️ by Kadir Yildiz</sub>
</div>

