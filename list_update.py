from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
import json
import time

# --- AYARLAR ---
OUTPUT_FILE = "data/sampiyon_listesi.json"
URL = "https://www.leagueofgraphs.com/champions/tier-list"

def extract_json_smart(text, start_keyword):
    """
    Regex yerine karakter karakter okuyarak JSON nesnesini hatasız çıkarır.
    Süslü parantezlerin dengesini { } sayar.
    """
    start_idx = text.find(start_keyword)
    if start_idx == -1:
        return None

    # İlk '{' karakterini bul
    json_start = text.find("{", start_idx)
    if json_start == -1:
        return None

    balance = 0
    in_string = False
    escape = False
    
    # JSON verisinin sonunu bulmak için döngü
    for i in range(json_start, len(text)):
        char = text[i]
        
        if in_string:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == '{':
                balance += 1
            elif char == '}':
                balance -= 1
                # Denge sıfıra ulaştığında JSON objesi bitmiş demektir
                if balance == 0:
                    return text[json_start:i+1]
    
    return None

def main():
    print(f"🌍 Siteye bağlanılıyor (curl_cffi Chrome taklidi ile): {URL}...")

    scraper = cffi_requests.Session(impersonate="chrome120")

    try:
        response = scraper.get(URL, timeout=20)
        if response.status_code != 200:
            print(f"❌ Hata: Siteye ulaşılamadı. Kod: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Bağlantı hatası: {e}")
        return

    # --- AKILLI JSON AYRIŞTIRMA ---
    html_content = response.text
    print("🔍 Sayfa kaynağında veri bloğu aranıyor...")
    
    # Verinin başladığı yer
    keyword = "ChampionsPage.init("
    
    json_str = extract_json_smart(html_content, keyword)

    if not json_str:
        print("⚠️ HATA: Veri bloğu bulunamadı. Site yapısı değişmiş olabilir.")
        # Debug için ufak bir kontrol
        soup = BeautifulSoup(html_content, 'lxml')
        print("Sayfa Başlığı:", soup.title.text.strip() if soup.title else "Yok")
        return

    try:
        data = json.loads(json_str)
        
        # 'rankings' listesini al
        rankings = data.get("rankings", [])
        
        print(f"✅ JSON başarıyla çözüldü. {len(rankings)} şampiyon bulundu.")
        
        champions_dict = {}

        for item in rankings:
            name = item.get("championName", "").strip()
            
            # Rol verisi: item['role']['title'] içinde duruyor
            role_data = item.get("role", {})
            role = role_data.get("title", "").strip() # "AD Carry", "Mid" vs.
            
            if name and role:
                # İsim düzeltmeleri
                if name == "MonkeyKing": name = "Wukong" 

                if name in champions_dict:
                    if role not in champions_dict[name]:
                        champions_dict[name].append(role)
                else:
                    champions_dict[name] = [role]
        
        # Listeyi formatla
        final_list = []
        for name, roles in champions_dict.items():
            roles_str = ", ".join(roles)
            final_list.append({"name": name, "role": roles_str})

        # Sırala
        final_list = sorted(final_list, key=lambda x: x['name'])

        # Kaydet
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(final_list, f, indent=4, ensure_ascii=False)
        
        print("-" * 40)
        print(f"🎉 İşlem Tamamlandı! Toplam {len(final_list)} benzersiz şampiyon kaydedildi.")
        print(f"📄 Dosya: '{OUTPUT_FILE}'")

    except json.JSONDecodeError as e:
        print(f"⚠️ HATA: JSON verisi çözümlenemedi: {e}")
        # Hatalı stringin başını yazdıralım ki görelim
        print("Hatalı veri parçası:", json_str[:100])

if __name__ == "__main__":
    main()
