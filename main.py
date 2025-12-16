import sys
import os
import asyncio
import traceback
import warnings

# --- 1. AYARLAR ---
warnings.filterwarnings("ignore", category=DeprecationWarning)

import qdarktheme
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QListWidget, 
                             QListWidgetItem, QFrame, QMessageBox, QPlainTextEdit,
                             QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QTextCursor

# --- 2. HATA YAKALAYICI ---
def global_exception_handler(exctype, value, tb):
    if "log_output" in str(value):
        sys.__stdout__.write(f"Başlangıç Log Hatası: {value}\n")
        return
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    sys.__stdout__.write(f"KRİTİK HATA:\n{error_msg}\n")
    try:
        if QApplication.instance():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("Beklenmeyen Hata")
            msg.setDetailedText(error_msg)
            msg.exec()
    except: pass

sys.excepthook = global_exception_handler

# --- 3. MODÜLLER ---
try:
    import list_update
    import veri_cekici_main
    import expert_parser
    import merge_expert_data
    import merge_damage_stats
    from core.lcu_connector import LCUWorker
    from core.ai_recommendation_final import LoLDecisionEngine
    from core.match_predictor import LoLMatchPredictor
except ImportError as e:
    print(f"⚠️ Modül Eksik: {e}")

# --- 4. YARDIMCI ---
def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- 5. LOG SİSTEMİ ---
class EmittingStream(QObject):
    textWritten = pyqtSignal(str)
    def write(self, text):
        if text: self.textWritten.emit(str(text))
    def flush(self): pass

# --- 6. ARKAPLAN İŞÇİSİ ---
class ScriptRunner(QThread):
    finished_task = pyqtSignal()
    def __init__(self, task_type):
        super().__init__()
        self.task_type = task_type

    def run(self):
        try:
            if self.task_type == "scrape_data":
                print("⏳ İstatistikler çekiliyor..."); veri_cekici_main.main()
            elif self.task_type == "merge_all":
                print("ℹ️ Veriler birleştiriliyor..."); expert_parser.main(); merge_expert_data.main(); merge_damage_stats.main()
                print("🎉 Veritabanı Hazır.")
        except Exception as e: print(f"❌ HATA: {str(e)}")
        self.finished_task.emit()

# --- 7. KART WIDGET ---
class ChampSlot(QFrame):
    def __init__(self, color_code):
        super().__init__()
        self.setStyleSheet(f"background-color: {color_code}; border-radius: 8px; border: 1px solid #444;")
        layout = QVBoxLayout(self); layout.setContentsMargins(5,5,5,5)
        self.lbl_name = QLabel("...")
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_name)

    def set_champ(self, name):
        if name in ["Picking...", "Unknown", "...", "None"]:
            self.lbl_name.setText("...")
            self.lbl_name.setStyleSheet("color: #aaa; font-style: italic;")
        else:
            self.lbl_name.setText(name)
            self.lbl_name.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")

# --- 8. ANA PENCERE ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL Smart Coach - Manual Force Edition")
        self.setGeometry(100, 100, 1200, 850)

        self.setup_ui()
        self.apply_styles()

        self.terminal_stream = EmittingStream()
        self.terminal_stream.textWritten.connect(self.append_terminal_text)
        sys.stdout = self.terminal_stream
        sys.stderr = self.terminal_stream

        self.data_path = resource_path(os.path.join("data", "tum_sampiyonlar_verisi_full.json"))
        self.ai_engine = None
        self.match_predictor = None
        self.current_role = "Unknown" # Rolü hafızada tutmak için
        
        print("⚙️ Sistem başlatılıyor...")
        self.load_ai_modules()

        try:
            self.lcu_thread = LCUWorker()
            self.lcu_thread.connection_status.connect(self.update_connection_status)
            self.lcu_thread.champ_select_update.connect(self.handle_champ_select)
            self.lcu_thread.start()
        except Exception as e: print(f"LCU Hatası: {e}")

    def load_ai_modules(self):
        if os.path.exists(self.data_path):
            try:
                self.ai_engine = LoLDecisionEngine(self.data_path)
                self.match_predictor = LoLMatchPredictor(self.data_path)
                print(f"✅ Veritabanı Hazır.")
            except: print("❌ Veritabanı Yüklenemedi.")
        else: print("⚠️ Veritabanı Yok! Lütfen Merge Yapın.")

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Header
        header = QHBoxLayout()
        self.lbl_role = QLabel("ROL: BELİRSİZ")
        self.lbl_role.setObjectName("RoleLabel")
        self.lbl_status = QLabel("Client Bekleniyor...")
        self.lbl_status.setObjectName("StatusLabel")
        header.addWidget(self.lbl_role); header.addStretch(); header.addWidget(self.lbl_status)
        main_layout.addLayout(header)

        # Tahmin Barı
        self.prediction_frame = QFrame()
        self.prediction_frame.setVisible(False)
        pred_layout = QVBoxLayout(self.prediction_frame)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("QProgressBar { border: 2px solid #444; border-radius: 5px; text-align: center; background-color: #b71c1c; color: white; } QProgressBar::chunk { background-color: #0d47a1; }")
        pred_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.prediction_frame)

        # Orta Alan
        mid = QHBoxLayout()
        
        self.blue_slots = []
        blue_layout = QVBoxLayout()
        blue_layout.addWidget(QLabel("🔵 SENİN TAKIMIN"))
        for _ in range(5): s = ChampSlot("#0d47a1"); self.blue_slots.append(s); blue_layout.addWidget(s)
        mid.addLayout(blue_layout, 1)

        ai_layout = QVBoxLayout()
        ai_layout.addWidget(QLabel("🧠 KOÇ ÖNERİLERİ"))
        self.suggestion_list = QListWidget()
        ai_layout.addWidget(self.suggestion_list)
        
        # --- ZORLA TAVSİYE TUŞU (YENİ) ---
        self.btn_force = QPushButton("⚡ ZORLA TAVSİYE VER")
        self.btn_force.setStyleSheet("""
            background-color: #ff9800; color: black; font-weight: bold; padding: 10px;
        """)
        self.btn_force.clicked.connect(self.force_recommendation)
        ai_layout.addWidget(self.btn_force)
        
        mid.addLayout(ai_layout, 2)

        self.red_slots = []
        red_layout = QVBoxLayout()
        red_layout.addWidget(QLabel("🔴 RAKİP TAKIM"))
        for _ in range(5): s = ChampSlot("#b71c1c"); self.red_slots.append(s); red_layout.addWidget(s)
        mid.addLayout(red_layout, 1)
        main_layout.addLayout(mid)

        # Alt Kısım
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFixedHeight(80)
        main_layout.addWidget(self.log_output)

        btns = QHBoxLayout()
        b1 = QPushButton("Veritabanı Güncelle"); b1.clicked.connect(lambda: self.run_script("scrape_data"))
        b2 = QPushButton("Merge Yap"); b2.clicked.connect(lambda: self.run_script("merge_all"))
        b3 = QPushButton("Test Yap"); b3.clicked.connect(self.run_test_scenario)
        btns.addWidget(b1); btns.addWidget(b2); btns.addWidget(b3)
        main_layout.addLayout(btns)

    def apply_styles(self):
        try: qdarktheme.setup_theme("dark")
        except: pass
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QLabel { color: white; font-weight: bold; }
            QLabel#RoleLabel { background-color: #263238; color: #ffeb3b; padding: 5px 10px; border-radius: 4px; }
            QPlainTextEdit { background-color: black; color: #00e676; font-family: Consolas; }
            QPushButton { background-color: #37474f; color: white; padding: 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #00bcd4; }
        """)

    def update_connection_status(self, msg):
        self.lbl_status.setText(msg)
        if "Bağlandı" in msg: self.lbl_status.setStyleSheet("color: #00e676;")
        else: self.lbl_status.setStyleSheet("color: #ff5252;")

    def append_terminal_text(self, text):
        if not hasattr(self, 'log_output'): return 
        try:
            self.log_output.moveCursor(QTextCursor.MoveOperation.End)
            self.log_output.insertPlainText(text)
            self.log_output.moveCursor(QTextCursor.MoveOperation.End)
        except RuntimeError: pass

    # --- YENİ ÖZELLİK: ZORLA TAVSİYE ---
    def force_recommendation(self):
        print("\n⚡ Manuel Tetikleme: Tavsiye zorlanıyor...")
        
        # Şu anki rolü kontrol et, eğer yoksa 'Mid' yap
        role_to_use = self.current_role
        if role_to_use in ["Unknown", "Belirsiz", "None", ""]:
            role_to_use = "Mid"
            print("⚠️ Rol bulunamadı, varsayılan 'Mid' kullanılıyor.")
        
        # Analizi boş parametrelerle bile olsa çalıştır
        # Bu sayede sadece Tier List (WR) bazlı öneri verir
        self.run_ai_analysis(role_to_use, None, [], [])

    # --- OTO ANALİZ ---
    def handle_champ_select(self, data):
        my_team = data.get('my_team', [])
        enemy_team = data.get('enemy_team', [])
        my_role = data.get('my_role', 'Unknown')
        
        # Rolü hafızaya al (Manuel tuş için gerekli)
        self.current_role = str(my_role)
        self.lbl_role.setText(f"ROL: {self.current_role.upper()}")

        for i in range(5):
            self.blue_slots[i].set_champ(my_team[i] if i < len(my_team) else "Picking...")
        for i in range(5):
            self.red_slots[i].set_champ(enemy_team[i] if i < len(enemy_team) else "Picking...")

        real_enemies = [c for c in enemy_team if c not in ["Picking...", "Unknown", "...", "None"]]
        
        # Rol Düzeltme
        analysis_role = self.current_role
        if str(analysis_role).lower() in ["unknown", "belirsiz", "none", "", "utility"]: 
            analysis_role = "mid" 

        # Analizi Çalıştır
        if self.ai_engine:
            target_enemy = real_enemies[-1] if real_enemies else None
            # print(f"🔍 Oto Analiz -> Rol: {analysis_role}")
            self.run_ai_analysis(analysis_role, target_enemy, my_team, enemy_team)

        # 5v5 Tahmin
        real_blue = [c for c in my_team if c not in ["Picking...", "Unknown", "...", "None"]]
        if len(real_blue) == 5 and len(real_enemies) == 5:
            self.prediction_frame.setVisible(True)
            if self.match_predictor:
                try:
                    b, r = self.match_predictor.predict_match(real_blue, real_enemies)
                    self.progress_bar.setValue(int(b))
                    self.progress_bar.setFormat(f"Mavi %v% - Kırmızı {int(r)}%")
                except: pass
        else:
            self.prediction_frame.setVisible(False)

    def run_ai_analysis(self, my_role, enemy_laner, ally_team, enemy_team):
        self.suggestion_list.clear()
        real_allies = [c for c in ally_team if c not in ["Picking...", "Unknown", "...", "None"]]
        real_enemies = [c for c in enemy_team if c not in ["Picking...", "Unknown", "...", "None"]]
        
        try:
            picks = self.ai_engine.calculate_score(my_role, enemy_laner, real_allies, real_enemies)
            
            if not picks:
                print(f"⚠️ '{my_role}' için veri bulunamadı.")
                return

            print(f"✅ {my_role} için {len(picks)} şampiyon önerildi.")

            for i, p in enumerate(picks, 1):
                text = f"#{i} {p['name']} ({p['class']}) - WR: %{p['wr']}\n   ➤ {', '.join(p['reasons'][:3])}"
                item = QListWidgetItem(text)
                if i == 1:
                    item.setForeground(QColor("#00e5ff"))
                    f = item.font(); f.setBold(True); item.setFont(f)
                self.suggestion_list.addItem(item)
        except Exception as e:
            print(f"AI Hatası: {e}")

    def run_script(self, task_type):
        print(f"🚀 İşlem: {task_type}")
        self.runner = ScriptRunner(task_type)
        self.runner.finished_task.connect(lambda: self.load_ai_modules())
        self.runner.start()

    def run_test_scenario(self):
        print("\n🧪 Test Senaryosu...")
        data = {
            "my_team": ["Malphite", "Picking...", "Picking...", "Picking...", "Picking..."],
            "enemy_team": ["Teemo", "Picking...", "Picking...", "Picking...", "Picking..."],
            "my_role": "Unknown" 
        }
        self.handle_champ_select(data)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())