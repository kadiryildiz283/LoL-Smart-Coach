from PyQt6.QtWidgets import (QWidget, QLabel, QFrame, QVBoxLayout, QPushButton, 
                             QGraphicsDropShadowEffect, QHBoxLayout, QSizePolicy)
from PyQt6.QtCore import (Qt, QPointF, QSize, pyqtSignal, QPropertyAnimation, 
                          QEasingCurve, QRect, QTimer, pyqtProperty)
from PyQt6.QtGui import (QPainter, QPolygonF, QColor, QPen, QBrush, 
                         QPainterPath, QFont, QRadialGradient)

class HexagonWidget(QWidget):
    def __init__(self, size=80, color="#1e1e1e", border_color="#00bcd4", parent=None):
        super().__init__(parent)
        self.setFixedSize(size, int(size * 1.15))
        self.color = QColor(color)
        self.border_color = QColor(border_color)
        self.text = "..."
        self.champ_name = ""
        
        # Shadow Effect
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(self.border_color)
        self.shadow.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow)

    def set_champ(self, name):
        self.champ_name = name
        if name in ["Picking...", "Unknown", "...", "None"]:
            self.text = "..."
            self.border_color = QColor("#30363d")
            self.color = QColor("#161b22")
            self.shadow.setColor(QColor(0,0,0,0)) # Hide shadow
        else:
            self.text = name
            # Colors will be managed by parent usually, but default behavior:
            # self.border_color = QColor("#00bcd4") 
            self.shadow.setColor(self.border_color)
        self.update()

    def set_color_theme(self, bg, border):
        self.color = QColor(bg)
        self.border_color = QColor(border)
        self.shadow.setColor(self.border_color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        
        path = QPainterPath()
        points = [
            QPointF(w/2, 0), QPointF(w, h*0.25), QPointF(w, h*0.75),
            QPointF(w/2, h), QPointF(0, h*0.75), QPointF(0, h*0.25)
        ]
        path.addPolygon(QPolygonF(points))

        # Fill
        grad = QRadialGradient(w/2, h/2, w/2)
        grad.setColorAt(0, self.color.lighter(120))
        grad.setColorAt(1, self.color)
        painter.setBrush(QBrush(grad))
        
        # Stroke
        pen = QPen(self.border_color)
        pen.setWidth(2)
        painter.setPen(pen)
        
        painter.drawPath(path)

        # Text
        if self.text:
            painter.setPen(QColor("white"))
            font = QFont("Segoe UI", 8, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)

class ModernButton(QPushButton):
    def __init__(self, text, color="#00bcd4", parent=None):
        super().__init__(text, parent)
        self.base_color = color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(self._get_style(color, 20))
        
        # Hover Animation Logic stub (QSS handles smooth transitions easier for buttons usually, 
        # but for advanced scaling we use QPropertyAnimation. Keeping it simple/robust with QSS + Logic)

    def _get_style(self, color, alpha):
        return f"""
            QPushButton {{
                background-color: {color}{alpha}; 
                color: {color};
                border: 1px solid {color};
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{
                background-color: {color}60;
                color: white;
            }}
            QPushButton:pressed {{
                background-color: {color};
                color: black;
            }}
        """

class RoleIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200)
        self.role_name = "Unknown"
        
        # Loading / Pulse Animation
        self._pulse_val = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._timer_tick)
        self.timer.start(50)
        self.direction = 1

    def set_role(self, role):
        self.role_name = role.upper() if role else "BELİRSİZ"
        self.update()

    def _timer_tick(self):
        self._pulse_val += 2 * self.direction
        if self._pulse_val >= 100: self.direction = -1
        if self._pulse_val <= 20: self.direction = 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        c = rect.center()
        
        # Pulse Circle
        alpha = 50 + self._pulse_val # 50-150 range
        color = QColor("#00e676")
        if self.role_name in ["UNKNOWN", "BELİRSİZ"]:
            color = QColor("#8b949e")
        
        color.setAlpha(alpha)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(c, 80, 80)
        
        # Inner Circle
        painter.setBrush(QBrush(QColor("#0d1117")))
        painter.drawEllipse(c, 70, 70)
        
        # Role Text
        painter.setPen(QColor(color.name())) # Full alpha text
        font = QFont("Segoe UI", 24, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.role_name)

class SuggestionCard(QFrame):
    """
    New animated card for AI suggestions.
    """
    def __init__(self, rank, name, champ_class, score, narrative, parent=None):
        super().__init__(parent)
        self.setFixedHeight(110)
        self.setStyleSheet("""
            QFrame {
                background-color: #21262d; 
                border-radius: 8px;
                border-left: 4px solid #00e676;
            }
            QFrame:hover {
                background-color: #30363d;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(5)
        
        # Top Row
        row1 = QHBoxLayout()
        rank_lbl = QLabel(f"#{rank} {name}")
        rank_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        rank_lbl.setStyleSheet("color: #00e676; border: none; background: transparent;")
        
        class_lbl = QLabel(f"({champ_class})")
        class_lbl.setStyleSheet("color: #8b949e; font-size: 11px; border: none; background: transparent;")
        
        score_lbl = QLabel(f"🏆 {score}")
        score_lbl.setStyleSheet("color: #ffab00; font-weight: bold; font-size: 13px; border: none; background: transparent;")
        
        row1.addWidget(rank_lbl)
        row1.addWidget(class_lbl)
        row1.addStretch()
        row1.addWidget(score_lbl)
        
        # Narrative
        desc_lbl = QLabel(narrative)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #c9d1d9; font-size: 12px; border: none; background: transparent;")
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        layout.addLayout(row1)
        layout.addWidget(desc_lbl)
        
        # Entrance Animation
        self.opacity_effect = QGraphicsDropShadowEffect(self) # Just a dummy to use graphics effect slot? No, use windowopacity or property
        # For widgets inside layout, PropertyAnimation on geometry or opacity effect is best.
        # But for simplicity in list, we usually just show. 
        # Let's add simple simple styling for now.
