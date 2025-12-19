from PyQt6.QtWidgets import QWidget, QLabel, QFrame, QVBoxLayout, QPushButton, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QPointF, QSize, pyqtSignal
from PyQt6.QtGui import QPainter, QPolygonF, QColor, QPen, QBrush, QPainterPath, QFont

class HexagonWidget(QWidget):
    """
    Altıgen şeklinde bir avatar/slot widget'ı.
    """
    def __init__(self, size=80, color="#1e1e1e", border_color="#00bcd4", parent=None):
        super().__init__(parent)
        self.setFixedSize(size, int(size * 1.15)) # Altıgen oranı
        self.color = QColor(color)
        self.border_color = QColor(border_color)
        self.text = "..."
        self.champ_name = ""
        
        # Gölge efekti (Neon glow benzeri)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(self.border_color)
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

    def set_champ(self, name):
        self.champ_name = name
        if name in ["Picking...", "Unknown", "...", "None"]:
            self.text = "Seçiliyor"
            self.border_color = QColor("#444")
            self.color = QColor("#1e1e1e")
        else:
            self.text = name
            # Takım rengine göre border (dışarıdan setlenmeli ama varsayılan parlak)
            # self.border_color = QColor("#00e676") 
        self.update()

    def set_color_theme(self, bg, border):
        self.color = QColor(bg)
        self.border_color = QColor(border)
        effect = self.graphicsEffect()
        if effect:
            effect.setColor(self.border_color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Altıgen Çizimi
        path = QPainterPath()
        w = float(self.width())
        h = float(self.height())
        
        # Noktalar (Düzgün Altıgen)
        #      1
        #   6     2
        #   5     3
        #      4
        
        points = [
            QPointF(w / 2.0, 0.0),               # 1
            QPointF(w, h * 0.25),               # 2
            QPointF(w, h * 0.75),               # 3
            QPointF(w / 2.0, h),                 # 4
            QPointF(0.0, h * 0.75),             # 5
            QPointF(0.0, h * 0.25)              # 6
        ]
        
        poly = QPolygonF(points)
        path.addPolygon(poly)

        # Dolgu
        painter.setBrush(QBrush(self.color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        # Kenarlık
        pen = QPen(self.border_color)
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawPath(path)

        # Metin (Şampiyon Adı)
        painter.setPen(QColor("white"))
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(font)
        
        # Metni ortala (basitçe)
        rect = self.rect()
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)

class ModernButton(QPushButton):
    def __init__(self, text, color="#00bcd4", parent=None):
        super().__init__(text, parent)
        self.default_color = color
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color}20; 
                color: {color};
                border: 1px solid {color};
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{
                background-color: {color}50;
                color: white;
            }}
            QPushButton:pressed {{
                background-color: {color};
                color: black;
            }}
        """)
