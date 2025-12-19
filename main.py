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
                             QHBoxLayout, QLabel, QFrame, QMessageBox, QPlainTextEdit,
                             QProgressBar, QComboBox, QGridLayout, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QTextCursor, QIcon

# --- YENİ MODÜLLER ---
from core.ui_components import HexagonWidget, ModernButton
from core.data_manager import ensure_data_directory, get_resource_path
import pyqtgraph as pg

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
    # Path düzeltme
    ensure_data_directory() 
    
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

# --- 8. ANA PENCERE ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL Smart Coach - Premium Edition")
        self.setGeometry(100, 100, 1280, 800)
        self.setWindowIcon(QIcon(get_resource_path("assets/logo.ico")))

        # Veri Yolu
        self.data_path = get_resource_path(os.path.join("data", "tum_sampiyonlar_verisi_full.json"))
        
        self.ai_engine = None
        self.match_predictor = None
        self.current_role = "Unknown" 
        self.current_my_team = []
        self.current_enemy_team = []

        self.setup_ui()
        self.apply_styles()

        # Log Bağlama
        self.terminal_stream = EmittingStream()
        self.terminal_stream.textWritten.connect(self.append_terminal_text)
        sys.stdout = self.terminal_stream
        sys.stderr = self.terminal_stream
        
        print("⚙️ Sistem başlatılıyor...")
        self.load_ai_modules()

        # LCU
        try:
            self.lcu_thread = LCUWorker()
            self.lcu_thread.connection_status.connect(self.update_connection_status)
            self.lcu_thread.champ_select_update.connect(self.handle_champ_select) 
            self.lcu_thread.start()
        except Exception as e: print(f"LCU Hatası: {e}")

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- HEADER ---
        header = QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #0d1117; border-bottom: 2px solid #00bcff;")
        h_layout = QHBoxLayout(header)
        
        self.lbl_role = QLabel("ROL: BELİRSİZ")
        self.lbl_role.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_role.setStyleSheet("color: #00bcff; letter-spacing: 1px;")
        
        self.lbl_status = QLabel("Client Bekleniyor...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        h_layout.addWidget(self.lbl_role)
        h_layout.addStretch()
        h_layout.addWidget(self.lbl_status)
        
        main_layout.addWidget(header)

        # --- CONTENT AREA (Sol - Orta - Sağ) ---
        content_area = QWidget()
        content_layout = QHBoxLayout(content_area)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # 1. SOL SÜTUN (Kendi Takımımız)
        left_col = QVBoxLayout()
        left_col.setSpacing(15)
        self.blue_slots = []
        for i in range(5):
            h = HexagonWidget(size=90, color="#0d47a1", border_color="#2979ff")
            self.blue_slots.append(h)
            left_col.addWidget(h, alignment=Qt.AlignmentFlag.AlignHCenter)
        left_col.addStretch()
        content_layout.addLayout(left_col, 1)

        # 2. ORTA ALAN (Grafikler ve Öneriler)
        mid_col = QVBoxLayout()
        mid_col.setSpacing(10)
        
        # -- Grafik Alanı --
        self.graph_container = QFrame()
        self.graph_container.setFixedHeight(250)
        self.graph_container.setStyleSheet("background-color: #161b22; border-radius: 10px; border: 1px solid #30363d;")
        graph_layout = QVBoxLayout(self.graph_container)
        
        # PyQtGraph Ayarları
        pg.setConfigOption('background', '#0d1117')
        pg.setConfigOption('foreground', 'w')
        self.bar_chart = pg.PlotWidget()
        self.bar_chart.setBackground(None) # Transparent olması için deneme, ama theme eziyor olabilir
        self.bar_chart.showGrid(x=False, y=True, alpha=0.3)
        self.bar_chart.getAxis('bottom').setTicks([[]]) # X ekseni yazılarını gizle
        self.bar_chart.setTitle("Takım Güç Analizi", color="w", size="10pt")
        graph_layout.addWidget(self.bar_chart)
        
        mid_col.addWidget(self.graph_container)

        # -- Öneri Listesi ve Kontroller --
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: transparent;")
        info_layout = QVBoxLayout(info_frame)
        
        # Rakip Seçici
        row_sel = QHBoxLayout()
        lbl_sel = QLabel("Rakip Koridor:")
        lbl_sel.setStyleSheet("color: #8b949e;")
        self.combo_enemy_laner = QComboBox()
        self.combo_enemy_laner.addItem("Rakip Seçiniz")
        self.combo_enemy_laner.setStyleSheet("""
            QComboBox { background-color: #21262d; color: white; border: 1px solid #30363d; padding: 5px; }
            QComboBox QAbstractItemView { background-color: #21262d; color: white; }
        """)
        self.combo_enemy_laner.currentIndexChanged.connect(self.re_run_analysis_from_ui)
        row_sel.addWidget(lbl_sel)
        row_sel.addWidget(self.combo_enemy_laner)
        info_layout.addLayout(row_sel)
        
        # Liste
        self.suggestion_label = QLabel("Bekleniyor...")
        self.suggestion_label.setWordWrap(True)
        self.suggestion_label.setStyleSheet("color: #e6edf3; font-size: 14px; background-color: #161b22; padding: 10px; border-radius: 8px;")
        self.suggestion_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        info_layout.addWidget(self.suggestion_label, 1)

        mid_col.addWidget(info_frame, 1)
        content_layout.addLayout(mid_col, 3)

        # 3. SAĞ SÜTUN (Rakip Takım)
        right_col = QVBoxLayout()
        right_col.setSpacing(15)
        self.red_slots = []
        for i in range(5):
            h = HexagonWidget(size=90, color="#b71c1c", border_color="#ff5252")
            self.red_slots.append(h)
            right_col.addWidget(h, alignment=Qt.AlignmentFlag.AlignHCenter)
        right_col.addStretch()
        content_layout.addLayout(right_col, 1)

        main_layout.addWidget(content_area)

        # --- FOOTER ---
        footer = QFrame()
        footer.setFixedHeight(120)
        footer.setStyleSheet("background-color: #0d1117; border-top: 1px solid #30363d;")
        f_layout = QVBoxLayout(footer)
        
        # Terminal
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #010409; color: #3fb950; border: none; font-family: Consolas;")
        f_layout.addWidget(self.log_output)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        b_reset = ModernButton("SIFIRLA", "#ff5252")
        b_reset.clicked.connect(self.reset_ui_state)
        
        b_update = ModernButton("Veri Güncelle", "#2f81f7")
        b_update.clicked.connect(lambda: self.run_script("scrape_data"))
        
        b_merge = ModernButton("Merge Yap", "#a371f7")
        b_merge.clicked.connect(lambda: self.run_script("merge_all"))
        
        b_force = ModernButton("Zorla Tavsiye", "#d29922")
        b_force.clicked.connect(self.force_recommendation)
        
        btn_layout.addWidget(b_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(b_update)
        btn_layout.addWidget(b_merge)
        btn_layout.addWidget(b_force)
        
        f_layout.addLayout(btn_layout)
        
        main_layout.addWidget(footer)

    def apply_styles(self):
        # Genel QDarkTheme
        try: qdarktheme.setup_theme("dark")
        except: pass
        
        # Global CSS Override
        self.setStyleSheet("""
            QMainWindow { background-color: #010409; }
            QLabel { color: #c9d1d9; }
            QScrollBar:vertical { background: #0d1117; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: #30363d; min-height: 20px; border-radius: 5px; }
        """)

    # ... (Diğer fonksiyonlar: load_ai_modules, reset_ui_state, vb. önceki mantıkla aynı)
    # Ancak UI elemanlarına referansları koda göre uyarlayacağız.
    
    def load_ai_modules(self):
        if os.path.exists(self.data_path):
            try:
                self.ai_engine = LoLDecisionEngine(self.data_path)
                self.match_predictor = LoLMatchPredictor(self.data_path)
                print(f"✅ Veritabanı Hazır.")
            except: print("❌ Veritabanı Yüklenemedi.")
        else: print("⚠️ Veritabanı Yok! Lütfen Merge Yapın.")

    def reset_ui_state(self):
        print("\n🗑️ Arayüz ve Hafıza Sıfırlandı.")
        self.current_role = "Unknown"
        self.current_my_team = []
        self.current_enemy_team = []
        
        self.lbl_role.setText("ROL: BELİRSİZ")
        self.suggestion_label.setText("Sıfırlandı.")
        self.combo_enemy_laner.clear()
        self.combo_enemy_laner.addItem("Rakip Seçiniz")
        
        # Hexagonları sıfırla
        for slot in self.blue_slots: slot.set_champ("...")
        for slot in self.red_slots: slot.set_champ("...")
        
        # Grafiği temizle
        self.bar_chart.clear()
        
        try:
            self.lcu_thread.stop() 
            self.lcu_thread = LCUWorker()
            self.lcu_thread.connection_status.connect(self.update_connection_status)
            self.lcu_thread.champ_select_update.connect(self.handle_champ_select) 
            self.lcu_thread.start()
        except: pass

    def update_connection_status(self, msg):
        self.lbl_status.setText(msg)
        if "Bağlandı" in msg: self.lbl_status.setStyleSheet("color: #3fb950; font-weight: bold;")
        else: self.lbl_status.setStyleSheet("color: #f85149;")

    def append_terminal_text(self, text):
        if not hasattr(self, 'log_output'): return 
        try:
            self.log_output.moveCursor(QTextCursor.MoveOperation.End)
            self.log_output.insertPlainText(text)
            self.log_output.moveCursor(QTextCursor.MoveOperation.End)
        except RuntimeError: pass

    def re_run_analysis_from_ui(self, index):
        if index == -1: return
        target_enemy = self.combo_enemy_laner.currentText()
        if "Rakip Seçiniz" in target_enemy: target_enemy = None
        
        role = self.current_role
        if role.lower() in ["unknown", "belirsiz", "none", ""]: role = "mid"
        
        if self.ai_engine:
            self.run_ai_analysis(role, target_enemy, self.current_my_team, self.current_enemy_team)

    def force_recommendation(self):
        print("\n⚡ Manuel Tetikleme.")
        role = self.current_role
        if role in ["Unknown", "Belirsiz", "None", ""]: role = "Mid"
        
        target = self.combo_enemy_laner.currentText()
        if "Rakip Seçiniz" in target: target = None
        
        self.run_ai_analysis(role, target, self.current_my_team, self.current_enemy_team)

    def handle_champ_select(self, data):
        my_team = data.get('my_team', [])
        enemy_team = data.get('enemy_team', [])
        my_role = data.get('my_role', 'Unknown')
        
        self.current_role = str(my_role)
        self.current_my_team = my_team
        self.current_enemy_team = enemy_team
        self.lbl_role.setText(f"ROL: {self.current_role.upper()}")
        
        # Hexagon güncelle
        for i in range(5):
            name = my_team[i] if i < len(my_team) else "..."
            self.blue_slots[i].set_champ(name)
        for i in range(5):
            name = enemy_team[i] if i < len(enemy_team) else "..."
            self.red_slots[i].set_champ(name)
            
        # Rakip Seçici
        current_selection = self.combo_enemy_laner.currentText()
        self.combo_enemy_laner.currentIndexChanged.disconnect(self.re_run_analysis_from_ui)
        self.combo_enemy_laner.clear()
        self.combo_enemy_laner.addItem("Rakip Seçiniz")
        real_enemies = [c for c in enemy_team if c not in ["Picking...", "Unknown", "...", "None"]]
        for e in real_enemies: self.combo_enemy_laner.addItem(e)
        
        if current_selection in real_enemies:
            self.combo_enemy_laner.setCurrentText(current_selection)
        self.combo_enemy_laner.currentIndexChanged.connect(self.re_run_analysis_from_ui)
        
        # Analiz
        target_enemy = self.combo_enemy_laner.currentText()
        if "Rakip Seçiniz" in target_enemy: target_enemy = None
        
        role = self.current_role
        if role.lower() in ["unknown", ""]: role = "mid"
        
        if self.ai_engine:
            self.run_ai_analysis(role, target_enemy, my_team, enemy_team)

    def run_ai_analysis(self, my_role, enemy_laner, ally_team, enemy_team):
        print(f"💡 Analiz: Rol={my_role}, Rakip={enemy_laner}")
        try:
            picks = self.ai_engine.calculate_score(my_role, enemy_laner, ally_team, enemy_team)
            if not picks:
                self.suggestion_label.setText("⚠ Uygun şampiyon bulunamadı.")
                return

            # Metin oluştur
            lines = []
            top_scores = [] # Grafik için
            top_names = []
            
            for i, p in enumerate(picks[:5], 1): # İlk 5
                reasons = ", ".join(p['reasons'][:2])
                html_line = f"<b style='color: #00e676; font-size:15px'>#{i} {p['name']}</b> <span style='color:#8b949e'>({p['class']})</span><br><i>{reasons}</i><br>"
                lines.append(html_line)
                
                # Grafik verisi
                top_names.append(p['name'])
                top_scores.append(p.get('total_score', 50)) # Skor yoksa 50 varsay

            self.suggestion_label.setText("".join(lines))
            
            # Grafiği Güncelle
            self.update_chart(top_names, top_scores)
            
        except Exception as e:
            print(f"AI Analiz Hatası: {e}")
            traceback.print_exc()

    def update_chart(self, names, scores):
        self.bar_chart.clear()
        # Bar chart çizimi
        bg = pg.BarGraphItem(x=range(len(scores)), height=scores, width=0.6, brush='#00bcd4')
        self.bar_chart.addItem(bg)
        
        # X Eksenine isimleri koy (Biraz trick gerektirir, pyqtgraph'ta AxisItem override etmek daha doğru ama basitçe stringaxis kullanabiliriz)
        ax = self.bar_chart.getAxis('bottom')
        ticks = [list(zip(range(len(names)), names))]
        ax.setTicks(ticks)

    def run_script(self, task_type):
        print(f"🚀 İşlem: {task_type}")
        self.runner = ScriptRunner(task_type)
        self.runner.finished_task.connect(lambda: self.load_ai_modules())
        self.runner.start()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())