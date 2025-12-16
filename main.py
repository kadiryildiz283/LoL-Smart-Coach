import sys
import os
import qdarktheme
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QListWidget, 
                             QListWidgetItem, QFrame, QMessageBox, QPlainTextEdit,
                             QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QTextCursor

# --- MODÜLLER ---
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
    pass # Exe içinde bazen import hatası görünebilir ama çalışır

# --- EXE UYUMLU DOSYA YOLU BULUCU ---
def resource_path(relative_path):
    """ PyInstaller ile oluşturulan exe için dosya yolunu bulur """
    try:
        # PyInstaller temp klasörü
        base_path = sys._MEIPASS
    except Exception:
        # Normal çalışma
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- LOG SİSTEMİ ---
class EmittingStream(QObject):
    textWritten = pyqtSignal(str)
    def write(self, text):
        if text: self.textWritten.emit(str(text))
    def flush(self): pass

class ScriptRunner(QThread):
    finished_task = pyqtSignal()
    def __init__(self, task_type):
        super().__init__()
        self.task_type = task_type

    def run(self):
        try:
            # Scriptlerin çalıştığı dizini düzeltmek gerekebilir
            if self.task_type == "update_list":
                print("⏳ Liste güncelleniyor..."); list_update.main()
            elif self.task_type == "scrape_data":
                print("⏳ İstatistikler çekiliyor..."); veri_cekici_main.main()
            elif self.task_type == "merge_all":
                print("ℹ️ Veriler birleştiriliyor..."); 
                expert_parser.main(); merge_expert_data.main(); merge_damage_stats.main()
                print("🎉 Veritabanı hazır.")
        except Exception as e: print(f"❌ HATA: {str(e)}")
        self.finished_task.emit()

# --- ÖZEL WIDGET: ŞAMPİYON KARTI ---
class ChampSlot(QFrame):
    def __init__(self, color_code):
        super().__init__()
        self.setObjectName("ChampSlot")
        self.setStyleSheet(f"QFrame#ChampSlot {{ background-color: {color_code}; border-radius: 8px; border: 1px solid #444; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        self.lbl_name = QLabel("...")
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_name)

    def set_champ(self, name):
        if name == "Picking...":
            self.lbl_name.setText("Seçiliyor...")
            self.lbl_name.setStyleSheet("color: #aaa; font-style: italic; font-size: 12px;")
        else:
            self.lbl_name.setText(name)
            self.lbl_name.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")

# --- ANA PENCERE ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL Smart Coach - Pro")
        self.setGeometry(100, 100, 1200, 850)

        # Veri yolunu resource_path ile alıyoruz
        self.data_path = resource_path(os.path.join("data", "tum_sampiyonlar_verisi_full.json"))
        
        self.ai_engine = None
        self.match_predictor = None
        self.load_ai_modules()

        # Terminal Bağlantısı
        self.terminal_stream = EmittingStream()
        self.terminal_stream.textWritten.connect(self.append_terminal_text)
        sys.stdout = self.terminal_stream
        sys.stderr = self.terminal_stream

        # LCU
        self.lcu_thread = LCUWorker()
        self.lcu_thread.connection_status.connect(self.update_connection_status)
        self.lcu_thread.champ_select_update.connect(self.handle_champ_select)
        self.lcu_thread.start()

        self.setup_ui()
        self.apply_styles()
        print("🚀 LoL Smart Coach Başlatıldı.")

    def load_ai_modules(self):
        if os.path.exists(self.data_path):
            self.ai_engine = LoLDecisionEngine(self.data_path)
            self.match_predictor = LoLMatchPredictor(self.data_path)
        else:
            print(f"⚠️ Veritabanı bulunamadı: {self.data_path}")

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(15)

        # 1. HEADER
        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")
        header_layout = QHBoxLayout(header_frame)
        self.lbl_role = QLabel("ROL: BELİRSİZ")
        self.lbl_role.setObjectName("RoleLabel")
        header_layout.addWidget(self.lbl_role)
        header_layout.addStretch()
        self.lbl_status = QLabel("❌ Client Bağlı Değil")
        self.lbl_status.setObjectName("StatusLabel")
        header_layout.addWidget(self.lbl_status)
        main_layout.addWidget(header_frame)

        # 2. TAHMİN BARI
        self.prediction_frame = QFrame()
        self.prediction_frame.setVisible(False)
        pred_layout = QVBoxLayout(self.prediction_frame)
        lbl_pred_title = QLabel("🔮 MAÇ SONUCU TAHMİNİ")
        lbl_pred_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_pred_title.setStyleSheet("color: #FFD700; font-weight: bold;")
        pred_layout.addWidget(lbl_pred_title)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 2px solid #333; border-radius: 5px; text-align: center; height: 25px; background-color: #b71c1c; color: white; font-weight: bold; }
            QProgressBar::chunk { background-color: #0d47a1; }
        """)
        self.progress_bar.setFormat("Mavi %v% - Kırmızı %p%") 
        pred_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.prediction_frame)

        # 3. ORTA ALAN
        mid_layout = QHBoxLayout()
        
        # Mavi
        self.blue_slots = []
        blue_layout = QVBoxLayout()
        blue_layout.addWidget(QLabel("🔵 SENİN TAKIMIN"))
        for _ in range(5):
            slot = ChampSlot("#0d47a1")
            self.blue_slots.append(slot)
            blue_layout.addWidget(slot)
        mid_layout.addLayout(blue_layout, 1)

        # AI
        ai_layout = QVBoxLayout()
        lbl_ai = QLabel("🧠 KOÇ ÖNERİLERİ")
        lbl_ai.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_ai.setStyleSheet("font-size: 18px; font-weight: bold; color: #00e5ff;")
        ai_layout.addWidget(lbl_ai)
        self.suggestion_list = QListWidget()
        ai_layout.addWidget(self.suggestion_list)
        mid_layout.addLayout(ai_layout, 2)

        # Kırmızı
        self.red_slots = []
        red_layout = QVBoxLayout()
        red_layout.addWidget(QLabel("🔴 RAKİP TAKIM"))
        for _ in range(5):
            slot = ChampSlot("#b71c1c")
            self.red_slots.append(slot)
            red_layout.addWidget(slot)
        mid_layout.addLayout(red_layout, 1)
        main_layout.addLayout(mid_layout)

        # 4. ALT KISIM
        bottom_layout = QHBoxLayout()
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setObjectName("LogOutput")
        self.log_output.setFixedHeight(80)
        bottom_layout.addWidget(self.log_output, 3)

        btn_layout = QVBoxLayout()
        btn_update = QPushButton("Veritabanı Güncelle"); btn_update.clicked.connect(lambda: self.run_script("scrape_data"))
        btn_merge = QPushButton("Merge Yap"); btn_merge.clicked.connect(lambda: self.run_script("merge_all"))
        btn_test = QPushButton("Test Yap"); btn_test.clicked.connect(self.run_test_scenario)
        btn_layout.addWidget(btn_update); btn_layout.addWidget(btn_merge); btn_layout.addWidget(btn_test)
        
        bottom_layout.addLayout(btn_layout, 1)
        main_layout.addLayout(bottom_layout)

    def apply_styles(self):
        try: qdarktheme.setup_theme("dark")
        except: pass
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QLabel { color: #eee; font-weight: bold; }
            QLabel#RoleLabel { background-color: #263238; color: #ffeb3b; padding: 8px; border-radius: 5px; border: 1px solid #444; }
            QLabel#StatusLabel { font-size: 14px; margin-right: 10px; }
            QListWidget { background-color: #1a1a1a; border: 1px solid #333; border-radius: 8px; font-size: 13px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #222; }
            QPlainTextEdit#LogOutput { background-color: #000; color: #00ff00; font-family: Consolas; font-size: 11px; }
            QPushButton { background-color: #37474f; color: white; padding: 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #00bcd4; color: black; }
        """)

    def update_connection_status(self, msg):
        self.lbl_status.setText(msg)
        if "Bağlandı" in msg: self.lbl_status.setStyleSheet("color: #00e676;")
        else: self.lbl_status.setStyleSheet("color: #ff5252;")

    def append_terminal_text(self, text):
        self.log_output.moveCursor(QTextCursor.MoveOperation.End)
        self.log_output.insertPlainText(text)
        self.log_output.moveCursor(QTextCursor.MoveOperation.End)

    def handle_champ_select(self, data):
        my_team = data['my_team']
        enemy_team = data['enemy_team']
        my_role = data.get('my_role', 'Unknown')
        
        self.lbl_role.setText(f"SEÇİLEN ROL: {my_role.upper()}")

        for i in range(5):
            self.blue_slots[i].set_champ(my_team[i] if i < len(my_team) else "...")
        for i in range(5):
            self.red_slots[i].set_champ(enemy_team[i] if i < len(enemy_team) else "...")

        if enemy_team:
            last_enemy = enemy_team[-1]
            if last_enemy != "Picking...":
                self.run_ai_analysis(my_role, last_enemy, my_team, enemy_team)

        # Maç Tahmini (5v5)
        real_blue = [c for c in my_team if c != "Picking..."]
        real_red = [c for c in enemy_team if c != "Picking..."]
        
        if len(real_blue) == 5 and len(real_red) == 5:
            self.prediction_frame.setVisible(True)
            if self.match_predictor:
                # Tahmin fonksiyonu artık değer döndürüyor
                blue_wr, red_wr = self.match_predictor.predict_match(real_blue, real_red)
                self.progress_bar.setValue(int(blue_wr))
                self.progress_bar.setFormat(f"Mavi %v% - Kırmızı {int(red_wr)}%")
        else:
            self.prediction_frame.setVisible(False)

    def run_ai_analysis(self, my_role, enemy_laner, ally_team, enemy_team):
        if not self.ai_engine: return
        self.suggestion_list.clear()
        
        real_allies = [c for c in ally_team if c != "Picking..."]
        real_enemies = [c for c in enemy_team if c != "Picking..."]
        if my_role == "Unknown": my_role = "Mid"

        picks = self.ai_engine.calculate_score(my_role, enemy_laner, real_allies, real_enemies)
        
        for i, p in enumerate(picks, 1):
            text = f"#{i} {p['name']} ({p['class']}) - WR: %{p['wr']}\n   ➤ {', '.join(p['reasons'][:3])}"
            item = QListWidgetItem(text)
            if i == 1:
                item.setForeground(QColor("#00e5ff"))
                font = item.font(); font.setBold(True); item.setFont(font)
            self.suggestion_list.addItem(item)

    def run_script(self, task_type):
        print(f"🚀 İşlem: {task_type}")
        self.runner = ScriptRunner(task_type)
        self.runner.finished_task.connect(lambda: self.load_ai_modules())
        self.runner.start()

    def run_test_scenario(self):
        data = {
            "my_team": ["Malphite", "Amumu", "Yasuo", "Kai'Sa", "Nautilus"],
            "enemy_team": ["Jayce", "Kha'Zix", "Zed", "Caitlyn", "Lux"],
            "my_role": "Mid"
        }
        self.handle_champ_select(data)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
