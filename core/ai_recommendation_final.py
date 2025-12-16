import json
import os

class LoLDecisionEngine:
    def __init__(self, data_file):
        self.data_file = data_file
        self.data = self.load_data()
        
        # Hızlı erişim için isimden veriye giden sözlük
        self.champ_lookup = {c['name'].lower(): c for c in self.data}

        # --- SINIFSAL ÜSTÜNLÜK TABLOSU (Senin Tanımladığın 6 Sınıf) ---
        # Sol Taraf (Anahtar) -> Sağ Taraftaki Listeyi YENER.
        self.class_counters = {
            "Assassin": ["Immobile_Mage", "ADC", "Support"], 
            "Tank": ["Assassin"],             
            "Skirmisher": ["Tank", "Assassin"],        
            "Immobile_Mage": ["ADC", "Support"],            
            "ADC": ["Tank"],
            "Support": [] # Destekler genelde koruyucudur, sınıf counterlamaz.
        }

    def load_data(self):
        if not os.path.exists(self.data_file):
            print(f"❌ HATA: '{self.data_file}' bulunamadı!")
            return []
        with open(self.data_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_list_score(self, list_data, target_name):
        """Listelerden (Synergy, Counter) puan çeker."""
        if not list_data: return 0.0
        for item in list_data:
            if item['champion'].lower() == target_name.lower():
                return float(item['score'])
        return 0.0

    def get_class_interaction(self, my_class, enemy_class):
        """Sınıf avantajını hesaplar."""
        if my_class == "Unknown" or enemy_class == "Unknown": return 0.0
        
        # Ben onu yener miyim?
        if my_class in self.class_counters and enemy_class in self.class_counters[my_class]:
            return 1.0 
        # O beni yener mi?
        if enemy_class in self.class_counters and my_class in self.class_counters[enemy_class]:
            return -1.0
        return 0.0

    def analyze_team_damage(self, ally_team):
        """Takımın AD ve AP puanlarını toplar, eksiği belirler."""
        total_ap = 0
        total_ad = 0
        
        for ally in ally_team:
            champ = self.champ_lookup.get(ally.lower())
            if champ:
                # Veri setinde damage_profile yoksa varsayılan 5/5 al
                dmg = champ.get('damage_profile', {"ap": 5, "ad": 5})
                total_ap += dmg['ap']
                total_ad += dmg['ad']
        
        # Takım dengesini belirle
        # Eğer AD puanı, AP puanından 15 fazlaysa -> Bize AP lazım
        needed = "Balanced"
        if total_ad > total_ap + 10: needed = "AP"
        elif total_ap > total_ad + 10: needed = "AD"
        
        return needed, total_ap, total_ad

    def calculate_score(self, my_role, enemy_laner=None, ally_team=[], enemy_team=[]):
        recommendations = []

        # ==============================================================================
        # ⚙️ AĞIRLIK AYARLARI (SENİN İSTEDİĞİN DÜZEN + YORUMLAR)
        # ==============================================================================
        
        # 1. TEMEL İSTATİSTİKLER
        # Win Rate çok önemli ama tek başına karar verdirmez.
        W_GENEL_WR          = 80.0  
        
        # 2. TAKIM UYUMU
        # Sinerji iyidir ama karşıda "Hard Counter" varsa sinerji kurtarmaz.
        W_SINERJI           = 5.0   
        
        # 3. KORİDOR (LANE) İSTATİSTİKLERİ
        # İstatistiksel olarak rakibi yenmek.
        W_LANE_ADVANTAGE    = 15.0  
        W_LANE_DISADVANTAGE = 20.0  
        
        # 4. ALTIN FARKI (100'e bölündüğü için katsayılar düşük görünebilir ama etkilidir)
        W_GOLD_ADV          = 5.0   
        W_GOLD_DEF          = 6.0   

        # 5. GENEL MAÇ (TAKIM SAVAŞI)
        W_GEN_GOOD_VS       = 8.0   
        W_GEN_BAD_VS        = 10.0  

        # 6. UZMAN GÖRÜŞÜ (OYUNU DEĞİŞTİREN FAKTÖR)
        # Bu puanlar çok yüksek çünkü "Mekanik Counter" her istatistiği yener.
        W_EXPERT_HARD_CTR   = 100.0  # Rakibi kesin yener
        W_EXPERT_COUNTERED  = 200.0 # Rakibe kesin yenilir (ASLA SEÇME)
        
        # 7. SINIF AVANTAJI
        W_CLASS_ADVANTAGE   = 40.0   

        # 8. HASAR İHTİYACI (YENİ)
        # Takım Full AD ise, AP şampiyona verilecek puan (Hasar puanı * bu katsayı)
        W_DMG_NEED          = 15.0   

        # ==============================================================================

        # Takım Analizi
        needed_dmg, t_ap, t_ad = self.analyze_team_damage(ally_team)
        
        print(f"🤖 Analiz Başladı | Rol: {my_role} | Rakip: {enemy_laner}")
        print(f"📊 Takım Hasarı: AP:{t_ap} - AD:{t_ad} => İhtiyaç: {needed_dmg}")
        print("-" * 60)

        # Rakip Sınıfı
        enemy_class = "Unknown"
        if enemy_laner:
            c = self.champ_lookup.get(enemy_laner.lower())
            if c: enemy_class = c.get('class', 'Unknown')

        # --- ŞAMPİYONLARI TARA ---
        for champ in self.data:
            # 1. Rol Filtresi
            if my_role.lower() not in champ['role'].lower(): continue

            name = champ['name']
            my_class = champ.get('class', 'Unknown')
            dmg_profile = champ.get('damage_profile', {"ap": 5, "ad": 5})
            
            total_score = 0.0
            reasons = [] 

            # --- A. GENEL WIN RATE ---
            wr = champ.get('general_win_rate', 0)
            if wr > 0:
                score = (wr - 50.0) * W_GENEL_WR
                total_score += score
            
            # --- B. HASAR İHTİYACI (Takım Dengesi) ---
            if needed_dmg == "AP":
                bonus = dmg_profile['ap'] * W_DMG_NEED
                total_score += bonus
                if dmg_profile['ap'] >= 7: reasons.append(f"⚖️ Takım AP istiyor (+{bonus:.0f})")
            
            elif needed_dmg == "AD":
                bonus = dmg_profile['ad'] * W_DMG_NEED
                total_score += bonus
                if dmg_profile['ad'] >= 7: reasons.append(f"⚖️ Takım AD istiyor (+{bonus:.0f})")

            # --- C. TAKIM SİNERJİSİ ---
            for ally in ally_team:
                syn = self.get_list_score(champ.get('synergies', []), ally)
                if syn > 0:
                    total_score += syn * W_SINERJI

            # --- D. GENEL RAKİP ANALİZİ ---
            for enemy in enemy_team:
                if enemy == enemy_laner: continue
                good = self.get_list_score(champ.get('general_good_against', []), enemy)
                bad = self.get_list_score(champ.get('general_bad_against', []), enemy)
                if good > 0: total_score += good * W_GEN_GOOD_VS
                if bad > 0: total_score -= bad * W_GEN_BAD_VS

            # --- E. KORİDOR RAKİBİ (EN ÖNEMLİ KISIM) ---
            if enemy_laner:
                expert = champ.get('expert_insight', {})
                expert_advantage = False
                expert_disadvantage = False

                # 1. Uzman Görüşü
                easy_matchups = [c.lower() for c in expert.get('easy_matchups', [])]
                if enemy_laner.lower() in easy_matchups:
                    total_score += W_EXPERT_HARD_CTR
                    reasons.append(f"🔥 UZMAN: {enemy_laner} yok edilir!")
                    expert_advantage = True
                
                hard_counters = [c.lower() for c in expert.get('hard_counters', [])]
                if enemy_laner.lower() in hard_counters:
                    total_score -= W_EXPERT_COUNTERED
                    reasons.append(f"💀 UZMAN: {enemy_laner} seni ezer!")
                    expert_disadvantage = True

                # 2. İstatistiksel Veri (Uzman "Yenilirsin" demediyse bak)
                if not expert_disadvantage:
                    lane_adv = self.get_list_score(champ.get('lane_counters', []), enemy_laner)
                    lane_dis = self.get_list_score(champ.get('lane_countered_by', []), enemy_laner)
                    
                    # Uzman "Yeneriz" dediyse istatistiksel ezilmeyi görmezden gel
                    if expert_advantage and lane_dis > 0: lane_dis = 0

                    if lane_adv > 0: total_score += lane_adv * W_LANE_ADVANTAGE
                    if lane_dis > 0: 
                        score = lane_dis * W_LANE_DISADVANTAGE
                        total_score -= score
                        reasons.append(f"Stat-Ezilir (-{score:.0f})")

                    # Gold Farkları
                    g_adv = self.get_list_score(champ.get('lane_gold_advantage', []), enemy_laner)
                    g_def = self.get_list_score(champ.get('lane_gold_deficit', []), enemy_laner)
                    
                    if g_adv > 0: total_score += (g_adv / 100.0) * W_GOLD_ADV
                    if g_def > 0: total_score -= (g_def / 100.0) * W_GOLD_DEF

                # 3. Sınıf Avantajı (Taş-Kağıt-Makas)
                if not expert_advantage and not expert_disadvantage:
                    class_int = self.get_class_interaction(my_class, enemy_class)
                    if class_int > 0:
                        total_score += W_CLASS_ADVANTAGE
                        reasons.append(f"Sınıf: {my_class} > {enemy_class}")
                    elif class_int < 0:
                        total_score -= W_CLASS_ADVANTAGE
                        # reasons.append(f"Sınıf: {my_class} < {enemy_class}")

            recommendations.append({
                "name": name,
                "class": my_class,
                "score": round(total_score, 1),
                "wr": wr,
                "reasons": reasons
            })

        # Puanı en yüksekten düşüğe sırala
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        return recommendations[:5]

if __name__ == "__main__":
    engine = LoLDecisionEngine("tum_sampiyonlar_verisi_full.json")
    
    # --- SENARYO ---
    # Sen: Mid (Son seçim)
    # Rakip: Katarina (Suikastçi)
    # Takımın: Full AD + Tank (Renekton, Sejuani, Ashe, Braum)
    # İhtiyaç: AP Hasarı + Katarina'yı durduracak biri (Hard CC)
    
    picks = engine.calculate_score(
        my_role="Mid", 
        enemy_laner="Katarina", 
        ally_team=["Renekton", "Sejuani", "Ashe", "Braum"], 
        enemy_team=["Darius", "Viego", "Samira", "Nautilus"]
    )
    
    print("\n🏆 YAPAY ZEKA TAVSİYELERİ:")
    for i, p in enumerate(picks, 1):
        print(f"{i}. {p['name']} ({p['class']})")
        print(f"   PUAN: {p['score']} | WR: %{p['wr']}")
        print(f"   NEDENLER: {', '.join(p['reasons'][:4])}") # İlk 4 nedeni yaz
        print("-" * 60)
