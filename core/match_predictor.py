import json
import os
# Ana dizinden değil, modül olarak çağrıldığında çalışması için 'core.' ekliyoruz
from core.ai_recommendation_final import LoLDecisionEngine

class LoLMatchPredictor(LoLDecisionEngine):
    def __init__(self, data_file):
        # Üst sınıfın (LoLDecisionEngine) özelliklerini miras al
        super().__init__(data_file)

    def calculate_team_power(self, team_list):
        """
        Bir takımın kendi içindeki gücünü hesaplar.
        Kriterler: Ortalama WR + Hasar Dengesi + Sinerji
        """
        power_score = 0.0
        details = []
        
        total_wr = 0
        ap_score = 0
        ad_score = 0
        valid_champs = 0
        
        # 1. TEMEL GÜÇ VE HASAR PROFİLİ
        for name in team_list:
            if name == "Picking..." or name == "...": continue
            
            champ = self.champ_lookup.get(name.lower())
            if not champ: continue
            
            valid_champs += 1
            wr = champ.get('general_win_rate', 50.0)
            total_wr += wr
            
            # Hasar Profilini Topla (Yoksa varsayılan 5/5)
            dmg = champ.get('damage_profile', {"ap": 5, "ad": 5})
            ap_score += dmg['ap']
            ad_score += dmg['ad']

        if valid_champs == 0: return 5000.0, ["Veri Yok"]

        avg_wr = total_wr / valid_champs
        # Baz puan: Ortalama WR * 100 (Örn: %52 -> 5200 puan)
        power_score += avg_wr * 100 
        details.append(f"Ortalama WR: %{avg_wr:.1f}")

        # 2. HASAR DENGESİ CEZASI (COMPOSITION PENALTY)
        # Eğer takım %80'den fazla tek tip hasar vuruyorsa ceza kes.
        total_dmg = ap_score + ad_score
        if total_dmg > 0:
            ad_ratio = ad_score / total_dmg
            ap_ratio = ap_score / total_dmg
            
            penalty = 300 # Ceza Puanı
            
            if ad_ratio > 0.80:
                power_score -= penalty
                details.append(f"⚠️ Full AD Cezası (-{penalty})")
            elif ap_ratio > 0.80:
                power_score -= penalty
                details.append(f"⚠️ Full AP Cezası (-{penalty})")
            else:
                details.append("✅ Hasar Dengesi İyi")

        # 3. SİNERJİ BONUSU
        synergy_score = 0
        for i in range(len(team_list)):
            for j in range(i + 1, len(team_list)):
                c1_name = team_list[i]
                c2_name = team_list[j]
                
                if c1_name == "Picking..." or c2_name == "Picking...": continue
                
                c1 = self.champ_lookup.get(c1_name.lower())
                if c1:
                    s = self.get_list_score(c1.get('synergies', []), c2_name)
                    synergy_score += s
        
        # Sinerji puanını ekle (Ağırlık: 5)
        if synergy_score > 0:
            bonus = synergy_score * 5
            power_score += bonus
            if bonus > 50: details.append(f"Yüksek Sinerji (+{bonus:.0f})")

        return power_score, details

    def calculate_matchup_advantage(self, team_blue, team_red):
        """
        Mavi takımın Kırmızı takıma karşı koridor ve genel avantajını hesaplar.
        """
        advantage_score = 0.0
        matchup_details = []

        # 1. KORİDOR EŞLEŞMESİ (LANE MATCHUP)
        # Varsayım: Listeler Role Göre Sıralı (Top, Jungle, Mid, ADC, Sup)
        # 5v5 tamamlansa bile bazen eksik veri olabilir, min() ile güvenli döngü
        limit = min(len(team_blue), len(team_red))
        
        roles = ["Top", "Jungle", "Mid", "ADC", "Sup"]
        
        for i in range(limit):
            blue_champ = team_blue[i]
            red_champ = team_red[i]
            
            if blue_champ == "Picking..." or red_champ == "Picking...": continue
            
            c_data = self.champ_lookup.get(blue_champ.lower())
            if not c_data: continue

            # A. İstatistiksel Skor
            lane_adv = self.get_list_score(c_data.get('lane_counters', []), red_champ)
            lane_dis = self.get_list_score(c_data.get('lane_countered_by', []), red_champ)
            
            net_lane = lane_adv - lane_dis
            
            # B. Uzman Görüşü (Expert Insight) - OYUN DEĞİŞTİRİCİ
            expert = c_data.get('expert_insight', {})
            expert_bonus = 0
            
            # Ben onu eziyor muyum?
            if red_champ.lower() in [x.lower() for x in expert.get('easy_matchups', [])]:
                expert_bonus = 20.0 # İstatistiksel olarak 10 puana denk devasa bonus
                matchup_details.append(f"🔥 {blue_champ} > {red_champ} (Hard Counter)")
            
            # O beni eziyor mu?
            elif red_champ.lower() in [x.lower() for x in expert.get('hard_counters', [])]:
                expert_bonus = -20.0
                matchup_details.append(f"💀 {blue_champ} < {red_champ} (Ezilir)")

            # Toplam Koridor Puanı (İstatistik + Uzman)
            # Koridor ağırlığı: 20
            total_lane_point = (net_lane + expert_bonus) * 20
            advantage_score += total_lane_point

        # 2. GENEL KARŞITLIK (Herkes Herkese Karşı)
        general_score = 0
        for b_name in team_blue:
            if b_name == "Picking...": continue
            b_data = self.champ_lookup.get(b_name.lower())
            if not b_data: continue
            
            for r_name in team_red:
                if r_name == "Picking...": continue
                
                good = self.get_list_score(b_data.get('general_good_against', []), r_name)
                bad = self.get_list_score(b_data.get('general_bad_against', []), r_name)
                general_score += (good - bad)
        
        # Genel puan ağırlığı: 5
        advantage_score += general_score * 5
        
        return advantage_score, matchup_details

    def predict_match(self, team_blue, team_red):
        """
        İki takımı karşılaştırır, terminale analiz yazar ve yüzdeleri DÖNDÜRÜR.
        """
        # Sadece gerçek isimleri filtrele
        real_blue = [c for c in team_blue if c not in ["Picking...", "..."]]
        real_red = [c for c in team_red if c not in ["Picking...", "..."]]
        
        if not real_blue or not real_red:
            return 50, 50

        print(f"\n🔮 MAÇ TAHMİNİ: {len(real_blue)}v{len(real_red)}")
        print("-" * 40)

        # 1. Takım Güçleri
        blue_power, blue_details = self.calculate_team_power(real_blue)
        red_power, red_details = self.calculate_team_power(real_red)

        # 2. Karşılaşma Avantajı (Pozitifse Mavi, Negatifse Kırmızı önde)
        matchup_advantage, matchup_details = self.calculate_matchup_advantage(real_blue, real_red)

        # 3. Skorları Birleştir
        # Avantajı ikiye bölüp birine ekleyip diğerinden çıkarıyoruz ki fark açılsın
        final_blue_score = blue_power + (matchup_advantage / 2)
        final_red_score = red_power - (matchup_advantage / 2)

        # 4. Yüzdeye Çevir
        total_points = final_blue_score + final_red_score
        
        if total_points == 0: 
            blue_win_rate = 50.0
        else:
            blue_win_rate = (final_blue_score / total_points) * 100
            
        red_win_rate = 100 - blue_win_rate

        # --- DETAYLI ANALİZ ÇIKTISI (Log Kutusuna Gider) ---
        print(f"🔵 Mavi Takım (%{blue_win_rate:.1f}): {', '.join(blue_details)}")
        print(f"🔴 Kırmızı Takım (%{red_win_rate:.1f}): {', '.join(red_details)}")
        
        if matchup_details:
            print(f"⚔️ Kritik Eşleşmeler:")
            for det in matchup_details[:4]: 
                print(f"   ➤ {det}")
        
        print(f"Sonuç: {'Mavi' if blue_win_rate > 50 else 'Kırmızı'} Takım Avantajlı")
        print("="*40)
        
        # --- GUI İÇİN RETURN ---
        return blue_win_rate, red_win_rate

# --- TEST ALANI ---
if __name__ == "__main__":
    # Test için ana dizinde çalışıyormuş gibi yol verelim
    try:
        predictor = LoLMatchPredictor("../tum_sampiyonlar_verisi_full.json")
    except:
        # Core içinden çalıştırılıyorsa
        predictor = LoLMatchPredictor("tum_sampiyonlar_verisi_full.json")
    
    TEAM_BLUE = ["Malphite", "Amumu", "Yasuo", "Kai'Sa", "Nautilus"]
    TEAM_RED = ["Jayce", "Kha'Zix", "Zed", "Caitlyn", "Lux"]
    
    b, r = predictor.predict_match(TEAM_BLUE, TEAM_RED)
    print(f"Return Değerleri: Mavi={b}, Kırmızı={r}")
