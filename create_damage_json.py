import json

# 1. TEMEL LİSTE (Senin verdiğin kategoriler)
# Önce varsayılan puanları atayacağız, sonra özel karakterleri düzelteceğiz.
base_categories = {
    "AP_HEAVY": [ # 9-10 AP Puanı
        "Ahri", "Anivia", "Annie", "Aurelion Sol", "Aurora", "Azir", "Brand", 
        "Cassiopeia", "Fiddlesticks", "Heimerdinger", "Hwei", "Karthus", 
        "Kennen", "LeBlanc", "Lissandra", "Lux", "Malzahar", "Mel", "Morgana", 
        "Neeko", "Orianna", "Ryze", "Seraphine", "Swain", "Syndra", "Taliyah", 
        "Twisted Fate", "Veigar", "Vel'Koz", "Vex", "Viktor", "Vladimir", 
        "Xerath", "Ziggs", "Zoe", "Zyra", "Elise", "Evelynn", "Fiddlesticks", 
        "Taliyah", "Karthus", "Nidalee", "Ekko", "Diana", "Fizz", "Gwen", 
        "Singed", "Rumble", "Sylas", "Zilean", "Sona", "Soraka", "Janna", 
        "Lulu", "Nami", "Yuumi", "Mililo", "Karma", "Ivern", "Bard", "Renata Glasc"
    ],
    
    "AD_HEAVY": [ # 9-10 AD Puanı
        "Zed", "Talon", "Qiyana", "Naafiri", "Kha'Zix", "Rengar", "Pyke", 
        "Blue Kayn", "Nocturne", "Draven", "Caitlyn", "Jhin", "Jinx", "Samira", 
        "Lucian", "Tristana", "Sivir", "Xayah", "Aphelios", "Miss Fortune", 
        "Kalista", "Graves", "Kindred", "Darius", "Garen", "Riven", "Fiora", 
        "Camille", "Renekton", "Kled", "Aatrox", "Olaf", "Pantheon", "Jayce", 
        "Yorick", "Urgot", "Illaoi", "Tryndamere", "Trundle", "Lee Sin", 
        "Vi", "Viego", "Xin Zhao", "Jarvan IV", "Rek'Sai", "Bel'Veth", "Briar", 
        "Master Yi", "Hecarim", "Wukong", "Red Kayn", "Zaahen", "Ambessa"
    ],
    
    "TANK_MAGIC": [ # Tanklar genelde büyü hasarı vurur (Sunfire + Yetenekler) -> 7 AP / 3 AD
        "Amumu", "Maokai", "Malphite", "Zac", "Sejuani", "Nunu & Willump", 
        "Rammus", "Cho'Gath", "Ornn", "Tahm Kench", "Shen", "Nautilus", 
        "Leona", "Braum", "Alistar", "Taric", "Rell", "Blitzcrank", "Skarner", "Galio", "Gragas"
    ],

    "TANK_PHYSICAL": [ # Fiziksel vuran tanklar -> 3 AP / 7 AD
        "Sion", "K'Sante", "Dr. Mundo", "Poppy", "Sett"
    ]
}

# 2. ÖZEL AYARLAR (HYBRID & İSTİSNALAR)
# Buradaki değerler yukarıdaki varsayılanları ezer.
# Format: "İsim": {"ap": X, "ad": Y} (Toplamı 10 olmak zorunda değil, etkiyi gösterir)
overrides = {
    # --- HYBRID NİŞANCILAR ---
    "Kai'Sa": {"ap": 6, "ad": 6},     # Hem AP hem AD vurur
    "Kog'Maw": {"ap": 7, "ad": 4},    # W'su büyü hasarı vurur
    "Ezreal": {"ap": 4, "ad": 8},     # Genelde AD ama yetenekleri büyü vurur
    "Varus": {"ap": 5, "ad": 7},      # W pasifi büyü hasarıdır
    "Corki": {"ap": 2, "ad": 9},      # (GÜNCEL YAMA: Artık Fiziksel ağırlıklı)
    "Zeri": {"ap": 3, "ad": 8},       # Pasif ve R büyü hasarı
    "Twitch": {"ap": 2, "ad": 9},     # Zehri gerçek hasar, E fiziksel (AP Twitch hariç)
    "Smolder": {"ap": 3, "ad": 8},    # Stackleri büyü/gerçek hasar ekler
    
    # --- HYBRID DÖVÜŞÇÜLER ---
    "Jax": {"ap": 4, "ad": 7},        # W ve R pasifi büyü vurur
    "Warwick": {"ap": 7, "ad": 4},    # Q ve R büyü hasarı vurur (AD kassa bile)
    "Volibear": {"ap": 6, "ad": 5},   # Pasif, E ve R büyü hasarı
    "Udyr": {"ap": 6, "ad": 5},       # R (Phoneix) büyü, Q fiziksel
    "Shyvana": {"ap": 7, "ad": 4},    # E ve W büyü hasarı (AD bruiser olsa bile)
    "Irelia": {"ap": 2, "ad": 9},     # Pasifi büyü vurur ama az
    "Yone": {"ap": 2, "ad": 9},       # Pasifi ve W'su büyü/fiziksel karışık
    "Yasuo": {"ap": 0, "ad": 10},     # Full AD
    "Nasus": {"ap": 2, "ad": 8},      # E ve R büyü vurur
    "Akali": {"ap": 9, "ad": 2},      # Hybrid build yapılabilir ama genelde AP
    "Katarina": {"ap": 8, "ad": 4},   # On-hit buildleri yüzünden AD de vurabilir
    "Shaco": {"ap": 5, "ad": 6},      # AD ve AP buildleri çok değişken
    "Teemo": {"ap": 9, "ad": 2},      # On-hit
    "Kayle": {"ap": 7, "ad": 5},      # Late game dalgaları büyü vurur
    "Twisted Fate": {"ap": 9, "ad": 2}, # AD build yapılabilir
    "Thresh": {"ap": 6, "ad": 4}      # E pasifi ve yetenekler büyü
}

def generate_damage_data():
    final_data = {}
    
    # 1. Varsayılanları Ata
    for champ in base_categories["AP_HEAVY"]:
        final_data[champ] = {"ap": 10, "ad": 0}
        
    for champ in base_categories["AD_HEAVY"]:
        final_data[champ] = {"ap": 0, "ad": 10}
        
    for champ in base_categories["TANK_MAGIC"]:
        final_data[champ] = {"ap": 7, "ad": 3}
        
    for champ in base_categories["TANK_PHYSICAL"]:
        final_data[champ] = {"ap": 2, "ad": 8}

    # 2. Özel Ayarları İşle (Varsayılanların üzerine yazar)
    for name, scores in overrides.items():
        final_data[name] = scores

    # 3. Sıralama ve Kayıt
    sorted_data = dict(sorted(final_data.items()))
    
    filename = "champion_damage_scores.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, indent=4, ensure_ascii=False)
        
    print(f"✅ '{filename}' başarıyla oluşturuldu.")
    print(f"📊 Toplam {len(final_data)} şampiyon sınıflandırıldı.")

if __name__ == "__main__":
    generate_damage_data()
