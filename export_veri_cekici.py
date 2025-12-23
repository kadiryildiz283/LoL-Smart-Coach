import json
import os
import time
import random
import re
from bs4 import BeautifulSoup
from curl_cffi import requests

# --- AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
INPUT_FILE = os.path.join(DATA_DIR, "sampiyon_listesi.json")

# Bölge ayarı (Linkteki 'iron' kısmı için)
REGION = "iron"  # emerald, platinum, diamond, master vb. yapabilirsin

# URL Düzeltmeleri
URL_FIXES = {
    "nunu & willump": "nunu",
    "renata glasc": "renata",
    "dr. mundo": "drmundo",
    "bel'veth": "belveth",
    "kai'sa": "kaisa",
    "kha'zix": "khazix",
    "kog'maw": "kogmaw",
    "k'sante": "ksante",
    "leblanc": "leblanc",
    "lee sin": "leesin",
    "master yi": "masteryi",
    "miss fortune": "missfortune",
    "tahm kench": "tahmkench",
    "twisted fate": "twistedfate",
    "xin zhao": "xinzhao",
    "rek'sai": "reksai",
    "jarvan iv": "jarvaniv",
    "aurelion sol": "aurelionsol",
    "wukong": "monkeyking"
}

class LoLScraper:
    def __init__(self):
        # Gerçekçi tarayıcı taklidi
        self.session = requests.Session(impersonate="chrome120")
        
    def get_soup(self, url):
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    return BeautifulSoup(response.content, 'lxml')
                elif response.status_code == 429:
                    print(f"   🛑 429 Hata (IP Ban Riski). 60sn soğuma...")
                    time.sleep(60)
                else:
                    time.sleep(2)
            except Exception as e:
                print(f"   ⚠️ Bağlantı hatası: {e}")
                time.sleep(2)
        return None

bot = LoLScraper()

def sanitize_name(name):
    """İsmi URL formatına çevirir."""
    name_lower = name.lower()
    if name_lower in URL_FIXES:
        return URL_FIXES[name_lower]
    return name_lower.replace(" ", "").replace("'", "").replace(".", "")

def get_roles_set(role_str):
    """ 'Jungler, Top' -> {'jungler', 'top'} """
    if not role_str: return set()
    parts = role_str.split(',')
    return set(p.strip().lower() for p in parts)

def extract_win_rate_from_script(soup):
    """
    HTML içindeki JavaScript kodunu tarar.
    {data: 45.7, color: window['wggreen']...} yapısını arar.
    En güvenilir yöntem budur.
    """
    if not soup: return None

    # 1. Yöntem: Script içinden Regex ile çek (En Sağlamı)
    scripts = soup.find_all("script")
    for script in scripts:
        if script.string and "graphDD2" in script.string:
            # Regex: 'wggreen' rengi genellikle "Kazanma" rengidir.
            # {data: 52.2, color: window['wggreen']...}
            match = re.search(r"\{data:\s*(\d+\.?\d*),\s*color:\s*window\['wggreen'", script.string)
            if match:
                return float(match.group(1))

    # 2. Yöntem: Div içindeki metni kontrol et (Yedek)
    graph_div = soup.find("div", id="graphDD2")
    if graph_div:
        text = graph_div.get_text().strip()
        match = re.search(r"(\d+\.?\d*)%", text)
        if match:
            return float(match.group(1))
            
    return None

def normalize_scores(matchup_list):
    """
    Verileri 0.1 (En Zor) - 10.0 (En Kolay) arasına yayar.
    """
    if not matchup_list:
        return []

    # Sadece sayısal değerleri al
    wrs = [m['raw_wr'] for m in matchup_list]
    
    if not wrs: return []

    min_val = min(wrs) # Örn: 42.0
    max_val = max(wrs) # Örn: 58.0

    print(f"   📊 İstatistikler: Min WR: %{min_val} | Max WR: %{max_val}")

    # Eğer hepsi aynıysa (Tek veri varsa veya herkes eşitse)
    if max_val == min_val:
        for m in matchup_list:
            m['score'] = 5.0
            del m['raw_wr']
        return matchup_list

    # Normalizasyon Döngüsü
    for m in matchup_list:
        val = m['raw_wr']
        
        # Formül: 0.1 + (Değer - Min) / (Max - Min) * 9.9
        normalized = 0.1 + ((val - min_val) / (max_val - min_val)) * 9.9
        
        m['score'] = round(normalized, 2)
        del m['raw_wr'] # Ham veriyi sil, sadece puan kalsın

    # Puana göre sırala (Büyükten küçüğe - 10.0 en üste)
    matchup_list.sort(key=lambda x: x['score'], reverse=True)
    
    return matchup_list

def process_champion(hero, all_champions):
    hero_name = hero['name']
    hero_slug = sanitize_name(hero_name)
    hero_roles = get_roles_set(hero.get('role', ''))
    
    raw_matchups = []
    
    print(f"\n🚀 {hero_name} ({hero['role']}) işleniyor...")
    
    # Rakipleri Filtrele (Rol Kesişimi)
    target_enemies = []
    for c in all_champions:
        if c['name'] == hero_name: continue
        
        enemy_roles = get_roles_set(c.get('role', ''))
        
        # Kümelerin kesişimi var mı? (Ortak rol var mı?)
        if hero_roles.intersection(enemy_roles):
            target_enemies.append(c)

    total_targets = len(target_enemies)
    print(f"   🎯 Hedef: {total_targets} rakip ile kıyaslanacak (Rol filtreli).")

    for i, enemy in enumerate(target_enemies):
        enemy_name = enemy['name']
        enemy_slug = sanitize_name(enemy_name)
        
        # Kullanıcının verdiği örnek link yapısı:
        # https://www.leagueofgraphs.com/champions/tier-list/kaisa/vs-aurelionsol/iron
        url = f"https://www.leagueofgraphs.com/champions/tier-list/{hero_slug}/vs-{enemy_slug}/{REGION}"
        
        print(f"\r   [{i+1}/{total_targets}] vs {enemy_name:<15}", end="")
        
        soup = bot.get_soup(url)
        raw_wr = extract_win_rate_from_script(soup)
        
        if raw_wr is not None:
            raw_matchups.append({
                "enemy": enemy_name,
                "raw_wr": raw_wr
            })
        else:
            # Veri çekilemezse (Site yapısı değişmiş veya veri yoksa)
            # Pas geçiyoruz, listeye eklemiyoruz.
            pass
        
        # Her istek arası bekleme
        time.sleep(random.uniform(0.8, 1.5))
    
    print(f"\n   ✅ {hero_name}: {len(raw_matchups)} veri toplandı. Normalizasyon yapılıyor...")
    
    # Normalizasyon
    final_matchups = normalize_scores(raw_matchups)
    
    return {
        "name": hero_name,
        "role_desc": hero['role'],
        "matchups": final_matchups
    }

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        champion_list = json.load(f)
    
    # İsteğe bağlı: Listeyi isme göre sırala
    champion_list.sort(key=lambda x: x['name'])
    
    for champ in champion_list:
        champ_name = champ['name']
        output_path = os.path.join(OUTPUT_DIR, f"{champ_name}.json")
        
        # Resume (Kaldığı yerden devam etme) Özelliği
        if os.path.exists(output_path):
            print(f"⏩ {champ_name} zaten tamamlanmış, geçiliyor.")
            continue
            
        try:
            data = process_champion(champ, champion_list)
            
            # Kaydet
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                
            print("💾 Kaydedildi. Soğuma bekleniyor (3sn)...")
            time.sleep(3)
            
        except Exception as e:
            print(f"\n❌ Kritik Hata ({champ_name}): {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
