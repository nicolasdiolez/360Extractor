"""
Modern Toggle Switch Widget for Qt applications.
A custom animated toggle switch to replace checkboxes.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, Property, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPainterPath


class ToggleSwitch(QWidget):
    """
    A modern animated toggle switch widget.
    """
    toggled = Signal(bool)

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._checked = False
        self._circle_position = 3  # Starting position (off)
        self._bg_color = QColor("#3C3C3C")
        
        # Animation for the circle movement
        self._animation = QPropertyAnimation(self, b"circle_position", self)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._animation.setDuration(200)
        
        # Layout with label
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        
        self._label = QLabel(text)
        self._label.setStyleSheet("color: #A1A1AA; font-size: 13px;")
        self._layout.addWidget(self._label)
        self._layout.addStretch()
        
        self.setFixedHeight(28)
        self.setCursor(Qt.PointingHandCursor)
        
    @Property(float)
    def circle_position(self):
        return self._circle_position
    
    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()
        
    def isChecked(self):
        return self._checked
    
    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self._animate()
            
    def setText(self, text):
        self._label.setText(text)
        
    def text(self):
        return self._label.text()
        
    def _animate(self):
        self._animation.stop()
        if self._checked:
            self._animation.setStartValue(self._circle_position)
            self._animation.setEndValue(25)  # On position
        else:
            self._animation.setStartValue(self._circle_position)
            self._animation.setEndValue(3)  # Off position
        self._animation.start()
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            self._animate()
            self.toggled.emit(self._checked)
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background track (right side of widget)
        track_width = 44
        track_height = 22
        track_x = self.width() - track_width
        track_y = (self.height() - track_height) // 2
        
        # Track color based on state
        if self._checked:
            track_color = QColor("#3B82F6")  # Electric blue
        else:
            track_color = QColor("#3C3C3C")  # Dark gray
            
        # Draw track
        path = QPainterPath()
        path.addRoundedRect(track_x, track_y, track_width, track_height, 11, 11)
        painter.fillPath(path, track_color)
        
        # Draw circle (handle)
        circle_size = 16
        circle_y = track_y + (track_height - circle_size) // 2
        circle_x = track_x + self._circle_position
        
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(int(circle_x), int(circle_y), circle_size, circle_size)
        
        painter.end()


class ToggleSwitchWithDescription(QWidget):
    """
    Toggle switch with a title and description text.
    """
    toggled = Signal(bool)
    
    def __init__(self, title="", description="", parent=None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(12)
        
        # Text container
        text_layout = QHBoxLayout()
        text_layout.setSpacing(4)
        
        self._title = QLabel(title)
        self._title.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 500;")
        text_layout.addWidget(self._title)
        
        if description:
            self._desc = QLabel(f"({description})")
            self._desc.setStyleSheet("color: #52525B; font-size: 11px;")
            text_layout.addWidget(self._desc)
        
        text_layout.addStretch()
        layout.addLayout(text_layout)
        
        # Toggle
        self._toggle = ToggleSwitch("", self)
        self._toggle.toggled.connect(self.toggled.emit)
        layout.addWidget(self._toggle)
        
    def isChecked(self):
        return self._toggle.isChecked()
    
    def setChecked(self, checked):
        self._toggle.setChecked(checked)
