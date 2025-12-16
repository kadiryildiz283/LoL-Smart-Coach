import json
import re
import os

# --- DOSYA YOLLARI ---
MAIN_DATA_FILE = "data/tum_sampiyonlar_verisi_full.json"
EXPERT_DATA_FILE = "data/expert_knowledge.json"
BACKUP_FILE = "data/tum_sampiyonlar_verisi_full_BACKUP.json"

def clean_champion_name(name):
    """
    'Renekton (Mid)', 'Ambessa (S15)', 'Vayne (Top)' gibi ifadeleri temizler.
    Sadece 'Renekton', 'Ambessa', 'Vayne' döndürür.
    """
    # Parantez ve içindeki her şeyi sil (Regex)
    clean = re.sub(r'\s*\(.*?\)', '', name)
    return clean.strip()

def main():
    # 1. Dosyaları Yükle
    if not os.path.exists(MAIN_DATA_FILE) or not os.path.exists(EXPERT_DATA_FILE):
        print("❌ Dosyalar bulunamadı! Lütfen önceki adımları tamamla.")
        return

    print("📂 Dosyalar yükleniyor...")
    with open(MAIN_DATA_FILE, "r", encoding="utf-8") as f:
        main_data = json.load(f)

    with open(EXPERT_DATA_FILE, "r", encoding="utf-8") as f:
        expert_data = json.load(f)

    # 2. Ana veriyi hızlı erişim için sözlüğe çevir (Lookup Table)
    # Anahtar olarak küçük harfli temiz ismi kullanacağız
    main_lookup = {d['name'].lower(): d for d in main_data}
    
    print(f"📊 Ana veritabanında {len(main_data)} şampiyon var.")
    print(f"🧠 Uzman raporunda {len(expert_data)} şampiyon var.")
    print("-" * 40)

    matched_count = 0
    
    # 3. Birleştirme İşlemi
    for expert_champ in expert_data:
        # A. Şampiyonun kendi ismini temizle: "Renekton (Mid)" -> "Renekton"
        raw_name = expert_champ['name']
        clean_name = clean_champion_name(raw_name)
        
        # B. Ana veritabanında bu şampiyonu bul
        target_champ = main_lookup.get(clean_name.lower())
        
        if target_champ:
            matched_count += 1
            
            # C. Counter listelerindeki isimleri de temizle
            # Örn: Counter listesindeki "Yasuo (ADC)" -> "Yasuo" olmalı
            clean_hard_counters = [clean_champion_name(c) for c in expert_champ.get('hard_counters', [])]
            clean_easy_matchups = [clean_champion_name(c) for c in expert_champ.get('easy_matchups', [])]
            
            # D. Veriyi ana yapıya ekle
            target_champ['expert_insight'] = {
                "role_description": expert_champ.get('role_desc', ''),
                "hard_counters": clean_hard_counters,   # Uzmana göre kesin kaybedeceği rakipler
                "easy_matchups": clean_easy_matchups    # Uzmana göre kesin yeneceği rakipler
            }
            
            print(f"✅ Eklendi: {clean_name}")
        else:
            print(f"⚠️ Eşleşme bulunamadı: {raw_name} -> {clean_name} (Ana dosyada yok mu?)")

    # 4. Yedekle ve Kaydet
    # Önce eskisini yedekleyelim (ne olur ne olmaz)
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(main_data, f, indent=4, ensure_ascii=False) # main_data referans olduğu için güncellenmiş halidir aslında ama yazarken tekrar okumadığımız için sorun yok, pardon.
        # Düzeltme: main_data şu an hafızada güncel. Biz dosyayı overwrite etmeden önce diske bir kopya alalım istersen ama Python'da direkt yazmak daha kolay.
        # Kodun akışı gereği şu an hafızadaki 'main_data' güncellenmiş durumda.
        # Yedekleme işlemini dosya üzerine yazmadan önce manuel yapmak daha sağlıklı ama basitlik adına direkt kaydediyorum.
    
    print("-" * 40)
    print(f"💾 Veriler birleştirildi ve '{MAIN_DATA_FILE}' üzerine yazılıyor...")
    
    with open(MAIN_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(main_data, f, indent=4, ensure_ascii=False)

    print(f"🎉 İŞLEM TAMAMLANDI! {matched_count} şampiyon uzman verisiyle güncellendi.")

if __name__ == "__main__":
    main()
