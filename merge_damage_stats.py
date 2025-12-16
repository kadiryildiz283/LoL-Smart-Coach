import json
import os

# --- DOSYA AYARLARI ---
MAIN_DATA_FILE = "data/tum_sampiyonlar_verisi_full.json"
DAMAGE_SCORES_FILE = "data/champion_damage_scores.json"

def normalize_name(name):
    """
    İsim eşleştirme şansını artırmak için temizler.
    Örn: "Kai'Sa" -> "kaisa", "Dr. Mundo" -> "drmundo"
    """
    return name.lower().replace(" ", "").replace("'", "").replace(".", "").strip()

def main():
    # 1. Dosya Kontrolü
    if not os.path.exists(MAIN_DATA_FILE):
        print(f"❌ '{MAIN_DATA_FILE}' bulunamadı!")
        return
    if not os.path.exists(DAMAGE_SCORES_FILE):
        print(f"❌ '{DAMAGE_SCORES_FILE}' bulunamadı! Lütfen önce bu dosyayı oluşturduğundan emin ol.")
        return

    print("📂 Dosyalar yükleniyor...")
    
    # 2. Dosyaları Oku
    with open(MAIN_DATA_FILE, "r", encoding="utf-8") as f:
        main_data = json.load(f)

    with open(DAMAGE_SCORES_FILE, "r", encoding="utf-8") as f:
        damage_scores = json.load(f)

    # 3. Hızlı Erişim Haritası Oluştur (Lookup Table)
    # damage_scores dosyasındaki anahtarları (isimleri) normalize ederek saklıyoruz.
    normalized_damage_map = {}
    for name, scores in damage_scores.items():
        clean_name = normalize_name(name)
        normalized_damage_map[clean_name] = scores

    print(f"📊 {len(normalized_damage_map)} adet hasar profili yüklendi.")

    # 4. Ana Veriyi Güncelle
    updated_count = 0
    missing_count = 0

    for champ in main_data:
        # Ana dosyadaki ismi al ve temizle
        current_name = normalize_name(champ['name'])
        
        # Haritada var mı?
        if current_name in normalized_damage_map:
            champ['damage_profile'] = normalized_damage_map[current_name]
            updated_count += 1
        else:
            # Listede yoksa varsayılan (Dengeli/Hybrid) ata ve bildir
            champ['damage_profile'] = {"ap": 5, "ad": 5}
            print(f"⚠️ Hasar profili bulunamadı: {champ['name']} (Varsayılan 5/5 atandı)")
            missing_count += 1

    # 5. Kaydet
    print("-" * 40)
    print(f"💾 Veriler '{MAIN_DATA_FILE}' üzerine yazılıyor...")
    
    with open(MAIN_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(main_data, f, indent=4, ensure_ascii=False)

    print(f"🎉 İŞLEM TAMAMLANDI!")
    print(f"✅ Güncellenen şampiyon: {updated_count}")
    if missing_count > 0:
        print(f"⚠️ Eksik/Varsayılan atanan: {missing_count}")

if __name__ == "__main__":
    main()
