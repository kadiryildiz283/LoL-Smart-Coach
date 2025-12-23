import json
import os

class LoLDecisionEngine:
    def __init__(self, data_file):
        self.data_file = data_file
        self.data = self.load_data()
        self.champ_lookup = {c['name'].lower(): c for c in self.data}
        
        # AYARLARI YÜKLE
        self.config_path = os.path.join(os.path.dirname(data_file), "config.json")
        self.output_dir = os.path.join(os.path.dirname(data_file), "output")
        self.weights = self.load_config()

        # Sınıf Üstünlükleri
        self.class_counters = {
            "Assassin": ["Immobile_Mage", "ADC", "Support"], 
            "Tank": ["Assassin"],             
            "Skirmisher": ["Tank", "Assassin"],        
            "Immobile_Mage": ["ADC", "Support"],            
            "ADC": [],
            "Support": [] 
        }

        # ÇOKLU DİL DESTEĞİ
        self.role_keywords = {
            "top": ["top", "üst", "upper"],
            "jungle": ["jungle", "orman"],
            "mid": ["mid", "middle", "orta"],
            "ad carry": ["ad carry", "adc", "bottom", "alt", "nişancı", "bot"],
            "support": ["support", "utility", "destek"]
        }
        
        # ARCHETYPE HARİTALAMASI (Basitleştirilmiş)
        self.archetypes = {
            "Poke": ["jayce", "xerath", "lux", "vel'koz", "ziggs", "varus", "nidalee", "zoe", "caitlyn", "ezreal"],
            "Engage": ["malphite", "amumu", "leona", "nautilus", "zac", "sejuani", "ornn", "alistar", "rakan", "rell"],
            "Disengage": ["janna", "braum", "lulu", "milie", "taric", "zyra", "anivia", "gragas"],
            "Pick": ["blitzcrank", "thresh", "morgana", "elise", "pyke", "twisted fate"],
            "Siege": ["tristana", "ziggs", "caitlyn", "heimerdinger", "yorick"],
            "Hypercarry": ["jinx", "kog'maw", "vayne", "twitch", "kayle", "master yi", "kassadin"]
        }

    def load_data(self):
        if not os.path.exists(self.data_file):
            print(f"❌ HATA: '{self.data_file}' bulunamadı!")
            return []
        with open(self.data_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_config(self):
        """config.json dosyasından ağırlıkları çeker. Yoksa varsayılanı döner."""
        default_weights = {
            "W_GENEL_WR": 80.0, "W_SINERJI": 15.0, "W_LANE_ADVANTAGE": 15.0, "W_LANE_DISADVANTAGE": 20.0,
            "W_GOLD_ADV": 15.0, "W_GOLD_DEF": 16.0, "W_GEN_GOOD_VS": 18.0, "W_GEN_BAD_VS": 20.0,
            "W_EXPERT_HARD_CTR": 100.0, "W_EXPERT_COUNTERED": 250.0, "W_CLASS_ADVANTAGE": 40.0,
            "W_DMG_NEED": 15.0, "W_COMP_SYNERGY": 25.0
        }
        
        # Eğer config.json yoksa ai_config.json'a bak (Fallback)
        path = self.config_path
        if not os.path.exists(path):
             path = path.replace("config.json", "ai_config.json")

        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    cfg = json.load(f)
                    active = cfg.get("active_profile", "balanced")
                    return cfg["profiles"].get(active, default_weights)
            except Exception as e:
                print(f"Config Load Error: {e}")
                
        return default_weights



    def set_profile(self, profile_name):
        """Aktif oyun tarzını (profile) değiştirir ve ağırlıkları günceller."""
        print(f"🔄 AI Profili Değiştiriliyor: {profile_name}")
        default_weights = {
            "W_GENEL_WR": 80.0, "W_SINERJI": 15.0, "W_LANE_ADVANTAGE": 15.0, "W_LANE_DISADVANTAGE": 20.0,
            "W_GOLD_ADV": 15.0, "W_GOLD_DEF": 16.0, "W_GEN_GOOD_VS": 18.0, "W_GEN_BAD_VS": 20.0,
            "W_EXPERT_HARD_CTR": 100.0, "W_EXPERT_COUNTERED": 250.0, "W_CLASS_ADVANTAGE": 40.0,
            "W_DMG_NEED": 15.0, "W_COMP_SYNERGY": 25.0
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    cfg = json.load(f)
                    # Sadece hafızada güncelle, dosyaya yazmaya gerek yok (veya istenirse yazılabilir)
                    self.weights = cfg["profiles"].get(profile_name, default_weights)
                    print("✅ Yeni ağırlıklar yüklendi.")
            except Exception as e:
                print(f"❌ Profil Değiştirme Hatası: {e}")

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
        
        if my_class in self.class_counters and enemy_class in self.class_counters[my_class]:
            return 1.0 
        if enemy_class in self.class_counters and my_class in self.class_counters[enemy_class]:
            return -1.0
        return 0.0

    def analyze_team_damage(self, ally_team):
        """Takımın AD ve AP puanlarını toplar, eksiği belirler."""
        total_ap, total_ad = 0, 0
        
        for ally in ally_team:
            if ally in ["Picking...", "Unknown", "...", "None"]: continue
            champ = self.champ_lookup.get(ally.lower())
            if champ:
                dmg = champ.get('damage_profile', {"ap": 5, "ad": 5})
                total_ap += dmg['ap']
                total_ad += dmg['ad']
        
        needed = "Balanced"
        if total_ad > total_ap + 15: needed = "AP"
        elif total_ap > total_ad + 15: needed = "AD"
        return needed

    def analyze_composition(self, ally_team):
        """Takımın kompozisyon tipini (Archetype) belirler."""
        team_archetypes = {}
        
        for ally in ally_team:
            if ally in ["Picking...", "Unknown", "...", "None"]: continue
            ally_lower = ally.lower()
            
            for arch, champs in self.archetypes.items():
                if ally_lower in champs:
                    team_archetypes[arch] = team_archetypes.get(arch, 0) + 1
        return team_archetypes

    def check_role_match(self, target_role, champ_role_text):
        """Şampiyon rolünü TR/EN kelimelerle eşleştirir."""
        keywords = self.role_keywords.get(target_role, [target_role])
        champ_role_lower = champ_role_text.lower()
        
        for kw in keywords:
            if kw in champ_role_lower:
                return True
        return False

    def generate_persuasive_narrative(self, name, positives, negatives, situational):
        """Puan ve sebeplere göre insani, ikna edici bir metin oluşturur."""
        import random
        
        # Giriş Cümlesi (Hook)
        openers = [
            f"🚀 **Hemen Kilitle:** {name} şu anki oyun için mükemmel bir tercih.",
            f"💎 **Gizli Cevher:** {name} bu kompozisyonda parlayacak.",
            f"🔥 **Taşıyıcı Potansiyeli:** {name} ile oyunu domine edebilirsin.",
            f"🛡️ **Güvenli Liman:** Riski en aza indirmek istiyorsan {name} al.",
            f"⚡ **Şok Etkisi:** Rakip takım {name} seçimine hazırlıksız yakalanacak."
        ]
        
        # Bağlaçlar
        connectors = ["Ayrıca,", "Bunun yanı sıra,", "Üstelik,", "En önemlisi,"]
        
        text_parts = []
        
        # 1. Başlık
        text_parts.append(random.choice(openers))
        
        # 2. Pozitif Sebepler (En önemli 2 tanesini seç)
        if positives:
            p_text = f"Çünkü {positives[0]}."
            if len(positives) > 1:
                p_text += f" {random.choice(connectors)} {positives[1]}."
            text_parts.append(p_text)
            
        # 3. Durumsal/Durum Analizi
        if situational:
             text_parts.append(f"💡 *Stratejik Not:* {situational[0]}")
             
        # 4. Negatif Uyarı (Varsa yumuşatarak söyle)
        if negatives:
            text_parts.append(f"⚠️ *Dikkat:* {negatives[0]}, ama yeteneğinle bunu aşabilirsin.")
            
        return " ".join(text_parts)

    def calculate_score(self, my_role, enemy_laner=None, ally_team=[], enemy_team=[]):
        recommendations = []
        W = self.weights # Kısa kullanım için

        # ROL EŞLEŞTİRME
        client_role_map = {
            "adc": "ad carry", "bottom": "ad carry", "bot": "ad carry",
            "support": "support", "utility": "support", "destek": "support",
            "mid": "mid", "middle": "mid", "orta": "mid",
            "jungle": "jungle", "orman": "jungle",
            "top": "top", "üst": "top",
            "unknown": "mid", "belirsiz": "mid", "none": "mid", "": "mid"
        }
        target_role = client_role_map.get(str(my_role).lower(), "mid")

        needed_dmg = self.analyze_team_damage(ally_team)
        team_archs = self.analyze_composition(ally_team)
        
        if enemy_laner and enemy_laner not in ["Picking...", "Unknown"]:
            c = self.champ_lookup.get(enemy_laner.lower())
            if c: enemy_class = c.get('class', 'Unknown')


        for champ in self.data:
            if not self.check_role_match(target_role, champ['role']): 
                continue

            name = champ['name']
            name_lower = name.lower()
            my_class = champ.get('class', 'Unknown')
            dmg_profile = champ.get('damage_profile', {"ap": 5, "ad": 5})
            
            total_score = 0.0
            
            # Narrative Data Collection
            positives = []
            negatives = []
            situational = []

            # A. GENEL WIN RATE
            wr = champ.get('general_win_rate', 0)
            if wr > 0:
                score = (wr - 50.0) * W["W_GENEL_WR"]
                total_score += score
                if wr > 52.0: positives.append(f"genel kazanma oranı çok yüksek (%{wr})")
            
            # B. HASAR İHTİYACI
            if needed_dmg == "AP":
                bonus = dmg_profile['ap'] * W["W_DMG_NEED"]
                total_score += bonus
                if dmg_profile['ap'] >= 7: positives.append("takımın AP hasarına ihtiyacı var ve bunu karşılıyor")
            elif needed_dmg == "AD":
                bonus = dmg_profile['ad'] * W["W_DMG_NEED"]
                total_score += bonus
                if dmg_profile['ad'] >= 7: positives.append("takımın AD hasar açığını kapatıyor")

            # C. TAKIM SİNERJİSİ & ARCHETYPE
            # 1. Birebir Sinerji
            for ally in ally_team:
                if ally in ["Picking...", "Unknown"]: continue
                syn = self.get_list_score(champ.get('synergies', []), ally)
                if syn > 0:
                    total_score += syn * W["W_SINERJI"]
                    if syn > 3.0: # Sadece güçlüleri söyle
                        positives.append(f"{ally} ile harika bir ikili oluyor")

            # 2. Archetype Bonusu (YENİ)
            for arch, count in team_archs.items():
                if count >= 1 and name_lower in self.archetypes[arch]:
                    # Eğer takımda zaten 1 Poke varsa, ve ben de Poke alıyorsam, Poke Kompu kuruyoruz.
                    total_score += W["W_COMP_SYNERGY"] * count
                    situational.append(f"Takımın '{arch}' stratejisine tam uyuyor.")

            # D. GENEL RAKİP ANALİZİ
            for enemy in enemy_team:
                if enemy in ["Picking...", "Unknown"] or enemy == enemy_laner: continue
                good = self.get_list_score(champ.get('general_good_against', []), enemy)
                bad = self.get_list_score(champ.get('general_bad_against', []), enemy)
                if good > 0: total_score += good * W["W_GEN_GOOD_VS"]
                if bad > 0: total_score -= bad * W["W_GEN_BAD_VS"]

            # E. KORİDOR RAKİBİ
            if enemy_laner and enemy_laner not in ["Picking...", "Unknown"]:
                expert = champ.get('expert_insight', {})
                expert_advantage = False
                expert_disadvantage = False

                # 1. Uzman Görüşü
                easy_matchups = [c.lower() for c in expert.get('easy_matchups', [])]
                if enemy_laner.lower() in easy_matchups:
                    total_score += W["W_EXPERT_HARD_CTR"]
                    positives.append(f"{enemy_laner} karşısında uzmanlar tarafından öneriliyor")
                    expert_advantage = True
                
                hard_counters = [c.lower() for c in expert.get('hard_counters', [])]
                if enemy_laner.lower() in hard_counters:
                    total_score -= W["W_EXPERT_COUNTERED"]
                    negatives.append(f"{enemy_laner} bu şampiyonu zorlayabilir")
                    expert_disadvantage = True
                


                # 2. İstatistiksel Veri
                if not expert_disadvantage:
                    lane_adv = self.get_list_score(champ.get('lane_counters', []), enemy_laner)
                    lane_dis = self.get_list_score(champ.get('lane_countered_by', []), enemy_laner)
                    
                    if expert_advantage and lane_dis > 0: lane_dis = 0

                    if lane_adv > 0: total_score += lane_adv * W["W_LANE_ADVANTAGE"]
                    if lane_dis > 0: 
                        score = lane_dis * W["W_LANE_DISADVANTAGE"]
                        total_score -= score
                        negatives.append("istatistiksel olarak koridorda geride kalıyor")

                    # Gold Farkları (Sadece skor, anlatıma girme)
                    g_adv = self.get_list_score(champ.get('lane_gold_advantage', []), enemy_laner)
                    g_def = self.get_list_score(champ.get('lane_gold_deficit', []), enemy_laner)
                    if g_adv > 0: total_score += (g_adv / 100.0) * W["W_GOLD_ADV"]
                    if g_def > 0: total_score -= (g_def / 100.0) * W["W_GOLD_DEF"]

                # 3. Sınıf Avantajı
                if not expert_advantage and not expert_disadvantage:
                    class_int = self.get_class_interaction(my_class, enemy_class)
                    if class_int > 0:
                        total_score += W["W_CLASS_ADVANTAGE"]
                        situational.append(f"Sınıf avantajın var ({my_class} > {enemy_class}).")
                    elif class_int < 0:
                        total_score -= W["W_CLASS_ADVANTAGE"]

            # Anlatıyı Oluştur
            narrative = self.generate_persuasive_narrative(name, positives, negatives, situational)

            recommendations.append({
                "name": name,
                "class": my_class,
                "score": round(total_score, 1),
                "wr": wr,
                "reasons": narrative # Artık liste değil, tam metin
            })

        recommendations.sort(key=lambda x: x['score'], reverse=True)
        return recommendations[:10]
