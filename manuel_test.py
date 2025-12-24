import sys
import os
import json

# Terminal renkleri (Linux sevdiğini bildiğim için :))
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Modül yollarını ayarla
sys.path.append(os.getcwd())

try:
    from core.ai_recommendation_final import LoLDecisionEngine
    from core.match_predictor import LoLMatchPredictor
except ImportError as e:
    print(f"{Colors.FAIL}Hata: 'core' modülü bulunamadı. Bu scripti main.py ile aynı dizinde çalıştırdığından emin ol.{Colors.ENDC}")
    print(e)
    sys.exit(1)

def print_separator():
    print(f"{Colors.CYAN}{'-' * 60}{Colors.ENDC}")

def get_list_input(prompt):
    """Kullanıcıdan virgülle ayrılmış liste alır."""
    val = input(f"{Colors.BOLD}{prompt} (Virgülle ayır): {Colors.ENDC}")
    if not val.strip():
        return []
    # Boşlukları temizle ve listeye çevir
    return [x.strip() for x in val.split(',') if x.strip()]

def main():
    print(f"{Colors.HEADER}League of Legends Smart Coach - CLI Test Modu{Colors.ENDC}")
    print_separator()

    # Veri yolu kontrolü
    data_path = os.path.join("data", "tum_sampiyonlar_verisi_full.json")
    if not os.path.exists(data_path):
        print(f"{Colors.FAIL}Hata: {data_path} dosyası bulunamadı!{Colors.ENDC}")
        return

    print(f"{Colors.BLUE}AI Motorları Yükleniyor...{Colors.ENDC}")
    try:
        ai_engine = LoLDecisionEngine(data_path)
        predictor = LoLMatchPredictor(data_path)
        print(f"{Colors.GREEN}Modüller Hazır!{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}Yükleme Hatası: {e}{Colors.ENDC}")
        return

    while True:
        print_separator()
        print("SENARYO OLUŞTUR:")
        
        # 1. Girdileri Al
        my_role = input(f"{Colors.BOLD}Senin Rolün (Top/Jungle/Mid/ADC/Sup): {Colors.ENDC}").strip()
        enemy_laner = input(f"{Colors.BOLD}Koridor Rakibin (Örn: Yasuo): {Colors.ENDC}").strip()
        
        print(f"\n{Colors.WARNING}Not: Takımları boş geçebilirsin, sadece 1v1 analizi yapar.{Colors.ENDC}")
        my_team = get_list_input("Senin Takımın (Sen hariç)")
        enemy_team = get_list_input("Rakip Takım (Rakibin dahil)")

        # Eğer enemy_laner girildiyse ama enemy_team boşsa, rakibi takıma ekle
        if enemy_laner and enemy_laner not in enemy_team:
            enemy_team.append(enemy_laner)

        print_separator()
        print(f"{Colors.HEADER}>>> ANALİZ BAŞLIYOR...{Colors.ENDC}")

        # --- 1. ŞAMPİYON ÖNERİSİ (AI RECOMMENDATION) ---
        print(f"\n{Colors.CYAN}[1] Şampiyon Önerileri ({my_role} vs {enemy_laner}):{Colors.ENDC}")
        
        try:
            suggestions = ai_engine.calculate_score(my_role, enemy_laner, my_team, enemy_team)
            
            if not suggestions:
                print(f"{Colors.FAIL}Uygun öneri bulunamadı.{Colors.ENDC}")
            else:
                for i, rec in enumerate(suggestions[:5], 1): # İlk 5 öneri
                    score = rec['score']
                    color = Colors.GREEN if score > 150 else (Colors.WARNING if score > 50 else Colors.ENDC)
                    
                    print(f"\n{Colors.BOLD}{i}. {rec['name']} {Colors.ENDC}({rec['class']})")
                    print(f"   Puan: {color}{score}{Colors.ENDC} | WR: %{rec['wr']}")
                    print(f"   {Colors.BLUE}Analiz:{Colors.ENDC} {rec['reasons']}")
        except Exception as e:
            print(f"{Colors.FAIL}Öneri Hatası: {e}{Colors.ENDC}")

        # --- 2. MAÇ TAHMİNİ (MATCH PREDICTOR) ---
        # Tahmin için benim takımıma (varsayılan olarak önerilen ilk şampiyonu ekleyelim veya boş bırakalım)
        # Kullanıcıya soralım:
        print_separator()
        selected_champ = input(f"{Colors.BOLD}Maç tahmini için hangi şampiyonu seçiyorsun? (Boş geçersen tahmin yapılmaz): {Colors.ENDC}").strip()
        
        if selected_champ:
            full_my_team = my_team + [selected_champ]
            
            print(f"\n{Colors.CYAN}[2] Maç Tahmini ({len(full_my_team)}v{len(enemy_team)}):{Colors.ENDC}")
            try:
                # Predictor zaten print aldığı için direkt çağırıyoruz, ayrıca değerleri döndürür
                blue_wr, red_wr = predictor.predict_match(full_my_team, enemy_team)
                
                # Görsel Çubuk
                bar_length = 40
                blue_chars = int((blue_wr / 100) * bar_length)
                red_chars = bar_length - blue_chars
                
                print("\nKazanma İhtimali:")
                print(f"{Colors.BLUE}{'█' * blue_chars}{Colors.FAIL}{'█' * red_chars}{Colors.ENDC}")
                print(f"{Colors.BLUE}%{blue_wr:.1f} (Biz){Colors.ENDC} vs {Colors.FAIL}%{red_wr:.1f} (Rakip){Colors.ENDC}")
                
            except Exception as e:
                print(f"{Colors.FAIL}Tahmin Hatası: {e}{Colors.ENDC}")

        # Devam mı?
        print_separator()
        cont = input("Yeni analiz yapılsın mı? (e/h): ").lower()
        if cont != 'e':
            print("Çıkış yapılıyor...")
            break

if __name__ == "__main__":
    main()
