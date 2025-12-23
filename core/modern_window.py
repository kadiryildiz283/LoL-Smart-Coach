import sys
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QLabel, 
                             QPushButton, QVBoxLayout, QApplication, QFrame)
from PyQt6.QtCore import Qt, QPoint, QSize
from PyQt6.QtGui import QColor, QIcon, QFont

class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(40)
        self.setStyleSheet("background-color: transparent;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 5, 0)
        layout.setSpacing(10)
        
        # Icon
        self.icon_label = QLabel()
        # Fallback or pass icon later
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setStyleSheet("background-color: transparent;")
        
        # Title
        self.title_label = QLabel("LoL Smart Coach - Premium")
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #c9d1d9; background-color: transparent;")
        
        # Buttons
        self.btn_min = self.create_nav_btn("-", "#4cb2ff", self.minimize_window)
        self.btn_close = self.create_nav_btn("X", "#ff5252", self.close_window)
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_close)
        
        self.start = QPoint(0, 0)
        self.pressing = False

    def create_nav_btn(self, text, hover_color, func):
        btn = QPushButton(text)
        btn.setFixedSize(30, 30)
        btn.clicked.connect(func)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #8b949e;
                border: none;
                font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                color: white;
            }}
        """)
        return btn

    def minimize_window(self):
        self.parent.showMinimized()

    def close_window(self):
        self.parent.close()

    def mousePressEvent(self, event):
        self.start = self.mapToGlobal(event.pos())
        self.pressing = True

    def mouseMoveEvent(self, event):
        if self.pressing:
            end = self.mapToGlobal(event.pos())
            movement = end - self.start
            self.parent.setGeometry(self.parent.x() + movement.x(),
                                  self.parent.y() + movement.y(),
                                  self.parent.width(),
                                  self.parent.height())
            self.start = end

    def mouseReleaseEvent(self, event):
        self.pressing = False

class ModernWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Frameless and Transparent
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Central Container (The actual window content wrapper)
        self.central_container = QWidget()
        self.central_container.setObjectName("CentralContainer")
        # Modern glassmorphism dark background with gradient
        self.central_container.setStyleSheet("""
            #CentralContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0d1117, stop:1 #161b22);
                border: 1px solid #30363d;
                border-radius: 12px;
            }
        """)
        self.setCentralWidget(self.central_container)
        
        self.main_layout = QVBoxLayout(self.central_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Title Bar
        self.title_bar = CustomTitleBar(self)
        self.main_layout.addWidget(self.title_bar)
        
        # Content Area (Children will add here)
        self.content_widget = QWidget()
        self.main_layout.addWidget(self.content_widget)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        if hasattr(self, 'title_bar'):
            self.title_bar.title_label.setText(title)

    def setWindowIcon(self, icon):
        super().setWindowIcon(icon)
        # In a real app, ideally convert QIcon to pixmap for label
        # Keeping it simple for now
