import cloudscraper
from bs4 import BeautifulSoup
import json
import re
import time
import random
import os

# --- AYARLAR ---
REGION = "iron"  
INPUT_FILE = "data/sampiyon_listesi.json"
MAPPING_FILE = "data/url_mappings.json"
OUTPUT_FILE = "data/tum_sampiyonlar_verisi_full.json"

# Global Mapping
CHAMPION_URL_MAP = {}

# --- GÜNCELLEME BURADA: Scraper'ı daha gerçekçi yapıyoruz ---
# Cloudflare'e "Ben Windows kullanan bir Chrome tarayıcısıyım" diyoruz.
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

def load_mappings():
    global CHAMPION_URL_MAP
    if os.path.exists(MAPPING_FILE):
        try:
            with open(MAPPING_FILE, "r", encoding="utf-8") as f:
                CHAMPION_URL_MAP = json.load(f)
            print(f"✅ URL Haritası yüklendi: {len(CHAMPION_URL_MAP)} kural.")
        except:
            CHAMPION_URL_MAP = {}
    else:
        CHAMPION_URL_MAP = {}

def get_soup_via_cloudscraper(url):
    # Hata durumunda 3 kereye kadar tekrar deneme mekanizması
    for attempt in range(3):
        try:
            response = scraper.get(url)
            
            # Eğer 429 (Çok Fazla İstek) aldıysak uzun bekle
            if response.status_code == 429:
                print(f"   ⚠️ Çok hızlı gidiyoruz (429). 10 saniye soğuma...")
                time.sleep(10)
                continue

            if response.status_code == 200:
                return BeautifulSoup(response.content, 'lxml')
            elif response.status_code == 404:
                return None # Sayfa yoksa normaldir, tekrar deneme
            else:
                print(f"   ⚠️ Hata Kodu: {response.status_code} (Deneme {attempt+1}/3)")
                time.sleep(2) # Kısa bir bekleme yapıp tekrar dene

        except Exception as e:
            print(f"   ⚠️ Bağlantı hatası: {e}")
            time.sleep(2)
            
    return None

def extract_value_final(row):
    p_bar = row.find("progressbar")
    if p_bar and p_bar.has_attr("data-value"):
        try:
            val = float(p_bar["data-value"])
            if val != 0.0:
                if abs(val) < 1.0: return round(val * 100, 2)
                return round(val, 2)
        except: pass

    txt_div = row.find("div", class_="progressBarTxt")
    if txt_div:
        text = txt_div.get_text().strip()
        match = re.search(r'([+-]?\d+\.?\d*)', text)
        if match: return float(match.group(1))
    
    element_with_sort = row.find(lambda tag: tag.has_attr('data-sort-value'))
    if element_with_sort:
        try:
            val = float(element_with_sort['data-sort-value'])
            if val != 0.0:
                if abs(val) < 1.0: return round(val * 100, 2)
                return round(val, 2)
        except: pass

    return 0.0

def sanitize_name_for_url(name):
    if name in CHAMPION_URL_MAP:
        return CHAMPION_URL_MAP[name]
    return name.lower().replace(".", "").replace("'", "").replace(" ", "").replace("&", "")

def get_champion_full_data(champ_info, region):
    slug = sanitize_name_for_url(champ_info['name'])
    
    data = {
        "name": champ_info['name'],
        "role": champ_info['role'],
        "slug": slug,
        "region": region,
        "general_win_rate": 0.0,
        "synergies": [],            
        "lane_counters": [],        
        "lane_countered_by": [],    
        "lane_gold_advantage": [],  
        "lane_gold_deficit": [],    
        "general_good_against": [],
        "general_bad_against": []   
    }

    # 1. Win Rate
    tier_url = f"https://www.leagueofgraphs.com/champions/tier-list/{slug}/{region}"
    soup_tier = get_soup_via_cloudscraper(tier_url)
    
    if soup_tier:
        wr_div = soup_tier.find("div", id="graphDD2")
        if wr_div:
            try:
                raw_text = wr_div.get_text().strip().replace('%', '')
                data["general_win_rate"] = float(raw_text)
            except: pass
    
    # Kısa bir bekleme (Sayfalar arası)
    time.sleep(random.uniform(0.5, 1.0))

    # 2. Counter Tabloları
    counter_url = f"https://www.leagueofgraphs.com/champions/counters/{slug}/{region}"
    soup_counter = get_soup_via_cloudscraper(counter_url)

    if soup_counter:
        boxes = soup_counter.find_all("div", class_="box")
        for box in boxes:
            header = box.find("h3")
            if not header: continue
            
            h_text = header.text.lower().strip()
            target_list = None
            
            if "is best with" in h_text: target_list = data["synergies"]
            elif "counters lane against" in h_text: target_list = data["lane_counters"]
            elif "gets countered in lane" in h_text: target_list = data["lane_countered_by"]
            elif "wins lane against" in h_text: target_list = data["lane_gold_advantage"]
            elif "loses lane against" in h_text: target_list = data["lane_gold_deficit"]
            elif "wins more against" in h_text: target_list = data["general_good_against"]
            elif "loses more against" in h_text: target_list = data["general_bad_against"]
            
            if target_list is not None:
                rows = box.find_all("tr")
                for row in rows:
                    name_span = row.find("span", class_="name")
                    if not name_span: continue
                    champ_name = name_span.text.strip()
                    score = extract_value_final(row)
                    target_list.append({"champion": champ_name, "score": score})
    
    return data

def main():
    load_mappings()

    if not os.path.exists(INPUT_FILE):
        print(f"❌ '{INPUT_FILE}' bulunamadı!")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        champions_to_scrape = json.load(f)
    
    full_database = []
    total = len(champions_to_scrape)
    
    print(f"🚀 {total} karakter taranacak. (Koruma Modu Aktif)")
    print("-" * 50)

    for i, champ in enumerate(champions_to_scrape, 1):
        print(f"[{i}/{total}] {champ['name']}...", end=" ", flush=True)
        
        try:
            champ_data = get_champion_full_data(champ, REGION)
            full_database.append(champ_data)
            
            wr = champ_data.get("general_win_rate", 0)
            
            if wr == 0.0:
                print("⚠️ (WR Çekilemedi - 403 olabilir)")
            else:
                print(f"✅ (WR: %{wr})")
            
        except Exception as e:
            print(f"❌ HATA: {e}")

        # --- GÜNCELLEME: Bekleme süresini artırdık ---
        # 403 hatası alıyorsan bu süreyi artırmak zorundasın.
        # Her karakterden sonra 2 ile 4 saniye arası bekleyecek.
        sleep_time = random.uniform(2.0, 4.0) 
        time.sleep(sleep_time)

    print("-" * 50)
    print(f"💾 Tüm veriler '{OUTPUT_FILE}' dosyasına kaydediliyor...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(full_database, f, indent=4, ensure_ascii=False)
    
    print("🎉 İŞLEM TAMAMLANDI!")

if __name__ == "__main__":
    main()
