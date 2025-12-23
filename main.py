import sys
import os
import asyncio
import traceback
import warnings
import json

# --- 1. SETTINGS ---
warnings.filterwarnings("ignore", category=DeprecationWarning)

import qdarktheme
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QFrame, QMessageBox, QPlainTextEdit,
                             QComboBox, QSizePolicy, QScrollArea, QGridLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QIcon, QTextCursor, QColor

# --- MODULES ---
from core.modern_window import ModernWindow
from core.ui_components import HexagonWidget, ModernButton, RoleIndicator, SuggestionCard
from core.data_manager import ensure_data_directory, get_resource_path
import pyqtgraph as pg

# --- 2. GLOBAL EXCEPTION HANDLER ---
def global_exception_handler(exctype, value, tb):
    if "log_output" in str(value):
        sys.__stdout__.write(f"Startup Log Error: {value}\n")
        return
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    sys.__stdout__.write(f"CRITICAL ERROR:\n{error_msg}\n")
    try:
        if QApplication.instance():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("Unexpected Error")
            msg.setDetailedText(error_msg)
            msg.exec()
    except: pass

sys.excepthook = global_exception_handler

# --- 3. IMPORTS ---
try:
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
    print(f"⚠️ Module Missing: {e}")

# --- 5. LOG SYSTEM ---
class EmittingStream(QObject):
    textWritten = pyqtSignal(str)
    def write(self, text):
        if text: self.textWritten.emit(str(text))
    def flush(self): pass

# --- 6. BACKGROUND WORKER ---
class ScriptRunner(QThread):
    finished_task = pyqtSignal()
    def __init__(self, task_type):
        super().__init__()
        self.task_type = task_type

    def run(self):
        try:
            if self.task_type == "scrape_data":
                print("⏳ Fetching stats..."); veri_cekici_main.main()
            elif self.task_type == "merge_all":
                print("ℹ️ Merging data..."); expert_parser.main(); merge_expert_data.main(); merge_damage_stats.main()
                print("🎉 Database Ready.")
        except Exception as e: print(f"❌ ERROR: {str(e)}")
        self.finished_task.emit()

# --- 8. MAIN WINDOW ---
class MainWindow(ModernWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoL Smart Coach - Premium Edition")
        self.resize(1350, 850)
        self.setWindowIcon(QIcon(get_resource_path("assets/logo.ico")))

        # Paths
        self.data_path = get_resource_path(os.path.join("data", "tum_sampiyonlar_verisi_full.json"))
        
        self.ai_engine = None
        self.match_predictor = None
        self.current_role = "Unknown" 
        self.current_my_team = []
        self.current_enemy_team = []

        self.setup_ui()
        self.apply_styles()

        # Logger
        self.terminal_stream = EmittingStream()
        self.terminal_stream.textWritten.connect(self.append_terminal_text)
        sys.stdout = self.terminal_stream
        sys.stderr = self.terminal_stream
        
        print("⚙️ System starting...")
        self.load_ai_modules()

        # LCU
        try:
            self.lcu_thread = LCUWorker()
            self.lcu_thread.connection_status.connect(self.update_connection_status)
            self.lcu_thread.champ_select_update.connect(self.handle_champ_select) 
            self.lcu_thread.start()
        except Exception as e: print(f"LCU Error: {e}")

    def setup_ui(self):
        """
        New Layout:
        - Top: Title Bar (Handled by ModernWindow) -> We add content below title bar.
        - Header: Status & Playstyle
        - Center: 
            [Left: Team Blue (Hexagons)] 
            [Center: ROLE INDICATOR + Chart] 
            [Right: Team Red (Hexagons)]
        - Bottom: Suggestion List (Cards)
        - Footer: Log & Controls
        """
        # We work on self.content_widget created by ModernWindow
        # FIX: Do not create new layout, retrieve existing one
        layout = self.content_layout
        # layout = QVBoxLayout(self.content_widget) # This was the bug
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(15)

        # --- 1. HEADER BAR (Game Info) ---
        header_layout = QHBoxLayout()
        
        self.lbl_status = QLabel("Waiting for Client...")
        self.lbl_status.setStyleSheet("color: #8b949e; font-weight: bold;")
        
        self.combo_playstyle = QComboBox()
        self.combo_playstyle.addItems(["Balanced", "Safe", "Aggressive"])
        self.combo_playstyle.setFixedWidth(120)
        self.combo_playstyle.currentIndexChanged.connect(self.change_playstyle)
        
        header_layout.addWidget(QLabel("Playstyle:", styleSheet="color:#8b949e"))
        header_layout.addWidget(self.combo_playstyle)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_status)
        
        layout.addLayout(header_layout)

        # --- 2. MAIN AREA (Teams + Indicator) ---
        main_area = QHBoxLayout()
        main_area.setSpacing(20)
        
        # LEFT: My Team
        team_blue_layout = QVBoxLayout()
        team_blue_layout.setSpacing(10)
        self.blue_slots = []
        for i in range(5):
            h = HexagonWidget(size=70, color="#1e3a8a", border_color="#3b82f6")
            self.blue_slots.append(h)
            team_blue_layout.addWidget(h, alignment=Qt.AlignmentFlag.AlignHCenter)
        main_area.addLayout(team_blue_layout)
        
        # CENTER: Role & Graph
        center_col = QVBoxLayout()
        center_col.setSpacing(20)
        
        # Role Indicator
        self.role_indicator = RoleIndicator()
        center_col.addWidget(self.role_indicator, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Chart
        self.bar_chart = pg.PlotWidget()
        self.bar_chart.setBackground(None)
        self.bar_chart.showGrid(x=False, y=True, alpha=0.3)
        self.bar_chart.getAxis('bottom').setTicks([[]])
        self.bar_chart.setTitle("Power Analysis", color="w", size="10pt")
        self.bar_chart.setFixedHeight(200)
        center_col.addWidget(self.bar_chart)
        
        main_area.addLayout(center_col, stretch=2)
        
        # RIGHT: Enemy Team
        team_red_layout = QVBoxLayout()
        team_red_layout.setSpacing(10)
        self.red_slots = []
        for i in range(5):
            h = HexagonWidget(size=70, color="#7f1d1d", border_color="#ef4444")
            self.red_slots.append(h)
            team_red_layout.addWidget(h, alignment=Qt.AlignmentFlag.AlignHCenter)
        main_area.addLayout(team_red_layout)
        
        layout.addLayout(main_area)

        # --- 3. SUGGESTIONS (Cards) ---
        suggestions_header = QHBoxLayout()
        suggestions_header.addWidget(QLabel("AI Recommendations", styleSheet="font-size: 16px; font-weight: bold; color: #e6edf3;"))
        
        # Enemy Laner Selector
        self.combo_enemy_laner = QComboBox()
        self.combo_enemy_laner.addItem("Select Opponent")
        self.combo_enemy_laner.setFixedWidth(200)
        self.combo_enemy_laner.currentIndexChanged.connect(self.re_run_analysis_from_ui)
        suggestions_header.addStretch()
        suggestions_header.addWidget(QLabel("Lane Opponent:", styleSheet="color: #8b949e"))
        suggestions_header.addWidget(self.combo_enemy_laner)
        
        layout.addLayout(suggestions_header)
        
        # Scroll Area for Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;") # Transparent scroll area
        
        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch() # Push items up
        
        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll, stretch=1)

        # --- 4. CONTROLS & LOG ---
        footer_layout = QHBoxLayout()
        
        # Buttons
        b_reset = ModernButton("RESET", "#ff5252")
        b_reset.clicked.connect(self.reset_ui_state)
        b_update = ModernButton("Update Data", "#2f81f7")
        b_update.clicked.connect(lambda: self.run_script("scrape_data"))
        b_merge = ModernButton("Merge Data", "#a371f7")
        b_merge.clicked.connect(lambda: self.run_script("merge_all"))
        b_force = ModernButton("Force Analyze", "#d29922")
        b_force.clicked.connect(self.force_recommendation)
        
        footer_layout.addWidget(b_reset)
        footer_layout.addWidget(b_update)
        footer_layout.addWidget(b_merge)
        footer_layout.addWidget(b_force)
        
        layout.addLayout(footer_layout)
        
        # Log (Hidden by default or minimized?) Let's keep it small at bottom
        self.log_output = QPlainTextEdit()
        self.log_output.setFixedHeight(60)
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #010409; color: #3fb950; border: 1px solid #30363d; border-radius: 4px; font-family: Consolas;")
        layout.addWidget(self.log_output)

    def apply_styles(self):
        try: qdarktheme.setup_theme("dark")
        except: pass
        
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI'; }
            QComboBox { background-color: #21262d; color: #c9d1d9; border: 1px solid #30363d; padding: 5px; border-radius: 4px; }
            QComboBox QAbstractItemView { background-color: #21262d; color: #c9d1d9; }
            QScrollBar:vertical { background: #0d1117; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: #30363d; min-height: 20px; border-radius: 5px; }
        """)

    def load_ai_modules(self):
        if os.path.exists(self.data_path):
            try:
                self.ai_engine = LoLDecisionEngine(self.data_path)
                self.match_predictor = LoLMatchPredictor(self.data_path)
                print(f"✅ AI Modules Loaded.")
            except: print("❌ Failed to load AI modules.")
        else: print("⚠️ Data not found! Please Merge.")

    def reset_ui_state(self):
        print("\n🗑️ Resetting UI State.")
        self.current_role = "Unknown"
        self.current_my_team = []
        self.current_enemy_team = []
        
        self.role_indicator.set_role("UNKNOWN")
        self.combo_enemy_laner.clear()
        self.combo_enemy_laner.addItem("Select Opponent")
        
        for slot in self.blue_slots: slot.set_champ("...")
        for slot in self.red_slots: slot.set_champ("...")
        
        self.bar_chart.clear()
        
        # Clear Cards
        self.clear_suggestions()
        
        try:
            self.lcu_thread.stop() 
            self.lcu_thread = LCUWorker()
            self.lcu_thread.connection_status.connect(self.update_connection_status)
            self.lcu_thread.champ_select_update.connect(self.handle_champ_select) 
            self.lcu_thread.start()
        except: pass

    def clear_suggestions(self):
        # Remove all widgets from cards_layout
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.cards_layout.addStretch()

    def update_connection_status(self, msg):
        self.lbl_status.setText(msg)
        if "Bağlandı" in msg or "Connected" in msg: 
            self.lbl_status.setStyleSheet("color: #3fb950; font-weight: bold;")
        else: 
            self.lbl_status.setStyleSheet("color: #f85149;")

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
        if "Select" in target_enemy: target_enemy = None
        
        role = self.current_role
        if role.lower() in ["unknown", "belirsiz", "none", ""]: role = "mid"
        
        if self.ai_engine:
            self.run_ai_analysis(role, target_enemy, self.current_my_team, self.current_enemy_team)

    def change_playstyle(self, index):
        styles = ["balanced", "safe", "aggressive"]
        if 0 <= index < len(styles):
            selected = styles[index]
            self.ai_engine.set_profile(selected)
            self.append_terminal_text(f"🧠 Playstyle: {selected.upper()}")
            if self.combo_enemy_laner.currentIndex() > 0:
                self.re_run_analysis_from_ui(0)

    def force_recommendation(self):
        print("\n⚡ Manual Trigger.")
        role = self.current_role
        if role in ["Unknown", "Belirsiz", "None", ""]: role = "Mid"
        
        target = self.combo_enemy_laner.currentText()
        if "Select" in target: target = None
        
        self.run_ai_analysis(role, target, self.current_my_team, self.current_enemy_team)

    def handle_champ_select(self, data):
        my_team = data.get('my_team', [])
        enemy_team = data.get('enemy_team', [])
        my_role = data.get('my_role', 'Unknown')
        
        self.current_role = str(my_role)
        self.current_my_team = my_team
        self.current_enemy_team = enemy_team
        
        self.role_indicator.set_role(self.current_role)
        
        # Update Hexagons
        for i in range(5):
            name = my_team[i] if i < len(my_team) else "..."
            self.blue_slots[i].set_champ(name)
        for i in range(5):
            name = enemy_team[i] if i < len(enemy_team) else "..."
            self.red_slots[i].set_champ(name)
            
        # Update Enemy List
        current_selection = self.combo_enemy_laner.currentText()
        self.combo_enemy_laner.currentIndexChanged.disconnect(self.re_run_analysis_from_ui)
        self.combo_enemy_laner.clear()
        self.combo_enemy_laner.addItem("Select Opponent")
        real_enemies = [c for c in enemy_team if c not in ["Picking...", "Unknown", "...", "None"]]
        for e in real_enemies: self.combo_enemy_laner.addItem(e)
        
        if current_selection in real_enemies:
            self.combo_enemy_laner.setCurrentText(current_selection)
        self.combo_enemy_laner.currentIndexChanged.connect(self.re_run_analysis_from_ui)
        
        # Trigger Analysis
        target_enemy = self.combo_enemy_laner.currentText()
        if "Select" in target_enemy: target_enemy = None
        
        role = self.current_role
        if role.lower() in ["unknown", ""]: role = "mid"
        
        if self.ai_engine:
            self.run_ai_analysis(role, target_enemy, my_team, enemy_team)
            
        # Match Prediction
        if self.match_predictor:
            if self.is_team_complete(my_team) and self.is_team_complete(enemy_team):
                print("\n🏁 5v5 Locked! Predicting Match...")
                self.match_predictor.predict_match(my_team, enemy_team)

    def is_team_complete(self, team):
        if not team or len(team) < 5: return False
        for member in team:
            if member in ["Picking...", "Unknown", "...", "None", ""]: 
                return False
        return True

    def run_ai_analysis(self, my_role, enemy_laner, ally_team, enemy_team):
        print(f"💡 Analysis: Role={my_role}, VS={enemy_laner}")
        try:
            picks = self.ai_engine.calculate_score(my_role, enemy_laner, ally_team, enemy_team)
            
            # Clear previous suggestions
            self.clear_suggestions()
            
            if not picks:
                lbl = QLabel("No suggestions found.")
                lbl.setStyleSheet("color: #8b949e;")
                self.cards_layout.insertWidget(0, lbl)
                return

            # Add Cards
            top_scores = []
            top_names = []
            
            # Show top 10? User said "more appealing". 5-10 is good.
            # Let's show top 10 but visually distinct
            for i, p in enumerate(picks[:10], 1):
                narrative = p['reasons']
                score = p.get('score', 0)
                
                card = SuggestionCard(i, p['name'], p['class'], score, narrative)
                self.cards_layout.insertWidget(self.cards_layout.count()-1, card) # Insert before stretch
                
                if i <= 5: # Graph only top 5
                    top_names.append(p['name'])
                    top_scores.append(score)

            self.update_chart(top_names, top_scores)
            
        except Exception as e:
            print(f"AI Analysis Error: {e}")
            traceback.print_exc()

    def update_chart(self, names, scores):
        self.bar_chart.clear()
        bg = pg.BarGraphItem(x=range(len(scores)), height=scores, width=0.6, brush='#00bcd4')
        self.bar_chart.addItem(bg)
        ax = self.bar_chart.getAxis('bottom')
        ticks = [list(zip(range(len(names)), names))]
        ax.setTicks(ticks)

    def run_script(self, task_type):
        print(f"🚀 Task: {task_type}")
        self.runner = ScriptRunner(task_type)
        self.runner.finished_task.connect(lambda: self.load_ai_modules())
        self.runner.start()

if __name__ == "__main__":
    # High DPI Support
    os.environ["QT_FONT_DPI"] = "96"
    if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, 'PassThrough'):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())