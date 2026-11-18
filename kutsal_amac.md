# GÖREV: League of Legends Draft Intelligence Engine — Üretim Kalitesinde Uçtan Uca Geliştirme

## 0. Rolün ve ana hedefimiz

Sen kıdemli bir yazılım mimarı, veri mühendisi, istatistikçi, makine öğrenmesi mühendisi ve League of Legends draft analisti olarak çalışacaksın.

Görevin mevcut projeyi inceleyerek dünyanın en güçlü teorik şampiyon seçimi öneri sistemlerinden biri olabilecek, bilimsel olarak değerlendirilebilir ve üretim kalitesinde bir **Draft Intelligence Engine** haline getirmek.

Bu proje basit bir counter pick listesi, tier list veya LLM sohbet uygulaması olmayacak.

**Temel soru:**

"Mevcut seçimler, yasaklamalar, oynayacağım rol, meta, takım kompozisyonları, belirsiz rakip rolleri ve henüz yapılmamış seçimler göz önüne alındığında, teorik olarak hangi şampiyonu seçmek takımımın kazanma olasılığını en fazla artırır?"

Sistemin bunu güvenilir istatistikler, oyun mekanikleri, olasılık modelleri ve gelecekteki draft simülasyonları üzerinden hesaplamasını istiyorum.

Oyuncunun mevcut şampiyon havuzuyla sınırlama yapma. Bütün seçilebilir ve ilgili rolde makul biçimde oynanabilen şampiyonları değerlendir. Ancak şampiyonun mekanik zorluğunu ve veri setindeki şampiyon deneyimi etkisini açıklamada gösterebilirsin.

Ana hedefimiz teorik optimumdur; oyuncuya özel optimum ayrı ve gelecekte eklenebilecek bir mod olsun.

## 1. Mevcut projeyi koruyarak çalış

İlk olarak bütün repoyu incele:

- Mevcut mimariyi, PyQt6 arayüzünü ve veri modellerini tespit et.
- Kullanılan bütün JSON dosyalarını ve onları üreten betikleri incele.
- Counter hesaplamasını, mevcut puanları, veri normalizasyonunu, rank ve region filtrelerini analiz et.
- Kullanılan veri kaynaklarını ve güncelleme mekanizmalarını denetle.
- LLM entegrasyonu varsa nasıl kullanıldığını incele.
- Çalışan fonksiyonları, eksiklikleri ve mimari sorunları raporla.

Özellikle geçmiş incelemelerde belirlenen sorunları doğrula: başarısız indirmede sıfır veri yazılması, ham kazanma oranlarının normalizasyon sırasında kaybedilmesi, eski dosyaların güncel kabul edilmesi, tekrar eden eşleşmeler ve lig ile sunucu kavramlarının karıştırılması.

Bunları körü körüne doğru kabul etme; mevcut kodda hâlâ geçerli olup olmadıklarını test et.

İşe başlamadan Git çalışma durumunu incele ve mevcut değişiklikleri koru. Güvenli bir checkpoint oluştur. Kullanıcının değişikliklerini silme, geri alma veya üzerine yazma.

Her şeyi sıfırdan yazmak yerine doğru çalışan bileşenleri koru. Fakat kötü tasarlanmış bir altyapıya yalnızca geçici yamalar ekleme. Gerekirse sınırları net, test edilebilir bir mimari oluştur.

Mevcut teknolojiler üzerinden ilerle; büyük teknoloji değişiklikleri için somut gerekçe üret.

## 2. Sistem mimarisi

Aşağıdaki bileşenleri birbirinden bağımsız fakat entegre çalışan modüller olarak tasarla:

1. **Data Acquisition & Validation:** Veri toplama, doğrulama, sürümleme ve güncelleme.
2. **Champion Knowledge Engine:** Şampiyonların oyun mekaniklerini ve yetenek profillerini modelleme.
3. **Meta Engine:** Güncel yamadaki rol bazlı şampiyon gücünü hesaplama.
4. **Role Inference Engine:** Belirsiz rollerin olasılıksal dağılımını hesaplama.
5. **Lane Matchup Engine:** Aynı koridordaki karşılaşmaları değerlendirme.
6. **Team Synergy Engine:** Müttefik şampiyonlar arasındaki uyumu analiz etme.
7. **Enemy Threat Engine:** Rakip kompozisyonun yarattığı tehditleri değerlendirme.
8. **Draft Simulation Engine:** Henüz yapılmamış seçimleri modelleme.
9. **Decision & Calibration Engine:** Tüm kanıtları birleştirme ve öneri sıralama.
10. **Local LLM Coach:** Hesaplanmış kararları kullanıcıya açıklama.
11. **Evaluation Engine:** Tahmin kalitesi, veri güvenilirliği ve regresyon testleri.

Bunları birbirinden habersiz, aynı bilgiyi tekrar tekrar puanlayan motorlar olarak tasarlama.

Modüller arasında güçlü tipli, versiyonlanmış veri sözleşmeleri bulunsun.

LLM kararın istatistiksel kaynağı olmasın. Sayısal karar motoru LLM kapalıyken de eksiksiz çalışabilsin.

## 3. Veri kaynakları ve League of Graphs entegrasyonu

Öncelikli istatistik sağlayıcısı tercihim:

https://www.leagueofgraphs.com/

Veri erişimi sürdürülebilir ve izlenebilir olacak.

> **AMENDMENT 2026-11-18 (kullanıcı yetkilendirmesi):** Proje sahibi Kadir, League of Graphs'tan
> otomatik veri çekimine açıkça izin vermiştir ("lol graphs'dan kaba kuvvet veri çekebilirsin,
> şartnameyi değiştir, ben izin veriyorum"). Bu izin proje sahibinin kendi sorumluluğundadır;
> LoG'un yayımlanmış kullanım şartları değişmez ve site tarafında erişim kısıtlama riski devam eder.
> İzin kaydı veri provenance'ında `permission: user_granted_2026-11-18` olarak taşınır.

Bu nedenle:

- LeagueOfGraphsProvider **AÇIK** geliştirilecek; izin kapsamı ve yapılandırması `engine/config.py` üzerinden yönetilecek.
- Kaba kuvvet = tam kapsama: tüm şampiyonlar, rol bazlı meta, rol-kesişimli matchup'lar; ham WR ve örneklem sayısı korunarak.
- Rate limit nazik tutulacak (istek arası bekleme, 429'da uzun soğuma, 403'ta session yenileme); CAPTCHA kırma veya kimlik doğrulama duvarı aşma YOK.
- Kullanılabilecek endpointleri, oran limitlerini ve veri alanlarını yapılandırılabilir yap.
- Siteye özel veri ayrıştırmayı diğer uygulama bileşenlerinden tamamen izole et (provider içinde, pipeline'a sadece normalize kayıt döner).
- Sistem Riot API ve diğer uygun kaynaklarla da çalışabilsin; LoG erişilemezse son sağlam veri seti korunur.

Resmî Riot API ve Riot Data Dragon altyapısını destekle:

https://developer.riotgames.com/docs/lol

Data Dragon'u şampiyon kimlikleri, görseller, yetenekler, eşyalar, rünler ve sürümlü statik oyun verileri için kullan.

Riot Match-v5 üzerinden uygun API erişimi varsa kendi istatistiksel veri kümelerimizi üretmeyi destekle. API'de hazır bulunmayan istatistiklerin ayrıca hesaplanması gerektiğini unutma.

Başka bir sağlayıcı eklemeden önce lisans, kullanım şartları, veri kapsamı ve kalite değerlendirmesi yap.

### 3.1 Gerekli istatistiklerin tamamı

Veri toplama mimarisi şu grupları desteklemeli:

**Champion / Role Meta**

- Şampiyon kimliği, adı ve geçerli rolü.
- Patch ve oyun modu.
- Win rate, pick rate, ban rate.
- Gerçek örneklem büyüklüğü.
- Rolün toplam oynanma oranı.
- Rank, sunucu ve bölgesel dağılım.
- Taraf bazlı kazanma oranı (varsa).
- Zaman aralığı ve veri güncelliği.
- Oyun süresine göre kazanma eğrisi (varsa).
- Şampiyon deneyimine göre performans (varsa).

**Matchup Data**

- A ve B şampiyon kimlikleri.
- A'nın rolü ve rakibin rolü.
- Aynı koridor eşleşmesi mi, çapraz takım eşleşmesi mi?
- A'nın B'ye karşı ham kazanma oranı.
- Eşleşme maç sayısı.
- Beklenen kazanma oranından fark.
- Koridor kazanma metrikleri.
- 10/15. dakika gold, CS ve XP farkı (varsa).
- Erken, orta ve geç oyun performansı (varsa).
- Patch, rank, region, oyun modu ve kaynak.
- İstatistiksel belirsizlik.

**Synergy Data**

- Aynı takımdaki iki şampiyonun birlikte kazanma oranı.
- Birlikte oynanma örneklemi.
- Şampiyonların rollerinin ne olduğu.
- Tekil şampiyon güçlerinden beklenen sonuca göre sinerji farkı.
- Birlikte oynama oranı.
- Daha büyük takım kombinasyonları için veri mevcutsa ek etkileşimler.

**Draft / Composition Data**

- Her rolün meta dağılımı.
- Flex pick oranları.
- Ban ve pick frekansları.
- Takım kompozisyonu profilleri.
- Hasar, kontrol, başlatma ve koruma özellikleri.
- Şampiyonlar arasındaki mekanik etkileşimler.
- Oyun süresi ve taraf avantajı.
- Gelecek draft tahmini için koşullu seçim olasılıkları.

**Build / Rune Data**

- Şampiyon ve rol bazlı eşya seçenekleri.
- Başlangıç eşyaları ve core build.
- Botlar, rünler, yetenek geliştirme sırası.
- Build popülerliği, kazanma oranı ve örneklem.
- Eşleşme ve rakip kompozisyonuna göre seçenekler.
- Mümkünse eşya satın alma zamanları ve maç öncesi durum.

Bu veri gruplarının her biri her sağlayıcıdan alınamıyor olabilir.

**Erişilemeyen veriyi asla uydurma.** Eksik alanı `null`, durumunu da açık bir `missing_reason` ile işaretle.

Bir sayfada sadece en iyi 15 eşleşme bulunuyorsa bütün eşleşmeler indirilmiş gibi davranma.

### 3.2 Veri doğruluğu

Aşağıdaki ayrımları kesinlikle koru:

- `region` ve `rank` ayrı alanlar olacak.
- Şampiyonun genel kazanma oranı ile rol bazlı kazanma oranı ayrı tutulacak.
- Aynı koridor eşleşmesi ile rakip takımda bulunma etkisi ayrı tutulacak.
- Ham istatistikler ile türetilmiş puanlar ayrılacak.
- Eksik istatistik sıfır değer olarak kaydedilmeyecek.
- `50.8%` gibi oranlar içeride standart olarak `0.508` biçiminde tutulacak.
- Örneklem sayısı tahmin edilip gerçek örneklem gibi gösterilmeyecek.
- Farklı kaynakların aynı metriği aynı anlama gelip gelmediği doğrulanacak.
- Kazanma oranlarının yönü ve perspektifi belirsiz olmayacak.
- Patch numarası veri kaynağından doğrulanacak.
- Yeni şampiyonlar ve yeniden tasarlanan şampiyonlar otomatik kimlik eşleştirmesinde korunacak.

Başarısız bir güncelleme başarılı son veri setini asla bozamamalı.

## 4. JSON veri mimarisi

Uygulamanın bütün istatistiklerini rastgele büyüyen JSON dosyalarında saklama.

JSON Schema ile doğrulanan, versiyonlanmış veri sözleşmeleri oluştur. Büyük miktarda maç verisini ihtiyaca göre ilişkisel veya analitik depoda tutabilir, dışarıya standart JSON/JSONL çıktıları sunabilirsin.

En azından şu mantıksal veri kümeleri bulunsun:

- `dataset_manifest.json`
- `champions.json`
- `champion_role_stats.json`
- `matchups.json`
- `synergies.json`
- `builds.json`
- `champion_mechanics.json`
- `draft_snapshot.json`
- `recommendation.json`
- `ingestion_report.json`

Aşağıdaki JSON biçimleri başlangıç sözleşmesi örnekleridir. Gerekiyorsa daha güçlü biçimde geliştir, ancak örnekteki alanların anlamını koru.

### 4.1 Champion/Role istatistik kaydı

```json
{
  "schema_version": "1.0",
  "champion_id": 84,
  "role": "MIDDLE",
  "patch": "source-verified-patch",
  "queue": "RANKED_SOLO",
  "region": "ALL",
  "rank_scope": "EMERALD_PLUS",
  "stats": {
    "win_rate": null,
    "pick_rate": null,
    "ban_rate": null,
    "role_play_rate": null,
    "sample_size": null
  },
  "provenance": {
    "provider": "riot_derived",
    "source_url": null,
    "collected_at": null,
    "period_start": null,
    "period_end": null
  },
  "quality": {
    "status": "missing",
    "missing_reason": "not_yet_collected",
    "confidence": null
  }
}
```

### 4.2 Matchup kaydı

```json
{
  "schema_version": "1.0",
  "champion_id": 84,
  "champion_role": "MIDDLE",
  "opponent_id": 103,
  "opponent_role": "MIDDLE",
  "relation_type": "SAME_LANE",
  "patch": "source-verified-patch",
  "region": "ALL",
  "rank_scope": "EMERALD_PLUS",
  "sample_size": null,
  "observed_win_rate": null,
  "expected_win_rate": null,
  "adjusted_matchup_delta": null,
  "lane_gold_diff_15": null,
  "lane_cs_diff_15": null,
  "lane_xp_diff_15": null,
  "confidence_interval": null,
  "provenance": {
    "provider": "riot_derived",
    "source_url": null,
    "collected_at": null
  },
  "quality": {
    "status": "missing",
    "missing_reason": "not_yet_collected"
  }
}
```

Bu sayılar veritabanında gerçekten karşılık bulduğunda doldurulacak. Örnekte bilerek gerçek istatistik yazmıyorum.

### 4.3 Dataset manifest

```json
{
  "schema_version": "1.0",
  "dataset_id": "unique-dataset-id",
  "status": "validated",
  "game": "LEAGUE_OF_LEGENDS",
  "patch": "source-verified-patch",
  "generated_at": null,
  "sources": [],
  "coverage": {
    "champions": 0,
    "champion_roles": 0,
    "matchups": 0,
    "synergies": 0
  },
  "quality": {
    "validation_passed": false,
    "warnings": [],
    "missing_segments": []
  }
}
```

Bu yalnızca yapı örneğidir; gerçek yayın işlemi tamamlanmadan `validated` durumuyla işaretlenmemeli.

JSON sözleşmelerine güçlü veri doğrulama testleri ekle.

## 5. Güvenilir veri güncelleme sistemi

Veri hattı aşağıdaki aşamalardan geçsin:

`Acquisition -> Raw Staging -> Parsing -> Normalization -> Validation -> Deduplication -> Quality Assessment -> Versioned Publish`

Kurallar:

1. Veri çekimi kesintiye uğrarsa yeniden başlatıldığında kaldığı yerden devam edebilsin.
2. Başarılı tamamlanmadan yeni veri seti yayımlanmasın.
3. Geçersiz sonuç eski sağlam veriyle değiştirilmesin.
4. Son sağlam veri seti her zaman korunabilsin.
5. Şampiyon, rol, patch, rank, region ve queue kombinasyonları karışmasın.
6. Her kaydın kaynağı ve güncelleme tarihi takip edilsin.
7. Tekrarlı kayıtlar doğal anahtarlarla tespit edilsin.
8. Çelişen kayıtlar sessizce birleştirilmesin; doğruluk kuralları uygulansın.
9. Güncelleme işlemi idempotent olsun.
10. Geçersiz, eski veya eksik veriler kullanıcıya görünür olsun.

Her güncellemede kapsam, başarı, hata, tekrar, eksik alan ve veri tutarlılığı raporu üret.

Önemli olan çok veri toplamak değil, anlamı bilinen doğru veri toplamaktır.

## 6. Champion Knowledge Engine

Her şampiyonu sadece Tank, Assassin, Mage, Fighter gibi tek kategorili sınıflara ayırmak yetersiz.

Bunun yerine çok boyutlu ve rol bazlı bir oyun profili oluştur.

En azından şu özellikleri modelle:

- Fiziksel, büyü ve gerçek hasar.
- Burst ve sustained damage.
- Menzil ve erişim.
- Mobility ve dash bağımlılığı.
- Engage ve disengage.
- Peel ve carry protection.
- Hard CC ve soft CC.
- Waveclear ve lane priority.
- Poke ve siege.
- Sustain, shield ve healing.
- Anti-heal, anti-shield ve anti-mobility.
- Tank shredding ve anti-tank.
- Frontline ve durability.
- Pick potential.
- Objective control ve secure.
- Split push.
- Early, mid ve late scaling.
- Power spike ve eşya bağımlılığı.
- Mekanik karmaşıklık ve hata toleransı.

Bu özellikleri yalnızca LLM'ye sorup 1–10 arasında puanlatma.

Mümkün olanları sürümlü oyun verilerinden, doğrulanmış kurallardan veya ölçülmüş istatistiklerden türet.

Uzman tarafından belirlenen özellikleri ayrı ve kaynaklı biçimde tut.

Doğrulanmış mekanik etkileşimleri açıkça modelle. Örneğin bir hareket engelleme özelliğinin rakibin hangi tür yeteneklerini etkilediğini değerlendir.

Şampiyon mekanikleri patch ile değiştiğinde bu bilgi de güncellenebilsin.

## 7. Meta Engine

Meta gücünü salt kazanma oranıyla ölçme.

Şampiyonun rol bazlı ve koşullu gücünü tahmin et:

- Güncel kazanma performansı.
- Meta popülerliği.
- Örneklem güvenilirliği.
- Rol uygunluğu.
- Rank/region farkları.
- Yeni yamaya geçiş etkisi.
- Oyun süresi dağılımı.
- Mümkünse taraf avantajı.

Kazanma oranını 0–10'a çevirerek ham değerleri silme.

Az örneklemli verileri geniş örneklem referansına yaklaştırmak için istatistiksel shrinkage kullan. Olasılıkları kalibre et.

Patch, rank veya region verisi eksik olduğunda kontrollü hiyerarşik fallback yap. Fallback ile elde edilen veri, doğrudan gözlemlenmiş veri gibi sunulmasın.

Yeni yama ilk çıktığında önceki yamalardan yararlanılabilir, fakat yama değişikliğinin boyutu ve ilgili şampiyon değişiklikleri dikkate alınmalı.

## 8. Lane Matchup Engine

A şampiyonunun B karşısında %54 kazanması otomatik olarak +4 counter avantajı anlamına gelmez.

Şampiyonların genel gücünden beklenen karşılaşma sonucu ile gözlemlenen sonucu karşılaştır.

Matchup değerlendirmesi:

- Beklenen galibiyet olasılığı.
- Gözlemlenen eşleşme kazanma oranı.
- Bu ikisi arasındaki düzeltilmiş fark.
- Örneklem ve belirsizlik.
- Erken koridor altın, CS ve XP farkı.
- Koridor baskısı ve önceliği.
- Oyun evrelerindeki güç değişimi.
- Şampiyon mekaniklerinin birbirini nasıl etkilediği.

Aynı koridor karşılaşmasını, rakip takımın başka rolündeki şampiyonla genel etkileşimden ayır.

Örneğin TOP oynayan bir şampiyonun karşı takım MID oyuncusuna karşı galibiyet ilişkisini doğrudan TOP koridor counter istatistiği sayma.

Kazanma oranı ve koridor avantajı arasındaki korelasyonu hesaba kat; aynı etkiyi tekrar tekrar puanlama.

Eksik veya düşük örneklemli eşleşmeleri olduğundan kesin gösterme.

## 9. Role Inference Engine

Rakip şampiyonların rollerini bağımsız ve kesinmiş gibi tahmin etme.

Tüm takımın olası rol atamalarını birlikte çöz.

Örneğin karşı takımda flex oynanabilen üç şampiyon varsa bu üçlü için beş rolün tutarlı dağılımlarını değerlendir.

Model şu bilgileri kullansın:

- Rol bazlı pick rate.
- Şampiyonun bilinen flex rolleri.
- Diğer takım arkadaşlarının olası rolleri.
- Mevcut kilitlenmiş veya bilinen roller.
- Seçim sırası.
- Patch ve rank bağlamı.
- Takımın tamamı için geçerli rol atama kısıtları.

Çıktı, olası takım rol atamalarının normalize edilmiş ortak olasılık dağılımı olsun.

Bir şampiyonun rolü bilinmiyorsa ona tek bir rolü zorla atama.

Sistem rol belirsizliğinin seçim sıralamasını ne kadar etkilediğini de raporlasın.

## 10. Team Synergy Engine

Kendi takımımızdaki şampiyonları sadece sınıf etiketiyle değerlendirme.

Takımın aşağıdaki alanlardaki durumunu incele:

- Hasar çeşitliliği.
- Fiziksel/büyü hasarı dengesi.
- Frontline.
- Engage ve disengage.
- Peel.
- CC zinciri.
- Poke ve siege.
- Pick kompozisyonu.
- Teamfight gücü.
- Side lane baskısı.
- Objective kontrolü.
- Erken ve geç oyun güç dağılımı.
- Carry koruma.
- Şampiyonların yetenek kombinasyonları.

Birlikte yüksek kazanma oranına sahip iki şampiyonun gerçekten güçlü sinerji oluşturduğunu varsayma. Genel şampiyon güçlerini ve rol etkilerini kontrol et.

Sadece çiftli sinerjileri toplamakla yetinme; takım kompozisyonunun bütüncül işlevini değerlendir.

Birden fazla takım arkadaşının aynı ihtiyacı zaten karşıladığı durumlarda marjinal katkı azalmalı.

Örneğin takımda zaten güçlü engage bulunuyorsa yeni engage şampiyonunun değeri ile hiç engage bulunmayan takımdaki değeri eşit olmamalı.

## 11. Enemy Threat Engine

Seçilecek adayın bütün rakip takım karşısındaki etkileşimini analiz et.

Önemli konular:

- Rakibin burst ve sustained damage profili.
- CC yoğunluğu.
- Rakibin erişim ve dive potansiyeli.
- Adayın bu tehditlere karşı savunması.
- Rakip frontline'ı aşabilme kapasitesi.
- Rakibin poke veya engage planını engelleyebilme.
- Adayın önemli rakip şampiyonlara erişebilmesi.
- Rakibin peel veya disengage kapasitesi.
- Adayın takım savaşındaki rolünü gerçekleştirebilmesi.

Koridor counter'ı ile bütün takım counter'ı farklı şeylerdir.

Aday rakip koridorda avantajlı olsa bile diğer dört rakip tarafından etkisizleştirilebiliyorsa sistem bunu hesaba katsın.

## 12. Future Draft Engine — Projenin en önemli farkı

Sistemin yalnızca mevcut draft'ı değil, gelecekteki olası draft tamamlanmalarını da değerlendirmesini istiyorum.

Desteklenmesi gereken senaryolar:

**Senaryo A:** Ben son seçimim. Dört takım arkadaşım ve beş rakip belli. Sistem mevcut bütün şampiyonları değerlendirip en iyi teorik seçimi bulmalı.

**Senaryo B:** Kendi takımımda üç seçim, rakipte üç seçim yapılmış ve sıra bende. Ben seçtikten sonra bir takım arkadaşım ve iki rakibim daha seçecek. Sistem bu bilinmeyenlerin etkisini hesaba katmalı.

**Senaryo C:** Ben erken seçim yapıyorum. Rakip rollerinin büyük bölümü bilinmiyor. Sistem daha güvenli blind pick adaylarını değerlendirebilmeli.

### 12.1 Draft state

Draft durumunda şu bilgiler korunmalı:

- Blue ve red tarafı.
- Oyun modu ve draft formatı.
- Gerçek pick/ban sırası.
- Seçilmiş şampiyonlar.
- Yasaklı şampiyonlar.
- Henüz boş seçim slotları.
- Kullanıcının tarafı, sırası ve rolü.
- Bilinen ve belirsiz oyuncu rolleri.
- Gelecekte hangi takımın hangi adımda seçeceği.
- Kullanılabilir şampiyon kümesi.

Draft kuralları format ve yama değişikliklerine göre yapılandırılabilir olmalı.

### 12.2 Gelecek seçim modeli

Bir aday seçildiğinde rakibin verebileceği cevapları değerlendir.

Aynı zamanda takım arkadaşının sonraki seçimini de değerlendir.

Rakip seçimleri için koşullu bir olasılık modeli kullan:

P(gelecek seçim | mevcut draft, roller, meta, banlar, önceki seçimler)

Her rakibin kusursuz counter seçtiğini varsayma.

Ancak rakibin güçlü counter cevabı verebileceği riskli senaryoları da ihmal etme.

### 12.3 Arama algoritması

Başlangıçta makul bir aday eleme ve beam-search yaklaşımı kullanabilirsin.

Gerekirse Monte Carlo örnekleme, expectimax veya başka bir olasılıksal arama yöntemi değerlendir.

Şunları mutlaka uygula:

- Geçersiz draft dallarını eleme.
- Geçerli rol dağılımları.
- Yasaklı ve seçilmiş şampiyonların tekrar seçilememesi.
- Olasılık temelli gelecek seçim adayları.
- Düzenli ve çeşitlendirilmiş örnekleme.
- Önemli kötü senaryoların değerlendirilmesi.
- Deterministik seed ve tekrarlanabilir testler.
- Arama bütçesi ve zaman sınırı.
- Gereksiz tekrarları engelleyen önbellek.
- Yeni seçim yapıldığında hızlı yeniden hesaplama.

İlk sürümde bütün olası draft kombinasyonlarını brute force ile taramaya çalışma.

### 12.4 Risk değerlendirmesi

Her aday için:

- Beklenen sonuç.
- Makul kötü senaryolar.
- Tahmin belirsizliği.
- Flex belirsizliği.
- Gelecek counter riski.
- Diğer seçimlerden ne kadar etkilendiği.

gibi metrikleri hesapla.

Kötü senaryo ölçümünde düşük olasılıklı, aşırı uç durumların tüm sistemi gereksiz yere yönlendirmesini önle.

Beklenen değer ve risk için açık, kalibre edilebilir bir seçim politikası oluştur.

Risk toleransı yapılandırılabilir olabilir; varsayılan politika teorik beklenen galibiyet avantajını esas alsın.

## 13. Decision Engine — Gerçek hedefimiz

Sonuçları rastgele ağırlıklarla toplayan basit bir puanlama motoru istemiyorum.

Hedef:

**Seçilebilir bir şampiyonun, mevcut draft bilgisi ve mümkün gelecek seçimler altında takımın galibiyet olasılığına yapacağı beklenen katkıyı hesaplamak.**

Mümkün olduğunda uygun istatistiksel veya makine öğrenmesi modelleri geliştir.

Önce basit, açıklanabilir bir baseline oluştur.

Sonra daha gelişmiş modellerin baseline'ı gerçekten geçip geçmediğini test et.

Aday değerlendirmesi:

1. Geçerli mi ve seçilebilir mi?
2. Hedef rolde makul ve veriyle desteklenebilir mi?
3. Güncel meta gücü nedir?
4. Doğrudan koridor eşleşmesi ne durumda?
5. Bilinen müttefiklerle uyumu ne?
6. Bilinen rakiplere karşı işlevi ne?
7. Bilinmeyen roller sonucu değiştiriyor mu?
8. Gelecekteki seçimlerle nasıl etkilenebilir?
9. Olası tamamlanmış draft'ların beklenen sonucu ne?
10. Bu tahmin ne kadar güvenilir?

Ham win rate değerlerini doğrudan toplayıp bu çıktıyı galibiyet olasılığı olarak sunma.

Gerçek kazanma olasılığı modeli kalibre edilene kadar sonuçları `ranking_score` veya benzeri ayrı bir isimle göster.

İstatistiksel galibiyet tahmini yalnızca doğrulandıktan ve kalibre edildikten sonra `predicted_win_probability` alanına yazılsın.

Aday skorundaki her katkı ölçülebilir, açıklanabilir ve test edilebilir olsun.

Veri güveni düştüğünde skorun kesinliği de düşmeli.

## 14. Local LLM Coach — Qwen entegrasyonu

Kullanılacak yerel model:

- Host: `172.16.10.142`
- Model kimliği: `qwen3.8:27b`

Önce çalışan sunucu altyapısını tespit et.

Ollama, OpenAI uyumlu API veya başka bir servis kullanılıyor olabilir. Protokolü, portu ve endpointleri varsayma; erişebildiğin servis keşif yöntemleriyle doğrula.

Model adı sunucuda birebir bulunmuyorsa mevcut modelleri kontrol et, eşleşmeyi yapılandırılabilir yap ve doğrulanmamış başka bir modeli sessizce kullanma.

Servis erişilemiyorsa ana karar motorunun çalışmasını engelleme.

LLM'nin görevi:

- Karar motorundan gelen kanıtları anlamlandırmak.
- En iyi öneriyi Türkçe açıklamak.
- Rakip şampiyon mekaniklerini yorumlamak.
- Oyuncuya koridor ve takım savaşı planı sunmak.
- Önemli riskleri açıklamak.
- Gerekçeli alternatifler göstermek.
- Veri eksikliği ve belirsizlikleri anlaşılır anlatmak.

LLM bütün ham veri arşivini her istekte okumayacak.

Yalnızca gerekli adayların ilgili matchup, synergy, meta ve composition kanıtlarını alacak.

**LLM'ye sınırsız karar yetkisi verme.**

- Seçilmiş veya yasaklı şampiyon öneremez.
- Var olmayan istatistik üretemez.
- Veriyle desteklenmeyen kazanma oranları uyduramaz.
- Karar motorunun sıralamasını denetimsiz değiştiremez.
- Kaynakların yama ve güven bilgilerini korur.
- Desteklenmeyen mekanik açıklamalarını gerçekmiş gibi sunamaz.

İstendiğinde alternatif öneri sunabilir, ancak alternatifin neden farklı olduğunu karar motoru kanıtlarıyla açıklamalı.

LLM çıktısı yapılandırılmış JSON sözleşmesine uygun olmalı, şema doğrulamasından geçmeli.

Timeout, retry, context budget, JSON parse hatası ve servis kesintisi durumlarına yönelik koruma ekle.

İç ağdaki model bağlantısını yapılandırılabilir yap. Servisi veya erişim bilgilerini herkese açık hale getirme. Gerekirse uygulama ile model arasındaki erişimi ağ seviyesinde kısıtla.

## 15. Recommendation JSON sözleşmesi

Her öneri en azından şu bilgileri içersin:

```json
{
  "schema_version": "1.0",
  "draft_id": "draft-example",
  "model_version": "untrained",
  "dataset_id": "dataset-example",
  "recommended_champion_id": null,
  "recommended_role": "MIDDLE",
  "predicted_win_probability": null,
  "ranking_score": null,
  "confidence": null,
  "evidence": {
    "meta": null,
    "lane_matchup": null,
    "team_synergy": null,
    "enemy_threat": null,
    "future_draft": null
  },
  "risk": {
    "counterpick_exposure": null,
    "role_uncertainty": null,
    "data_uncertainty": null
  },
  "alternatives": [],
  "explanations": [],
  "source_references": [],
  "limitations": [],
  "status": "not_evaluated"
}
```

Bunun tam JSON Schema tanımını oluştur ve uygun alanları ayrıntılandır.

Önemli şart: Bir sonuç neden üretildiği sonradan denetlenebilir olmalı.

Sistem önerilerinin sıralaması, veri seti sürümü ve kullanılan model sürümü izlenebilmeli.

## 16. Arayüz ve kullanıcı deneyimi

Mevcut PyQt6 arayüzünü incele. Kullanışlı bileşenleri koruyarak profesyonel draft paneli haline getir.

Ana ekran:

- Kendi takımının beş seçim slotu.
- Rakip takımın beş seçim slotu.
- Yasaklamalar.
- Rol seçici.
- Patch, rank ve sunucu seçenekleri.
- Bilinen ve bilinmeyen rol göstergeleri.
- Seçim sırası.
- Önerilen ana şampiyon.
- En güçlü iki alternatif.
- Öneri gerekçeleri.
- Veri güvenilirliği.
- Olası gelecek counter riskleri.
- Qwen ile detaylı yorum alanı.

Kullanıcının her seçim değişikliğinde yeniden hesaplama yapabilmesini sağla.

Kritik hedef: Seçim ekranı süresinde hızlı ve kararlı sonuç.

Karar motorunu önbellekli ve ölçülebilir yap. İlk performans hedefi sıcak veriyle p95 2 saniye içinde temel öneri üretebilmek olsun; gerçek donanım ve veri hacmiyle benchmark yapıp hedefin sağlanıp sağlanmadığını raporla.

LLM açıklaması temel kararı bloklamamalı. Ayrı hazırlanabilsin.

Örneğin kullanıcı yeni seçim yaptığında önce sayısal öneri güncellensin; Qwen açıklaması daha sonra ekrana gelsin.

## 17. Model eğitimi ve değerlendirme

Başarıyı yalnızca birkaç örnek draft üzerinde doğru gibi görünmesine göre değerlendirme.

Geçmiş maçları kullanarak tekrarlanabilir test altyapısı kur.

### Baseline modeller

- Salt meta kazanma oranı.
- Salt koridor counter istatistiği.
- Meta + matchup.
- Meta + matchup + synergy.
- Tam kompozisyon modeli.
- Gelecek draft değerlendirmesi eklenmiş model.

Gelişmiş modelin basit modellere karşı katkısını ölç.

### Değerlendirme metrikleri

- Brier score.
- Log loss.
- Beklenen kalibrasyon hatası.
- Ranking tutarlılığı.
- Role inference doğruluğu.
- Draft tahmini kalitesi.
- Veri kapsamı.
- Düşük örneklem dayanıklılığı.
- Yama değişimlerinde performans.
- Belirsizlik ve kalibrasyon.
- Öneri gecikmesi.
- Bağımsız validator başarı oranı.

Eğitim ve test verilerini zaman bazında ayır. Gelecek yamaların sonuçları eski yamaların tahminlerine sızmasın.

Geçmiş draft'ların önceki seçim durumları yeniden oluşturulurken o anda bilinmeyen gelecekteki seçimleri sisteme gösterme.

Seçilmemiş alternatiflerin gerçek maç sonucunu bilemeyeceğimizin farkında ol. Backtest başarısını doğrudan nedensel galibiyet artışı olarak sunma.

Gerekiyorsa bir canlı deneme veya daha güçlü karşılaştırma tasarımı öner.

## 18. Zorunlu test senaryoları

En az şu durumları test et:

1. Dokuz şampiyon belli, son seçim bizde.
2. Üç takım arkadaşı ve üç rakip belli, sıra bizde.
3. Sadece birkaç rakip belli, blind pick gerekiyor.
4. Rakibin flex pick yapmış olması.
5. Rakibin oynadığı rolün kesin bilinmesi.
6. Aynı şampiyonun yasaklı veya seçilmiş olması.
7. Yeni yamanın çıkmış fakat yeterli maçın toplanmamış olması.
8. Az örneklemli matchup.
9. Kaynaklardan birinin erişilemez olması.
10. Yanlış, tekrar eden veya eksik JSON.
11. Rank ve region filtreleri arasında veri farklılığı.
12. Yerel Qwen sunucusunun kapalı olması.
13. İstatistiksel güç ile takım uyumunun çelişmesi.
14. Koridorda güçlü fakat diğer rakiplere karşı zayıf aday.
15. Gelecek counter riski yüksek aday.
16. Değişen seçim sırasının sonuca etkisi.
17. Veri güncellemesinin yarıda kesilmesi.
18. Şampiyonun birden fazla rolde oynanabilmesi.
19. Kaynak metriklerinin birbirinden farklı tanımlanması.
20. Aynı draft ve aynı veri sürümünde deterministik sonuç.

Testler sadece fonksiyonları çalıştırmak için değil, hatalı stratejik çıkarımları yakalamak için de tasarlansın.

Özellikle veri bulunmadığında sistemin yanlış biçimde çok güvenli konuşmadığını doğrula.

## 19. Kod kalitesi ve operasyonel güvenilirlik

Şu kalite şartlarını uygula:

- Modüler mimari.
- Güçlü veri modelleri.
- JSON Schema doğrulaması.
- Tip denetimi.
- Unit ve integration testleri.
- Veri sağlayıcılar için mock/fixture tabanlı testler.
- Uçtan uca draft testleri.
- Deterministik rastgelelik.
- Yapılandırılmış loglar.
- Zaman aşımı yönetimi.
- Hata sınıflandırması.
- Veri sürümleme.
- Geri alma mekanizması.
- Performans profilleme.
- Ağ bağlantısı kesildiğinde kontrollü davranış.
- Gizli anahtarların ortam değişkenlerinde saklanması.
- Güvenli uygulama güncellemeleri.
- Kurulum ve çalıştırma dokümantasyonu.

Gereksiz soyutlama ve mikroservis karmaşıklığı oluşturma. Modülleri mantıksal olarak ayırmak zorunlu; her modül için ayrı bir servis kurmak zorunlu değil.

## 20. Uygulama sırası

Çalışmayı şu sırayla tamamla.

**Aşama 1 — Audit ve güvenli temel**

Mevcut repoyu denetle, sorunları kanıtla, mevcut çalışmayı koru ve veri hatalarını gider.

**Aşama 2 — Veri altyapısı**

İzinli veri sağlayıcılarını, resmî Riot entegrasyonlarını, standart JSON şemalarını ve veri doğrulama hattını oluştur.

Gerçek verinin hangi kaynaklardan sağlanabildiğini ve hangi alanların eksik kaldığını raporla.

**Aşama 3 — Güvenilir temel counter motoru**

Meta, rol, eşleşme ve örneklem belirsizliğiyle çalışan temel öneri sistemini tamamla.

Dokuz seçim belli olduğunda güvenilir sıralama üret.

**Aşama 4 — Gelişmiş kompozisyon zekâsı**

Şampiyon mekanikleri, müttefik sinerjileri, rakip tehditleri ve koşullu takım değerlendirmelerini entegre et.

**Aşama 5 — Predictive Draft Engine**

Role inference, future draft sampling, lookahead search ve risk değerlendirmesini tamamla.

Eksik draft durumları artık anlamlı biçimde analiz edilebilmeli.

**Aşama 6 — Yerel Qwen ve arayüz**

Yerel `qwen3.8:27b` modelini bağla. Profesyonel öneri ve açıklama ekranını tamamla.

**Aşama 7 — Kalibrasyon, optimizasyon ve doğrulama**

Modelleri geçmiş veriyle test et, baseline'larla kıyasla, performansı iyileştir ve regresyonları temizle.

## 21. Tamamlanma kriterleri

Projeyi yalnızca kod yazıldı diye tamamlanmış sayma.

Aşağıdaki durumlar doğrulanmalı:

- Seçilebilir şampiyonların rol bazlı kapsamı kontrol edilmiş olmalı.
- Veri kaynaklarının yetki ve erişim koşulları doğrulanmış olmalı.
- Ham ve türetilmiş istatistikler ayrılmış olmalı.
- Geçersiz veri hiçbir şekilde başarılı veri gibi yayımlanmamalı.
- Dokuz bilinen seçimle öneri üretilebilmeli.
- Eksik seçimlerle gelecek senaryoları değerlendirilebilmeli.
- Flex pick belirsizliği modellenebilmeli.
- Öneriler kaynaklarıyla açıklanabilmeli.
- LLM olmadan karar motoru çalışmalı.
- LLM bulunmayan veri ve istatistikleri uyduramamalı.
- Aynı veri ve aynı seed ile sonuçlar tekrarlanabilmeli.
- Gerçek performans ve doğruluk ölçümleri bulunmalı.
- Regression testleri geçmeli.
- Kullanıcı arayüzü kararları anlaşılır sunmalı.

Veri sağlayıcısına erişim izni veya gerekli API anahtarı henüz yoksa bunu açık bir dış bağımlılık olarak işaretle. Demo verilerle çalışan sistemin gerçek veriyle doğrulanmış olduğunu iddia etme.

## 22. Çalışma ve raporlama biçimin

Sadece mimari öneri üretip işi bırakmanı istemiyorum.

Repo erişimin ve izin verilen kaynaklar ölçüsünde gerçekten uygula, test et, doğrula ve entegre et.

Önce kısa bir mevcut durum denetimi çıkar. Ardından aşamaları somut uygulamaya dönüştür.

Her aşamada:

- Yapılan değişiklikleri açıkla.
- İlgili modülleri belirt.
- Çalıştırılan testleri ve sonuçlarını göster.
- Gerçek veri kapsamını raporla.
- Doğrulanmamış varsayımları açıkça ayır.
- Performans ölçümlerini sun.
- Bir sonraki aşamaya geçmeden temel regresyonları kontrol et.

Eksik bir bağımlılık varsa diğer bağımsız işleri sürdür. Kritik yetki veya kimlik doğrulama gerektiren adımları izinsiz aşma.

Geçici mock çıktıları gerçek üretim sonuçları gibi gösterme.

## 22. Champion Knowledge Discovery & Rule Engine — LLM ile Oyun Kanunları Üretimi

Bu projeye çok önemli bir yeni bileşen eklemeni istiyorum:

**LLM tarafından üretilen, doğrulanan, zamanla geliştirilen ve JSON formatında kalıcı olarak saklanan bir League of Legends Oyun Kanunları Bilgi Tabanı.**

Bu sistemin amacı istatistiklerin tek başına yanıltıcı kararlar üretmesini engellemek ve oyun mekaniklerine dayanan kalıcı bilgileri karar motoruna kazandırmaktır.

### 22.1. Temel problem

Örneğin Vayne ile Caitlyn arasındaki eşleşmeyi düşün.

Caitlyn'in Vayne'e kıyasla belirgin bir temel saldırı menzili avantajı vardır. Bu, Caitlyn'in özellikle erken koridor aşamasında Vayne'i farm yaparken baskılama potansiyeline sahip olması demektir.

Ancak League of Graphs üzerinde belirli bir yamada Vayne'in Caitlyn'e karşı daha yüksek maç kazanma oranına sahip olduğunu görebiliriz.

Bu iki bilgi birbiriyle mutlaka çelişmez.

- Caitlyn erken koridor aşamasında avantajlı olabilir.
- Vayne belirli takım kompozisyonlarında daha değerli olabilir.
- Vayne geç oyunda daha iyi sonuçlar alabilir.
- İstatistikler oyuncu seviyesi, örneklem veya meta nedeniyle farklılaşabilir.
- Caitlyn'in koridordaki avantajı her zaman maç galibiyetine dönüşmeyebilir.

Sistemin bu ayrımı anlayabilmesini istiyorum.

**LLM, mekanik bilgileri istatistiklerden bağımsız gerçekler olarak koruyabilmeli; ancak mekanik avantajları hiçbir zaman koşulsuz maç sonucu garantisi olarak yorumlamamalı.**

Bunun için yalnızca `matchups.json` değil, ayrıca kalıcı bir oyun bilgisi ve kurallar sistemi geliştir.

### 22.2. Üç farklı bilgi sınıfı

Üretilen bilgileri üç ana sınıfa ayır.

**A. Mekanik kurallar (Mechanic Rules)**

Oyunun yetenekleri ve mekanik etkileşimleri üzerinden doğrulanabilen bilgiler.

Örnekler:

- Bir şampiyonun diğerinden daha uzun temel saldırı menziline sahip olması.
- Bir yeteneğin belirli türdeki hareket yeteneklerini engellemesi.
- Bir şampiyonun belirli bir kontrol etkisine karşı savunma mekanizmasına sahip olması.
- Bir yeteneğin normal saldırılarla veya hareket yetenekleriyle etkileşimi.

Bu bilgiler ilgili oyun verileriyle doğrulanabilir olmalı.

**B. Stratejik ve koşullu kurallar (Strategic Rules)**

Oyun mekaniklerinden ve güvenilir analizlerden çıkarılan, belirli koşullarda geçerli stratejik ilişkiler.

Örnekler:

- Uzun menzilli bir şampiyon kısa menzilli rakibine karşı erken koridor baskısı oluşturabilir.
- Güçlü waveclear sağlayan şampiyonlar belirli eşleşmelerde koridor önceliği elde edebilir.
- Hareket yeteneklerine bağımlı şampiyonlar, hareketlerini engelleyebilen rakiplere karşı belirli durumlarda zorlanabilir.
- Engage kompozisyonları, yeterli disengage barındırmayan rakip kompozisyonlara karşı avantaj elde edebilir.

Bu kuralların koşulları, istisnaları ve belirsizlikleri olmalı.

**C. İstatistiksel eğilimler (Empirical Rules)**

Güncel maç verilerinden çıkarılan, meta ve oyuncu popülasyonuna bağlı ilişkiler.

Örnekler:

- Belirli bir yamada belirli matchup'ın ortalamadan daha güçlü sonuç vermesi.
- Bir şampiyonun belirli takım kompozisyonlarında daha iyi performans göstermesi.
- Bir eşleşmenin erken oyunda dezavantajlı olup geç oyunda avantajlı hale gelmesi.
- Belirli bir şampiyonun meta değişiminden sonra matchup performansının değişmesi.

Bu kurallar patch, rank, region, örneklem büyüklüğü ve güven aralığı ile ilişkilendirilmeli.

**Mekanik gerçek, stratejik çıkarım ve istatistiksel gözlemi aynı veri türüne indirgeme.**

### 22.3. Otomatik Rule Discovery Pipeline

Yerel `qwen3.8:27b` modelini kullanarak bir bilgi keşif hattı oluştur.

Önerilen işlem zinciri:

`Validated Data -> Evidence Collection -> LLM Rule Proposal -> Schema Validation -> Mechanic Verification -> Statistical Validation -> Conflict Detection -> Rule Registry -> Decision Engine`

Bu işlem her veri güncellemesinde sıfırdan bütün kuralları üretmemeli.

Bunun yerine:

1. Yeni veya değişen veri kümelerini tespit et.
2. İlgili şampiyonları ve eşleşmeleri belirle.
3. Mevcut JSON kurallarını yükle.
4. İlgili mekanik ve istatistiksel kanıtları topla.
5. LLM'ye mevcut kurallarla birlikte bu kanıtları ver.
6. Yeni kurallar öner.
7. Mevcut kuralların güncellenmesi gerekip gerekmediğini değerlendir.
8. Tekrarlı veya çelişkili kuralları tespit et.
9. Kuralları bağımsız validator'lardan geçir.
10. Onaylanan kuralları JSON kayıtlarına ekle veya güncelle.
11. Önceki kural sürümlerini koru.

LLM'nin oluşturduğu bir kural, yalnızca JSON biçimi doğru diye kabul edilmemeli.

### 22.4. JSON dosya mimarisi

Aşağıdaki mantıksal veri kümelerini oluştur:

- `game_rules/mechanics.json`
- `game_rules/champion_matchups.json`
- `game_rules/champion_synergies.json`
- `game_rules/team_compositions.json`
- `game_rules/strategic_principles.json`
- `game_rules/meta_observations.json`
- `game_rules/rule_registry.json`
- `game_rules/rule_conflicts.json`

Bunlar mantıksal veri koleksiyonlarıdır. Veriler büyüdüğünde veritabanı kullanabilir, JSON/JSONL biçiminde dışarı aktarabilirsin.

Her kuralın tekil ve kararlı bir kimliği olmalı.

### 22.5. Örnek kural JSON formatı

Aşağıdaki örnek gerçek bir istatistiksel sonuç değil, veri sözleşmesini göstermek için hazırlanmış temsili bir kayıttır.

```json
{
  "schema_version": "1.0",
  "rule_id": "lane-caitlyn-vayne-range-001",
  "rule_type": "strategic",
  "status": "proposed",
  "title": "Caitlyn'in Vayne'e karşı menzil baskısı",
  "subject": {
    "champion": "Caitlyn",
    "role": "BOTTOM"
  },
  "target": {
    "champion": "Vayne",
    "role": "BOTTOM"
  },
  "relation": "LANE_PRESSURE_ADVANTAGE",
  "game_phase": "EARLY",
  "claim": "Caitlyn'in temel saldırı menzili avantajı, uygun dalga ve pozisyon koşullarında Vayne üzerinde erken koridor baskısı kurabilmesini destekler.",
  "conditions": [
    "Her iki şampiyonun da BOTTOM rolünde oynanması",
    "Caitlyn'in menzil avantajını güvenle kullanabilmesi",
    "Destek eşleşmesinin baskıyı tamamen etkisizleştirmemesi"
  ],
  "exceptions": [
    "Caitlyn'in güvenli pozisyon alamaması",
    "Rakip destek ve ormancı baskısı",
    "Belirli dalga ve güç seviyesi durumları"
  ],
  "evidence": {
    "mechanical_sources": [],
    "statistical_sources": [],
    "sample_size": null,
    "observed_lane_advantage": null,
    "observed_match_win_rate": null
  },
  "confidence": {
    "mechanical": null,
    "strategic": null,
    "empirical": null
  },
  "scope": {
    "patch_from": null,
    "patch_to": null,
    "rank": "ALL",
    "region": "ALL"
  },
  "impact": {
    "category": "LANING",
    "estimated_effect": null,
    "calibration_status": "not_calibrated"
  },
  "provenance": {
    "generated_by": "qwen3.8:27b",
    "generation_type": "llm_proposal",
    "created_at": null,
    "validated_at": null,
    "validator_version": null
  },
  "review": {
    "verification_status": "pending",
    "contradictions": [],
    "last_reviewed_patch": null
  }
}
```

Bu JSON'u genişletip resmî JSON Schema haline getir.

Kuralın benzersizliği yalnızca başlığına bağlı olmasın; şampiyon, ilişki, rol, oyun evresi, koşullar ve kapsam üzerinden semantik tekrar kontrolü yap.

### 22.6. LLM kuralları nasıl üretmeli?

LLM rastgele oyun bilgisi üretmemeli.

Her kural önerisi için aşağıdaki girdileri kullan:

- Güncel şampiyon yetenek verileri.
- Şampiyonların doğrulanmış mekanik özellikleri.
- Temel saldırı menzili ve ilgili istatistikler.
- Role-specific matchup verileri.
- Early/mid/late performans verileri.
- Takım sinerjileri.
- Mevcut meta verileri.
- Daha önce doğrulanmış oyun kuralları.
- Kullanılabilir geçmiş patch istatistikleri.
- Mevcut kuralla ilişkili istisnalar.
- Kullanılan kaynakların açık referansları.

LLM mevcut şampiyonları tek tek değerlendirmekle kalmamalı; birden fazla şampiyon arasında tekrar eden mekanik ilişkileri de keşfetmeye çalışmalı.

Örneğin uzun menzil avantajının kısa menzilli şampiyonlara karşı hangi koşullarda baskı oluşturduğunu daha genel bir stratejik ilke olarak önerebilir.

Ardından bunun belirli şampiyon eşleşmelerine uygulanıp uygulanmadığı ayrıca doğrulanmalı.

Ama bir şampiyonda doğru görünen ilişkiyi bütün şampiyonlara otomatik genelleme.

### 22.7. İstatistiklerle çelişki yönetimi

Sistemde bir **Rule Conflict Resolver** oluştur.

Örneğin:

Mekanik kural:
"Caitlyn erken koridor aşamasında Vayne'e karşı menzil baskısı oluşturabilir."

Güncel istatistik:
"Belirli bir yamada Vayne'in Caitlyn karşısında maç kazanma oranı daha yüksek."

Bu durumu otomatik olarak bir kuralın yanlış olduğu şeklinde değerlendirme.

İlk olarak ölçülen kavramları ayır:

- Koridor baskısı.
- Koridor altın/CS avantajı.
- Maç kazanma oranı.
- Oyun süresine göre performans.
- Takım kompozisyonu etkisi.
- İstatistiksel güvenilirlik.

Koridor baskısı ile maç galibiyeti farklı hedef değişkenlerdir.

Eğer veriler gerçekten aynı hedef değişken üzerinde çelişiyorsa:

1. Veri kapsamını karşılaştır.
2. Patch farkını kontrol et.
3. Örneklem büyüklüğünü incele.
4. İstatistiksel belirsizliği değerlendir.
5. Şampiyon değişikliklerini kontrol et.
6. Mekanik kuralın koşullarını incele.
7. Kuralı geçersiz kılabilecek yeni kanıtları değerlendir.

Gerekirse kuralın durumunu `needs_review`, `superseded` veya `rejected` olarak değiştir.

Önceki kuralları sessizce silme. Geçmiş değişiklikler denetlenebilir olsun.

**Çok önemli: Oyun kanunları güncel istatistikleri yok saymak için değil, onları doğru yorumlamak ve eksik verilerde daha iyi genelleme yapmak için kullanılmalı.**

### 22.8. Kuralların karar motoruna etkisi

Bu bilgi tabanını ana Decision Engine'e entegre et.

Ancak LLM'nin oluşturduğu kurallara rastgele +10 veya -20 counter puanı verme.

Kuralın etkisi:

- İlgili hedef değişkene.
- Geçerlilik koşullarına.
- Doğrulama durumuna.
- İstatistiksel kanıta.
- Geçerli patch'e.
- Karar motorunun kalibrasyonuna.

bağlı olmalı.

Mekanik ve stratejik kurallar, istatistiksel modelin özelliklerine veya kısıtlarına dönüştürülebilir.

İstatistiksel tahminlerde zaten kullanılan bir bilgiyi kural üzerinden tekrar puanlayarak aynı etkiyi iki kez sayma.

Kuralın tahminlere katkısını ablation testleriyle ölç.

Yalnızca doğrulanmış ve karar modelinde kullanılması onaylanmış kurallar otomatik sıralamayı etkileyebilmeli.

LLM tarafından yeni önerilmiş, doğrulanmamış kurallar yalnızca inceleme kuyruğunda bulunmalı.

### 22.9. Kural güvenilirliği ve yaşam döngüsü

Her kural şu yaşam döngüsünü desteklesin:

`proposed -> validating -> verified -> active`

Alternatif durumlar:

`needs_review`, `rejected`, `superseded`, `deprecated`

Doğrulama türlerini ayır:

- Mekanik olarak doğrulandı.
- İstatistiksel olarak desteklendi.
- Uzman tarafından incelendi.
- Sadece LLM hipotezi.
- Yetersiz kanıt.
- Güncel yamada yeniden inceleme gerekiyor.

`confidence` alanı LLM'nin kendi kendine verdiği öznel güven puanı olmamalı.

İstatistiksel güven veriden, mekanik doğrulama güvenilir oyun kaynaklarından, stratejik güven ise test edilmiş değerlendirme süreçlerinden gelmeli.

Her kuralın kaynağı, sürümü, geçerlilik koşulları ve son inceleme tarihi tutulmalı.

### 22.10. Sürekli öğrenen bilgi tabanı

Yeni bir veri seti yayımlandığında:

1. Değişen şampiyon ve eşleşmeleri tespit et.
2. Bunlarla ilişkili mevcut kuralları bul.
3. Yeni veriyle kuralları karşılaştır.
4. Gerekirse LLM'ye yalnızca ilgili kanıtları gönder.
5. Yeni kural adaylarını üret.
6. Eski kurallarla semantik karşılaştırma yap.
7. Doğrulama süreçlerini çalıştır.
8. Sadece doğrulanmış güncellemeleri yayımla.

Aynı bilgi için yüzlerce tekrar eden kural oluşmasın.

Örneğin bir şampiyonun menzil avantajı tek bir doğrulanabilir mekanik gerçek olarak saklanabilir; bu avantajın belirli eşleşmelerdeki koşullu sonuçları ayrıca ilişkilendirilebilir.

Bir kural güncellendiğinde eski sürümü, değişiklik nedeni ve yeni kanıtları sakla.

LLM'nin daha önce kendi ürettiği açıklamaları bağımsız kanıt kabul etme.

Sistem kendi ürettiği varsayımları tekrar tekrar okuyarak yanlış bir sonucu giderek daha kesin hale getirmemeli.

### 22.11. Genel oyun kanunlarını keşfetme

LLM'nin yalnızca iki şampiyon arasındaki counter ilişkisini öğrenmesini istemiyorum.

Daha genel stratejik ilkeleri de keşfetmesini istiyorum.

Örnek araştırma alanları:

- Menzil avantajı ve koridor baskısı.
- Waveclear ve koridor önceliği.
- Mobility ile anti-mobility etkileşimleri.
- Burst ile dayanıklılık etkileşimleri.
- Engage ile disengage ilişkileri.
- Frontline ve anti-tank özellikleri.
- Kısa takas / uzun takas avantajları.
- Erken ve geç oyun güç farkları.
- Poke ve sustain etkileşimleri.
- Pick kompozisyonları ile koruma kompozisyonları.
- Split push ve takım savaşı kompozisyonları.
- CC zincirleri ve carry erişimi.

Bu başlıkları doğru olduğu önceden kabul edilmiş evrensel kurallar olarak değil, **kanıtlarla sınanacak stratejik hipotez aileleri** olarak değerlendir.

LLM bunlardan yeni ilişkiler önerebilir. Ancak doğrulama katmanı gerçek kaynak ve verilerle kontrol etmeden bunları aktif hale getiremez.

### 22.12. Üretim ve kalite şartları

Kural üretim hattı:

- Toplu işlem desteklemeli.
- Gereksiz LLM çağrılarını önlemeli.
- Yeni kanıt olmadığında aynı işlemleri tekrar etmemeli.
- İdempotent olmalı.
- Atomik veri güncellemesi yapmalı.
- JSON Schema ile doğrulanmalı.
- Hatalı LLM çıktılarında eski kurallar korunmalı.
- Her üretilen kuralı kaynağına bağlamalı.
- Belirsiz kuralları inceleme kuyruğuna almalı.
- Patch değişikliklerini takip etmeli.
- Kural çelişkilerini raporlamalı.
- Üretilen kuralların Decision Engine'e gerçek katkısını ölçmeli.

Rule Registry için ayrıca testler oluştur.

Özellikle şu senaryoları doğrula:

1. İstatistiksel kazanma oranı mekanik koridor avantajının tersi olduğunda iki bilgi doğru şekilde birlikte korunuyor mu?
2. LLM doğrulanmamış bir mekanik ilişki önerdiğinde sistem bunu otomatik kabul ediyor mu? Etmemeli.
3. Yeni patch mekanik bir kuralı geçersiz kıldığında doğru güncelleme yapılıyor mu?
4. Az örneklemli istatistikler güçlü, doğrulanmış mekanik kanıtları gereksiz yere geçersiz kılıyor mu?
5. Güçlü ve güvenilir yeni veriler eski stratejik varsayımların yeniden değerlendirilmesini sağlayabiliyor mu?
6. Aynı kural tekrar üretilince ikinci kayıt oluşuyor mu? Oluşmamalı.
7. Kurallar kaldırıldığında veya eklendiğinde karar motorunun başarısındaki fark ölçülüyor mu?

### 22.13. Nihai hedef

Bu bileşenin sonunda elimizde sıradan bir statik counter tablosu değil, sürekli güncellenen bir **League of Legends Strategic Knowledge Graph / Rule Engine** bulunmalı.

Bilgi tabanı:

- Şampiyonların gerçek mekanik özelliklerini bilmeli.
- Hangi mekaniklerin hangi koşullarda avantaj oluşturabileceğini bilmeli.
- Güncel meta verileriyle bu bilgileri karşılaştırabilmeli.
- İstatistiksel sonuçlar ile mekanik avantajları karıştırmamalı.
- Eksik eşleşme verilerinde doğrulanmış genel bilgilerden yararlanabilmeli.
- Çelişkileri tespit edip açıklayabilmeli.
- Yeni patch'lerle bilgilerini güncelleyebilmeli.
- Ana Draft Intelligence Engine'in karar kalitesini ölçülebilir şekilde artırmalı.

**En önemli prensip:**

LLM'nin görevi oyun kurallarını keyfi olarak icat etmek değil; verilerden ve doğrulanabilir oyun mekaniklerinden yeni bilgi adayları keşfetmek, bunları yapılandırılmış JSON olarak önermek ve bağımsız doğrulama süreçleriyle güvenilir bir bilgi tabanı oluşturmaktır.

Bu sistemi ana projeye gerçek bir bileşen olarak ekle. Yalnızca teorik bir doküman oluşturmakla kalma; veri üretimi, doğrulama, kural kayıt sistemi, karar motoru entegrasyonu ve otomatik testleriyle birlikte uygula.
## 23. Unified Mathematical Language & Probabilistic Decision Framework

### 23.1. Temel amaç

Bütün Draft Intelligence Engine modüllerinin aynı matematiksel çerçevede çalışmasını istiyorum.

Mevcut sistemde Meta Engine, Lane Matchup Engine, Team Synergy Engine, Enemy Threat Engine, Future Draft Engine ve LLM Rule Engine farklı türde veriler üretmektedir.

Bunları keyfî biçimde puanlayıp toplamaya çalışma.

**Bütün sistemin ortak karar dili, bağlamı tanımlanmış olasılıksal tahminler, ölçülebilir etki büyüklükleri ve belirsizliklerden oluşmalıdır.**

Nihai hedef, aday şampiyonun seçilmesi durumunda takımın beklenen galibiyet olasılığını tahmin etmektir.

Ancak bu olasılığın gerçek maç verileriyle eğitilmiş ve kalibre edilmiş olması zorunludur.

Yeterli veri veya doğrulanmış model bulunmuyorsa sistemi geçici sıralama modunda çalıştır; keyfî bir skoru gerçek kazanma olasılığı gibi sunma.

### 23.2. Canonical Evidence Schema

Bütün analiz motorları ortak bir kanıt sözleşmesi kullanmalı.

Her sinyal aşağıdaki bilgileri taşımalı:

- `signal_id`
- `signal_type`
- `subject`
- `target`
- `context`
- `metric`
- `raw_value`
- `unit`
- `sample_size`
- `uncertainty`
- `source`
- `patch`
- `validation_status`
- `model_version`

Örnek:

```json
{
  "schema_version": "1.0",
  "signal_id": "matchup-lane-gold-001",
  "signal_type": "LANE_MATCHUP",
  "subject": {
    "champion": "Caitlyn",
    "role": "BOTTOM"
  },
  "target": {
    "champion": "Vayne",
    "role": "BOTTOM"
  },
  "context": {
    "patch": "source-verified",
    "rank_scope": "EMERALD_PLUS",
    "region": "ALL",
    "game_phase": "EARLY",
    "perspective": "SUBJECT"
  },
  "metric": "GOLD_DIFFERENCE_AT_15",
  "raw_value": null,
  "unit": "GOLD",
  "sample_size": null,
  "uncertainty": {
    "standard_error": null,
    "lower_bound": null,
    "upper_bound": null
  },
  "source": {
    "provider": "riot_derived",
    "dataset_id": null
  },
  "validation_status": "missing",
  "model_version": null
}
```

Bu temel şemadır; gerektiğinde genişlet.

Önemli olan bütün verilerin aynı anlamsal yapıya sahip olmasıdır.

Farklı birimler tek bir alanda gizlenmemeli. Altın, kazanma oranı, menzil, örneklem sayısı ve etki büyüklükleri tipli biçimde korunmalı.

### 23.3. Ortak matematiksel temsil

İlk üretim modelinde açıklanabilir, düzenlileştirilmiş ve hiyerarşik bir olasılıksal model geliştir.

Tamamlanmış bir draft için başlangıç yaklaşımı:

`P(win | draft, context) = sigmoid(base + champion_effects + matchup_effects + synergy_effects + composition_effects)`

Buradaki her etki, aynı doğrusal tahminci üzerinde öğrenilmiş bir log-odds katkısı olmalıdır.

Asla şu şekilde işlem yapma:

`meta_score + counter_score + synergy_score + llm_score`

Bunun yerine:

1. Ham verileri ayrı tut.
2. Bağlama göre özellikler oluştur.
3. Özellikleri uygun biçimde ölçekle.
4. Birlikte eğitilen bir tahmin modeli kullan.
5. Adayları aynı hedef değişkene göre değerlendir.
6. Tahmin olasılıklarını kalibre et.
7. Belirsizliği ve veri güvenini ayrıca hesapla.

Modelde düzenlileştirme, hiyerarşik kısmi havuzlama (partial pooling) ve uygun istatistiksel shrinkage yöntemlerini kullan.

Yalnızca veri sayısının çok yüksek olması yeterli değildir. Özelliklerin doğru tanımlandığını ve modelin yeni maçlara genellenebildiğini doğrula.

### 23.4. Etkilerin anlamları

Aşağıdaki kavramları ayrı tanımla:

**Champion Main Effect**

Şampiyonun belirli rol, patch ve oyuncu popülasyonundaki temel istatistiksel gücü.

**Lane Matchup Effect**

İki şampiyonun aynı koridorda karşılaşmasından kaynaklanan, temel güçlerinin ötesindeki ilave ilişki.

**Ally Synergy Effect**

İki veya daha fazla müttefik şampiyonun beraber oynandığında beklenen performanstan sapması.

**Enemy Interaction Effect**

Adayın rakip takım şampiyonlarıyla etkileşiminden doğan ek ilişki.

**Composition Effect**

Takımın tamamının hasar profili, kontrol, başlatma, dayanıklılık, ölçeklenme ve diğer yapısal özelliklerinin etkisi.

**Mechanical Features**

Menzil, hareket yetenekleri, kontrol mekanikleri, iyileşme, koruma gibi doğrulanabilir oyun özellikleri.

Mekanik özellikleri doğrudan galibiyet bonusu olarak kullanma. Bunları uygun özellik mühendisliği, koşullu etkileşim veya doğrulanmış model kısıtı olarak değerlendir.

### 23.5. Double Counting Prevention

Aynı bilginin birden fazla motorda tekrar hesaplanmasını önle.

Örneğin:

- Bir matchup kazanma oranı.
- Aynı matchup'tan türetilmiş counter skoru.
- Bu matchup hakkında LLM'nin ürettiği stratejik kural.

aynı kanıttan türemiş olabilir.

Bunların üçüne de bağımsız pozitif etki vererek sonucu yapay biçimde güçlendirme.

Kanıtların kaynak ilişkilerini takip eden bir provenance/dependency sistemi kur.

Aynı bilgiye bağlı özellikler için korelasyon, etkileşim ve çoklu bağlantı analizleri yap.

Model bileşenlerinin katkısını ablation testleriyle değerlendir.

### 23.6. LLM Rule Engine ile matematiksel entegrasyon

Aşama 22'de oluşturulan JSON oyun kuralları bu modelle bütünleşmeli.

Her kural şu üç tür çıktının birini veya birkaçını destekleyebilir:

1. **Mechanic Feature:** Doğrulanmış bir oyun özelliği.
2. **Conditional Interaction:** Belirli koşullarda ortaya çıkması beklenen etkileşim.
3. **Empirical Hypothesis:** Veriyle sınanabilecek istatistiksel hipotez.

Örnek:

"Caitlyn'in Vayne'e karşı erken oyunda menzil baskısı oluşturabilmesi."

Bunu doğrudan `+10 counter` şeklinde puanlama.

Bunun yerine:

- İlgili mekanik özelliği doğrula.
- Kuralın koşullarını değerlendir.
- Bunun erken koridor avantajı üzerinde ne kadar açıklayıcı olduğunu geçmiş veriyle test et.
- Etki ölçülebiliyorsa modelin ilgili özelliği olarak kullan.
- Veri yoksa kuralı açıklama veya düşük güvenli hipotez olarak sakla.
- Kuralın maç kazanma oranına etkisini, koridor baskısından bağımsız olarak doğrulamadan varsayma.

LLM'nin oluşturduğu kuralın etkisi model tarafından öğrenilmeli veya bağımsız veriyle doğrulanmalı.

LLM'nin kendi verdiği puanlar istatistiksel katsayı kabul edilmemeli.

### 23.7. Farklı hedef değişkenleri ayır

Tek bir kazanma oranından her türlü oyun avantajını çıkarmaya çalışma.

Mümkün olduğunda ayrı tahmin hedefleri geliştir:

- `P(MATCH_WIN)`
- `EXPECTED_GOLD_DIFF_15`
- `EXPECTED_CS_DIFF_15`
- `EXPECTED_XP_DIFF_15`
- `P(LANE_ADVANTAGE)`
- `P(DRAFT_RESPONSE | CURRENT_DRAFT)`

Bu hedeflerin aynı ölçekte olması gerekmez.

Örneğin altın farkı altın cinsinden tahmin edilebilir. Bunların ana galibiyet tahminine nasıl bağlandığı ayrıca öğrenilmeli.

Erken koridor altın farkı ile maç galibiyetini aynı olay gibi değerlendirme.

Her hedef için ayrı hata ölçümü, veri kapsamı ve belirsizlik bulunmalı.

### 23.8. Future Draft matematiği

Tamamlanmamış draft'ta her aday için gelecek seçimler ve rol atamalarının olasılıklarını hesaba kat.

Her adayın beklenen sonucu:

`Q(candidate) = Σ P(future_draft, role_assignment | current_draft, candidate) × P(win | completed_draft)`

Toplam, geçerli tamamlanmış senaryoların dağılımını temsil eder.

Bütün kombinasyonlar hesaplanamıyorsa uygun bir Monte Carlo veya önem örnekleme yaklaşımı kullan.

Şunları raporla:

- Beklenen sonuç.
- Monte Carlo tahmin hatası.
- Gelecek draft belirsizliği.
- Rol belirsizliği.
- Tahmin modelinin belirsizliği.
- Olası kötü senaryo kaybı.

Bu belirsizlik türlerini birbirine karıştırma.

### 23.9. Güven, eksik veri ve fallback

Her tahminin güvenilirliğini değerlendir.

Az örneklemli matchup verisi daha geniş referanslara yaklaştırılabilmeli.

Yeni patch'te eksik veri varsa önceki yamalardan kontrollü bilgi aktarımı yapılabilmeli.

Ancak fallback sonucu doğrudan ölçülmüş istatistik olarak gösterme.

Üç farklı çalışma modu oluştur:

**CALIBRATED**

Gerçek verilerle eğitilmiş, geçmiş maçlarda test edilmiş ve kalibre edilmiş kazanma olasılığı modeli.

**PROVISIONAL**

Kısmen eğitilmiş veya henüz yeterince doğrulanmamış tahmin modeli. Sonuç tahmini gösterilebilir fakat kalibrasyon eksikliği açıkça belirtilmeli.

**HEURISTIC**

Yeterli istatistiksel model bulunmadığında doğrulanmış mekanik ve uygun verilerle üretilen geçici sıralama.

HEURISTIC modunda `predicted_win_probability` üretme.

### 23.10. Karşılaştırılabilir nihai sonuç

Her aday için ortak bir karar çıktısı üret:

```json
{
  "schema_version": "1.0",
  "champion_id": 84,
  "role": "MIDDLE",
  "evaluation_mode": "HEURISTIC",
  "predicted_win_probability": null,
  "ranking_score": null,
  "prediction_interval": null,
  "expected_future_draft_value": null,
  "downside_risk": null,
  "model_uncertainty": null,
  "draft_uncertainty": null,
  "feature_contributions": [],
  "evidence_ids": [],
  "model_version": null,
  "dataset_id": null
}
```

Bu yapı başlangıç şemasıdır. Tam uygulamada:

- Etki katkılarının birimi.
- Açıklanan hedef.
- Referans/baseline.
- Kalibrasyon yöntemi.
- Belirsizlik hesaplama yöntemi.
- Gelecek draft örnekleme yöntemi.

de açıkça tanımlanmalı.

`feature_contributions` alanında katkıların log-odds, olasılık farkı veya başka bir ölçekte olup olmadığı kesinlikle belirtilmeli.

Farklı ölçeklerdeki katkılar aynı toplamda gösterilmemeli.

### 23.11. Model doğrulama şartları

En az aşağıdaki modelleri karşılaştır:

1. Basit rol bazlı meta modeli.
2. Meta + matchup modeli.
3. Meta + matchup + synergy modeli.
4. Tam composition modeli.
5. Mekanik özellikler eklenmiş model.
6. Future Draft Engine ile çalışan tam model.

Her yeni bileşenin gerçekten fayda sağlayıp sağlamadığını ölç.

Brier score, log loss, kalibrasyon eğrisi ve zaman bazlı testlerle tahmin performansını değerlendir.

Şampiyon seçiminden sonra gerçekleşmiş maç olaylarını, seçim anındaki modelin girdilerine dahil etme.

Eğer yalnızca toplulaştırılmış League of Graphs istatistikleri varsa bu verilerin gerçek maç seviyesinde bir galibiyet modeli eğitmek için yeterli olduğunu varsayma.

Maç seviyesinde uygun eğitim verisi için Riot API veya lisanslı kaynaklardan destek alınması gerekebilir.

Eksik veri nedeniyle tam model eğitilemiyorsa bunu açıkça raporla; doğrulanmamış katsayılarla gerçek kazanma olasılığı üretme.

### 23.12. Nihai zorunluluk

Sistemde ortak bir **Mathematical Contract** oluştur.

Bu sözleşme bütün motorlara aşağıdaki soruları zorunlu kılmalı:

- Hangi hedefi ölçüyorsun?
- Hangi birimi kullanıyorsun?
- Hangi veri bağlamında geçerlisin?
- Hangi kaynaktan üretildin?
- Ne kadar örneklem mevcut?
- Belirsizliğin nedir?
- Başka hangi kanıtlardan türedin?
- Hangi model tarafından nasıl kullanılıyorsun?

**Asıl hedef: Bütün analiz motorlarını aynı 0–100 puanına zorlamak değil, bütün kanıtları tek bir tutarlı, doğrulanabilir ve kalibre edilebilir karar modelinde birleştirmek.**

Bu ortak matematiksel altyapı olmadan Draft Intelligence Engine'in hiçbir nihai sıralamasını üretim kalitesinde kabul etme.

### Nihai hedef

Oyuncu şampiyon seçim ekranındayken rolünü ve mevcut seçimleri verdiğinde sistem birkaç saniye içerisinde:

1. Bütün geçerli adayları değerlendirir.
2. Bilinen ve belirsiz rakip rollerini hesaba katar.
3. Güncel metayı ve eşleşmeleri analiz eder.
4. Takım kompozisyonunu inceler.
5. Rakip takımın tamamını değerlendirir.
6. Gelecek seçim senaryolarını simüle eder.
7. Riskleri ve veri güvenilirliğini ölçer.
8. Teorik olarak en avantajlı şampiyonu önerir.
9. İki anlamlı alternatifi gösterir.
10. Yerel Qwen modeliyle önerisini kaynaklı, anlaşılır ve stratejik biçimde açıklar.

**Ürünün başarısı, bir şampiyona yüksek puan vermesi değil; o şampiyonun neden diğer bütün geçerli adaylardan daha mantıklı olduğunu kanıtlarla açıklayabilmesi ve karar kalitesinin ölçülebilir biçimde artmasıdır.**

Hedefimiz bir şampiyon tier listesi yapmak değil; gerçek bir **Draft Intelligence Engine** geliştirmektir.

Bu şartnameyi projenin ana hedef dokümanı olarak kabul et. Önce mevcut repoda hangi parçaların bulunduğunu ve hangilerinin eksik olduğunu kanıtlarla belirle, sonra sistematik biçimde uygulamaya geç.
