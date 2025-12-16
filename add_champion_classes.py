import json
import os

# --- DOSYA AYARLARI ---
MAIN_DATA_FILE = "tum_sampiyonlar_verisi_full.json"
CLASSES_FILE = "champion_classes.json"

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
    if not os.path.exists(CLASSES_FILE):
        print(f"❌ '{CLASSES_FILE}' bulunamadı! Lütfen dosyanın orada olduğundan emin ol.")
        return

    print("📂 Dosyalar yükleniyor...")
    
    # 2. Dosyaları Oku
    with open(MAIN_DATA_FILE, "r", encoding="utf-8") as f:
        main_data = json.load(f)

    with open(CLASSES_FILE, "r", encoding="utf-8") as f:
        classes_data = json.load(f)

    # 3. Tersine Arama Tablosu Oluştur (Şampiyon -> Sınıf)
    # { "Assassin": ["Zed", "Akali"] }  --->  { "zed": "Assassin", "akali": "Assassin" }
    champ_class_map = {}
    
    for class_name, champ_list in classes_data.items():
        for champ_name in champ_list:
            clean_name = normalize_name(champ_name)
            
            # Özel Durum: Senin listende "Blue Kayn" ve "Red Kayn" var.
            # Ana veride sadece "Kayn" olduğu için, "Kayn" kelimesini içerenleri yakalıyoruz.
            if "kayn" in clean_name:
                champ_class_map["kayn"] = class_name 
            else:
                champ_class_map[clean_name] = class_name

    print(f"📊 Sınıflandırma haritası oluşturuldu.")

    # 4. Ana Veriyi Güncelle
    updated_count = 0
    unknown_count = 0

    for champ in main_data:
        # Ana dosyadaki ismi al ve temizle
        current_name = normalize_name(champ['name'])
        
        # Haritada var mı?
        if current_name in champ_class_map:
            champ['class'] = champ_class_map[current_name]
            updated_count += 1
        else:
            # Listede olmayanlar için varsayılan değer
            champ['class'] = "Unknown"
            print(f"⚠️ Sınıfı bulunamadı: {champ['name']}")
            unknown_count += 1

    # 5. Kaydet
    print("-" * 40)
    print(f"💾 Veriler '{MAIN_DATA_FILE}' dosyasına güncelleniyor...")
    
    with open(MAIN_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(main_data, f, indent=4, ensure_ascii=False)

    print(f"🎉 İŞLEM TAMAMLANDI!")
    print(f"✅ Sınıf atanan şampiyon sayısı: {updated_count}")
    
    if unknown_count > 0:
        print(f"❓ Tanımsız kalan (Unknown): {unknown_count} (Bunları json dosyana ekleyebilirsin)")

if __name__ == "__main__":
    main()
