import json
import os

class LoLDecisionEngine:
    def __init__(self, data_file):
        self.data_file = data_file
        self.data = self.load_data()
        
        # Hızlı erişim için isimden veriye giden sözlük
        self.champ_lookup = {c['name'].lower(): c for c in self.data}

        # --- SINIFSAL ÜSTÜNLÜK TABLOSU (Taş-Kağıt-Makas) ---
        # Sol Taraf (Anahtar) -> Sağ Taraftaki Listeyi YENER.
        self.class_counters = {
            "Assassin": ["Immobile_Mage", "ADC", "Support"], 
            "Tank": ["Assassin"],             
            "Skirmisher": ["Tank", "Assassin"],        
            "Immobile_Mage": ["ADC", "Support"],            
            "ADC": ["Tank"],
            "Support": [] 
        }

        # --- ÇOKLU DİL DESTEĞİ (TR/EN) ---
        self.role_keywords = {
            "top": ["top", "üst", "upper"],
            "jungle": ["jungle", "orman"],
            "mid": ["mid", "middle", "orta"],
            "ad carry": ["ad carry", "adc", "bottom", "alt", "nişancı", "bot"],
            "support": ["support", "utility", "destek"]
        }

    def load_data(self):
        if not os.path.exists(self.data_file):
            print(f"❌ HATA: '{self.data_file}' bulunamadı!")
            return []
        with open(self.data_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_list_score(self, list_data, target_name):
        """Listelerden (Synergy, Counter) puan çeker."""
        if not list_data or not target_name: return 0.0
        for item in list_data:
            if item['champion'].lower() == target_name.lower():
                return float(item['score'])
        return 0.0

    def get_class_interaction(self, my_class, enemy_class):
        """Sınıf avantajını hesaplar (Taş-Kağıt-Makas)."""
        if my_class in ["Unknown", "None"] or enemy_class in ["Unknown", "None"]: return 0.0
        
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
            if ally in ["Picking...", "Unknown", "...", "None"]: continue

            champ = self.champ_lookup.get(ally.lower())
            if champ:
                # Veri setinde damage_profile yoksa varsayılan 5/5 al
                dmg = champ.get('damage_profile', {"ap": 5, "ad": 5})
                total_ap += dmg['ap']
                total_ad += dmg['ad']
        
        # Takım dengesini belirle
        needed = "Balanced"
        if total_ad > total_ap + 15: needed = "AP"
        elif total_ap > total_ad + 15: needed = "AD"
        
        return needed

    def check_role_match(self, target_role, champ_role_text):
        """
        Şampiyonun rol yazısı (örn: 'Orta Koridor') ile hedef rolü (örn: 'mid')
        karşılaştırır. Türkçe/İngilizce fark etmeksizin eşleştirir.
        """
        keywords = self.role_keywords.get(target_role, [target_role])
        champ_role_lower = champ_role_text.lower()
        
        # Keywords listesindeki HERHANGİ bir kelime şampiyon rolünde geçiyor mu?
        for kw in keywords:
            if kw in champ_role_lower:
                return True
        return False

    def calculate_score(self, my_role, enemy_laner=None, ally_team=[], enemy_team=[]):
        recommendations = []

        # ==============================================================================
        # ⚙️ AĞIRLIK AYARLARI (SENİN KALİTELİ DÜZENİN)
        # ==============================================================================
        W_GENEL_WR          = 80.0  # Kazanma Oranı en önemli faktör
        W_SINERJI           = 15.0   
        W_LANE_ADVANTAGE    = 15.0  
        W_LANE_DISADVANTAGE = 20.0  
        W_GOLD_ADV          = 15.0   
        W_GOLD_DEF          = 16.0   
        W_GEN_GOOD_VS       = 18.0   
        W_GEN_BAD_VS        = 20.0  
        W_EXPERT_HARD_CTR   = 100.0  # Uzman Bonusu
        W_EXPERT_COUNTERED  = 200.0  # Uzman Cezası
        W_CLASS_ADVANTAGE   = 40.0   
        W_DMG_NEED          = 15.0   # Takım ihtiyacı bonusu
        # ==============================================================================

        # --- 1. ROL EŞLEŞTİRME (ÇOKLU DİL DESTEĞİ) ---
        # Client'tan gelen rol isimlerini standartlaştır (adc -> ad carry)
        client_role_map = {
            "adc": "ad carry", "bottom": "ad carry", "bot": "ad carry",
            "support": "support", "utility": "support", "destek": "support",
            "mid": "mid", "middle": "mid", "orta": "mid",
            "jungle": "jungle", "orman": "jungle",
            "top": "top", "üst": "top",
            "unknown": "mid", "belirsiz": "mid", "none": "mid", "": "mid"
        }
        target_role = client_role_map.get(str(my_role).lower(), "mid")

        # Takım Analizi
        needed_dmg = self.analyze_team_damage(ally_team)
        
        # Rakip Sınıfı
        enemy_class = "Unknown"
        if enemy_laner and enemy_laner not in ["Picking...", "Unknown"]:
            c = self.champ_lookup.get(enemy_laner.lower())
            if c: enemy_class = c.get('class', 'Unknown')

        # --- ŞAMPİYONLARI TARA ---
        for champ in self.data:
            # AKILLI ROL FİLTRESİ (TR/EN Uyumlu)
            if not self.check_role_match(target_role, champ['role']): 
                continue

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
            
            # --- B. HASAR İHTİYACI ---
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
                if ally in ["Picking...", "Unknown"]: continue
                syn = self.get_list_score(champ.get('synergies', []), ally)
                if syn > 0:
                    total_score += syn * W_SINERJI

            # --- D. GENEL RAKİP ANALİZİ ---
            for enemy in enemy_team:
                if enemy in ["Picking...", "Unknown"] or enemy == enemy_laner: continue
                good = self.get_list_score(champ.get('general_good_against', []), enemy)
                bad = self.get_list_score(champ.get('general_bad_against', []), enemy)
                if good > 0: total_score += good * W_GEN_GOOD_VS
                if bad > 0: total_score -= bad * W_GEN_BAD_VS

            # --- E. KORİDOR RAKİBİ ---
            if enemy_laner and enemy_laner not in ["Picking...", "Unknown"]:
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

                # 2. İstatistiksel Veri
                if not expert_disadvantage:
                    lane_adv = self.get_list_score(champ.get('lane_counters', []), enemy_laner)
                    lane_dis = self.get_list_score(champ.get('lane_countered_by', []), enemy_laner)
                    
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

                # 3. Sınıf Avantajı
                if not expert_advantage and not expert_disadvantage:
                    class_int = self.get_class_interaction(my_class, enemy_class)
                    if class_int > 0:
                        total_score += W_CLASS_ADVANTAGE
                        reasons.append(f"Sınıf: {my_class} > {enemy_class}")
                    elif class_int < 0:
                        total_score -= W_CLASS_ADVANTAGE

            recommendations.append({
                "name": name,
                "class": my_class,
                "score": round(total_score, 1),
                "wr": wr,
                "reasons": reasons
            })

        # Puanı en yüksekten düşüğe sırala ve ilk 10'u döndür
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        return recommendations[:10]

# --- TEST ALANI ---
if __name__ == "__main__":
    test_path = "data/tum_sampiyonlar_verisi_full.json"
    if not os.path.exists(test_path):
        test_path = "../data/tum_sampiyonlar_verisi_full.json"

    engine = LoLDecisionEngine(test_path)
    
    print("\n🧪 Test: TR Rol Analizi...")
    # Client 'belirsiz' veya 'unknown' gönderirse 'Mid' analizi yapmalı
    picks = engine.calculate_score(
        my_role="belirsiz", 
        enemy_laner="Katarina", 
        ally_team=["Renekton", "Sejuani", "Ashe", "Braum"], 
        enemy_team=["Darius", "Viego", "Samira", "Nautilus"]
    )
    
    for i, p in enumerate(picks, 1):
        print(f"{i}. {p['name']} | Puan: {p['score']}")