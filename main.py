import sys
import os
import asyncio
import traceback
import warnings
import json

# --- 1. AYARLAR ---
warnings.filterwarnings("ignore", category=DeprecationWarning)

import qdarktheme
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QListWidget, 
                             QListWidgetItem, QFrame, QMessageBox, QPlainTextEdit,
                             QProgressBar, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QTextCursor

# --- 2. DOSYA YOLU YARDIMCISI (EXE İÇİN KRİTİK) ---
def resource_path(relative_path):
    """ PyInstaller ile derlenmiş exe için doğru yolu bulur """
    try:
        # PyInstaller temp klasörü
        base_path = sys._MEIPASS
    except Exception:
        # Normal çalışma ortamı
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- 3. MODÜLLERİ GÜVENLİ YÜKLE ---
# Bu blok en üstte olmalı ki PyInstaller modülleri paketlesin.
try:
    # Core modüller (Yapay Zeka ve Bağlantı)
    from core.lcu_connector import LCUWorker
    from core.ai_recommendation_final import LoLDecisionEngine
    from core.match_predictor import LoLMatchPredictor
    
    # Script dosyaları (Veri Çekme ve Birleştirme)
    import veri_cekici_main
    import expert_parser
    import merge_expert_data
    import merge_damage_stats
    
    MODULES_LOADED = True
except ImportError as e:
    print(f"⚠️ Kritik Import Hatası: {e}")
    # Hata olsa bile değişkenleri None yap ki aşağıda 'not defined' hatası alma
    LCUWorker = None
    LoLDecisionEngine = None
    LoLMatchPredictor = None
    veri_cekici_main = None
    expert_parser = None
    merge_expert_data = None
    merge_damage_stats = None
    MODULES_LOADED = False

# --- 4. HATA YAKALAYICI (Kapanmayı Önler) ---
def global_exception_handler(exctype, value, tb):
    if "log_output" in str(value): return
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    sys.__stdout__.write(f"KRİTİK SİSTEM HATASI:\n{error_msg}\n")

sys.excepthook = global_exception_handler

# --- 5. LOG SİSTEMİ (Terminal -> Arayüz) ---
class EmittingStream(QObject):
    textWritten = pyqtSignal(str)
    def write(self, text):
        if text: self.textWritten.emit(str(text))
    def flush(self): pass

# --- 6. ARKAPLAN İŞÇİSİ (Veri Güncelleme) ---
class ScriptRunner(QThread):
    finished_task = pyqtSignal()
    def __init__(self, task_type):
        super().__init__()
        self.task_type = task_type

    def run(self):
        try:
            if self.task_type == "scrape_data":
                if veri_cekici_main:
                    print("⏳ İstatistikler Data Dragon ve Web'den çekiliyor..."); 
                    veri_cekici_main.main()
                else:
                    print("❌ HATA: 'veri_cekici_main' modülü bulunamadı.")
                    
            elif self.task_type == "merge_all":
                # Tüm veri setlerini (Expert, Damage, Classes) birleştir
                if expert_parser and merge_expert_data and merge_damage_stats:
                    print("ℹ️ Uzman verileri işleniyor..."); expert_parser.main()
                    print("ℹ️ Veritabanları birleştiriliyor..."); merge_expert_data.main()
                    print("ℹ️ Hasar profilleri ve Sınıflar ekleniyor..."); merge_damage_stats.main()
                    print("🎉 Veritabanı başarıyla oluşturuldu: tum_sampiyonlar_verisi_full.json")
                else:
                    print("❌ HATA: Birleştirme modülleri eksik.")
                    
        except Exception as e: 
            print(f"❌ İşlem Hatası: {str(e)}")
        self.finished_task.emit()

# --- 7. KART WIDGET (Şampiyon Görseli Yeri) ---
class ChampSlot(QFrame):
    def __init__(self, color_code):
        super().__init__()
        self.setStyleSheet(f"background-color: {color_code}; border-radius: 8px; border: 1px solid #444;")
        layout = QVBoxLayout(self); layout.setContentsMargins(5,5,5,5)
        self.lbl_name = QLabel("...")
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_name.setStyleSheet("color: #aaa; font-style: italic; font-size: 13px;")
        layout.addWidget(self.lbl_name)

    def set_champ(self, name):
        if name in ["Picking...", "Unknown", "...", "None", None]:
            self.lbl_name.setText("...")
            self.lbl_name.setStyleSheet("color: #aaa; font-style: italic;")
        else:
            self.lbl_name.setText(name)
            self.lbl_name.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")

# --- 8. ANA PENCERE ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL Smart Coach - Final Release")
        self.setGeometry(100, 100, 1280, 850)

        self.setup_ui()
        self.apply_styles()

        # Logları arayüze yönlendir
        self.terminal_stream = EmittingStream()
        self.terminal_stream.textWritten.connect(self.append_terminal_text)
        sys.stdout = self.terminal_stream
        sys.stderr = self.terminal_stream

        # Veri Yolu
        self.data_path = resource_path(os.path.join("data", "tum_sampiyonlar_verisi_full.json"))
        
        # Değişkenler
        self.ai_engine = None
        self.match_predictor = None
        self.lcu_thread = None
        self.current_role = "Unknown" 
        self.current_my_team = []
        self.current_enemy_team = []
        
        print("⚙️ Sistem başlatılıyor...")
        self.load_ai_modules()
        self.start_lcu()

    def load_ai_modules(self):
        """Yapay Zeka motorunu ve Tahminciyi yükler"""
        if os.path.exists(self.data_path):
            try:
                if LoLDecisionEngine:
                    self.ai_engine = LoLDecisionEngine(self.data_path)
                if LoLMatchPredictor:
                    self.match_predictor = LoLMatchPredictor(self.data_path)
                print(f"✅ Veritabanı başarıyla yüklendi.")
            except Exception as e: print(f"❌ Veritabanı Yükleme Hatası: {e}")
        else:
            print("⚠️ Veritabanı Bulunamadı! Lütfen önce 'Veritabanı Güncelle' sonra 'Merge Yap' butonlarını kullanın.")

    def start_lcu(self):
        """LCU Bağlantısını başlatır"""
        if LCUWorker is None:
            print("❌ LCU Modülü yüklenemediği için otomatik bağlantı devre dışı.")
            return
        try:
            self.lcu_thread = LCUWorker()
            self.lcu_thread.connection_status.connect(self.update_connection_status)
            self.lcu_thread.champ_select_update.connect(self.handle_champ_select) 
            self.lcu_thread.start()
        except Exception as e: print(f"❌ LCU Başlatılamadı: {e}")

    # --- GÜVENLİ SIFIRLAMA (Donma Yapmaz) ---
    def reset_ui_state(self):
        """
        Thread'i öldürmez, sadece arayüzü temizler.
        LCU bağlantısı arkada kopsa bile kendi kendine yeniden bağlanır.
        """
        print("\n🗑️ Arayüz Temizleniyor (Bağlantı korunuyor)...")
        
        self.current_role = "Unknown"
        self.current_my_team = []
        self.current_enemy_team = []
        
        self.lbl_role.setText("ROL: BELİRSİZ")
        self.suggestion_list.clear()
        self.prediction_frame.setVisible(False)
        
        # Sinyalleri durdurup temizle
        self.combo_enemy_laner.blockSignals(True)
        self.combo_enemy_laner.clear()
        self.combo_enemy_laner.addItem("Rakip Seçiniz")
        self.combo_enemy_laner.blockSignals(False)
        
        for slot in self.blue_slots + self.red_slots:
            slot.set_champ("...")
            
        print("✅ Arayüz Sıfırlandı.")

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # --- ÜST HEADER ---
        header = QHBoxLayout()
        self.lbl_role = QLabel("ROL: BELİRSİZ")
        self.lbl_role.setObjectName("RoleLabel")
        self.lbl_status = QLabel("Bağlantı Bekleniyor...")
        self.lbl_status.setObjectName("StatusLabel")
        header.addWidget(self.lbl_role); header.addStretch(); header.addWidget(self.lbl_status)
        main_layout.addLayout(header)

        # --- TAHMİN BARI ---
        self.prediction_frame = QFrame()
        self.prediction_frame.setVisible(False)
        pred_layout = QVBoxLayout(self.prediction_frame)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("QProgressBar { border: 2px solid #444; border-radius: 5px; text-align: center; background-color: #b71c1c; color: white; height: 20px; font-weight: bold; } QProgressBar::chunk { background-color: #0d47a1; }")
        pred_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.prediction_frame)

        # --- ORTA ALAN ---
        mid = QHBoxLayout()
        
        # Sol: Mavi Takım
        self.blue_slots = []
        blue_layout = QVBoxLayout()
        blue_layout.addWidget(QLabel("🔵 SENİN TAKIMIN"))
        for _ in range(5): s = ChampSlot("#0d47a1"); self.blue_slots.append(s); blue_layout.addWidget(s)
        mid.addLayout(blue_layout, 1)

        # Orta: AI Önerileri
        ai_layout = QVBoxLayout()
        ai_layout.addWidget(QLabel("🧠 KOÇ ÖNERİLERİ"))
        
        # Rakip Seçici (Manuel)
        enemy_select_layout = QHBoxLayout()
        enemy_select_layout.addWidget(QLabel("Rakip:"))
        self.combo_enemy_laner = QComboBox()
        self.combo_enemy_laner.addItem("Rakip Seçiniz")
        self.combo_enemy_laner.currentIndexChanged.connect(self.re_run_analysis_from_ui)
        enemy_select_layout.addWidget(self.combo_enemy_laner)
        ai_layout.addLayout(enemy_select_layout)
        
        self.suggestion_list = QListWidget()
        ai_layout.addWidget(self.suggestion_list)
        
        # Zorla Tavsiye Butonu
        self.btn_force = QPushButton("⚡ ZORLA TAVSİYE")
        self.btn_force.setStyleSheet("background-color: #ff9800; color: black; font-weight: bold; padding: 10px;")
        self.btn_force.clicked.connect(self.force_recommendation)
        ai_layout.addWidget(self.btn_force)
        
        mid.addLayout(ai_layout, 2)

        # Sağ: Kırmızı Takım
        self.red_slots = []
        red_layout = QVBoxLayout()
        red_layout.addWidget(QLabel("🔴 RAKİP TAKIM"))
        for _ in range(5): s = ChampSlot("#b71c1c"); self.red_slots.append(s); red_layout.addWidget(s)
        mid.addLayout(red_layout, 1)
        main_layout.addLayout(mid)

        # --- ALT ALAN (LOG & BUTONLAR) ---
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFixedHeight(100)
        main_layout.addWidget(self.log_output)

        btns = QHBoxLayout()
        b0 = QPushButton("❌ SIFIRLA")
        b0.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
        b0.clicked.connect(self.reset_ui_state)
        
        b1 = QPushButton("Veritabanı Güncelle (İnternet)"); b1.clicked.connect(lambda: self.run_script("scrape_data"))
        b2 = QPushButton("Merge Yap (Veriyi İşle)"); b2.clicked.connect(lambda: self.run_script("merge_all"))
        b3 = QPushButton("Test Yap"); b3.clicked.connect(self.run_test_scenario)
        
        btns.addWidget(b0); btns.addWidget(b1); btns.addWidget(b2); btns.addWidget(b3)
        main_layout.addLayout(btns)

    def apply_styles(self):
        try: qdarktheme.setup_theme("dark")
        except: pass
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QLabel { color: white; font-weight: bold; font-family: 'Segoe UI'; }
            QLabel#RoleLabel { background-color: #263238; color: #ffeb3b; padding: 8px; border-radius: 4px; font-size: 16px; }
            QPlainTextEdit { background-color: #000; color: #00e676; font-family: Consolas; border: 1px solid #333; }
            QPushButton { background-color: #37474f; color: white; padding: 8px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #00bcd4; color: black; }
            QListWidget { background-color: #1e1e1e; border: 1px solid #333; }
            QComboBox { padding: 5px; background-color: #333; color: white; border: 1px solid #555; }
        """)

    def update_connection_status(self, msg):
        self.lbl_status.setText(msg)
        if "Bağlandı" in msg: self.lbl_status.setStyleSheet("color: #00e676; font-weight: bold;")
        else: self.lbl_status.setStyleSheet("color: #ff5252; font-weight: bold;")

    def append_terminal_text(self, text):
        if not hasattr(self, 'log_output'): return 
        try:
            self.log_output.moveCursor(QTextCursor.MoveOperation.End)
            self.log_output.insertPlainText(text)
            self.log_output.moveCursor(QTextCursor.MoveOperation.End)
        except: pass
        
    def re_run_analysis_from_ui(self, index):
        if index == -1: return
        target = self.combo_enemy_laner.currentText()
        if "Seçiniz" in target: target = None
        self.run_ai_analysis(self.current_role, target, self.current_my_team, self.current_enemy_team)

    def force_recommendation(self):
        print("\n⚡ Manuel Tetikleme: Analiz Zorlanıyor...")
        role = self.current_role if self.current_role not in ["Unknown", "Belirsiz", ""] else "Mid"
        target = self.combo_enemy_laner.currentText()
        if "Seçiniz" in target: target = None
        self.run_ai_analysis(role, target, self.current_my_team, self.current_enemy_team)

    def handle_champ_select(self, data):
        """LCU'dan gelen veriyi işler"""
        my_team = data.get('my_team', [])
        enemy_team = data.get('enemy_team', [])
        my_role = data.get('my_role', 'Unknown')
        
        self.current_role = str(my_role)
        self.current_my_team = my_team
        self.current_enemy_team = enemy_team
        self.lbl_role.setText(f"ROL: {self.current_role.upper()}")

        # Kartları Güncelle
        for i in range(5):
            self.blue_slots[i].set_champ(my_team[i] if i < len(my_team) else "Picking...")
            self.red_slots[i].set_champ(enemy_team[i] if i < len(enemy_team) else "Picking...")
        
        # Rakip Listesini Güncelle
        self.update_enemy_combo(enemy_team)
        
        # Analiz için rol belirle
        role = self.current_role
        if str(role).lower() in ["unknown", "belirsiz", "none", "", "utility"]: role = "mid" 

        # Hedef rakibi belirle
        target = self.combo_enemy_laner.currentText()
        if "Seçiniz" in target: target = None
        
        if self.ai_engine:
            self.run_ai_analysis(role, target, my_team, enemy_team)

        # 5v5 Tahmin
        real_blue = [c for c in my_team if c not in ["Picking...", "Unknown", None]]
        real_red = [c for c in enemy_team if c not in ["Picking...", "Unknown", None]]
        
        if len(real_blue) == 5 and len(real_red) == 5 and self.match_predictor:
            try:
                b, r = self.match_predictor.predict_match(real_blue, real_red)
                self.progress_bar.setValue(int(b))
                self.progress_bar.setFormat(f"Kazanma Şansı: Mavi %v% - Kırmızı {int(r)}%")
                self.prediction_frame.setVisible(True)
            except: pass

    def update_enemy_combo(self, enemy_team):
        curr = self.combo_enemy_laner.currentText()
        self.combo_enemy_laner.blockSignals(True)
        self.combo_enemy_laner.clear()
        self.combo_enemy_laner.addItem("Rakip Seçiniz")
        real = [c for c in enemy_team if c not in ["Picking...", "Unknown", "...", None]]
        for e in real: self.combo_enemy_laner.addItem(e)
        if curr in real: self.combo_enemy_laner.setCurrentText(curr)
        self.combo_enemy_laner.blockSignals(False)

    def run_ai_analysis(self, role, enemy, ally, enemy_t):
        self.suggestion_list.clear()
        if not self.ai_engine: return
        
        try:
            picks = self.ai_engine.calculate_score(role, enemy, ally, enemy_t)
            if not picks:
                # print(f"⚠️ '{role}' için öneri yok.")
                return
            
            # print(f"✅ Analiz tamamlandı: {len(picks)} öneri.")
            
            for i, p in enumerate(picks, 1):
                reasons = ", ".join(p['reasons'][:3]) # İlk 3 nedeni göster
                text = f"#{i} {p['name']} ({p['class']}) - WR: %{p['wr']}\n   ➤ {reasons}"
                item = QListWidgetItem(text)
                
                # İlk sıradakini vurgula
                if i == 1:
                    item.setForeground(QColor("#00e5ff"))
                    font = QFont("Segoe UI", 10, QFont.Weight.Bold)
                    item.setFont(font)
                
                self.suggestion_list.addItem(item)
        except Exception as e: print(f"Analiz Hatası: {e}")

    def run_script(self, task_type):
        self.runner = ScriptRunner(task_type)
        self.runner.finished_task.connect(lambda: self.load_ai_modules())
        self.runner.start()

    def run_test_scenario(self):
        print("\n🧪 Test Senaryosu Çalıştırılıyor...")
        self.handle_champ_select({
            "my_team": ["Malphite", "Amumu", "Yasuo", "Kai'Sa", "Nautilus"],
            "enemy_team": ["Teemo", "Lee Sin", "Zed", "Caitlyn", "Lux"],
            "my_role": "Mid" 
        })

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
