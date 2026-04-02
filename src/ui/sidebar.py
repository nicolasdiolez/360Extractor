from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, 
    QSizePolicy, QHBoxLayout, QFrame
)
from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QIcon, QFont, QColor, QPainter

from core.version import VERSION
from ui.icons import get_icon

class SidebarButton(QPushButton):
    """A styled sidebar navigation button with premium hover effects."""
    
    def __init__(self, icon_name, label, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._label = label
        self._active = False
        
        self.setText(f"  {label}")
        self.setIcon(get_icon(icon_name, color="#71717A", size=20))
        self.setIconSize(QSize(20, 20))
        
        self.setCheckable(True)
        self.setFixedHeight(48)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()
        
    def _update_style(self):
        if self._active:
            self.setIcon(get_icon(self._icon_name, color="#3B82F6", size=20))
            self.setStyleSheet("""
                QPushButton {
                    background-color: rgba(59, 130, 246, 0.08);
                    border: none;
                    border-radius: 8px;
                    color: #3B82F6;
                    font-size: 13px;
                    font-weight: 600;
                    padding-left: 16px;
                    text-align: left;
                    margin: 2px 10px;
                }
            """)
        else:
            self.setIcon(get_icon(self._icon_name, color="#71717A", size=20))
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 8px;
                    color: #71717A;
                    font-size: 13px;
                    font-weight: 500;
                    padding-left: 16px;
                    text-align: left;
                    margin: 2px 10px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.03);
                    color: #E4E4E7;
                }
            """)
            
    def setActive(self, active):
        self._active = active
        self.setChecked(active)
        self._update_style()

    def enterEvent(self, event):
        if not self._active:
            self.setIcon(get_icon(self._icon_name, color="#E4E4E7", size=20))
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._active:
            self.setIcon(get_icon(self._icon_name, color="#71717A", size=20))
        super().leaveEvent(event)


class Sidebar(QWidget):
    """
    Navigation sidebar with icon buttons and a modern aesthetic.
    """
    page_changed = Signal(str)
    
    PAGES = [
        ("video", "Videos", "videos"),
        ("settings", "Settings", "settings"),
        ("export", "Export", "export"),
        ("advanced", "Advanced", "advanced"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Logo Section
        header = QWidget()
        header.setFixedHeight(100)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(12)
        
        logo_container = QFrame()
        logo_container.setFixedSize(32, 32)
        logo_container.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:1 #2563EB);
            border-radius: 8px;
        """)
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(6, 6, 6, 6)
        
        logo_icon = QLabel()
        logo_icon.setPixmap(get_icon("logo", color="#FFFFFF", size=20).pixmap(20, 20))
        logo_layout.addWidget(logo_icon)
        
        header_layout.addWidget(logo_container)
        
        title_container = QVBoxLayout()
        title_container.setSpacing(0)
        
        title = QLabel("360 Extractor")
        title.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: 700; letter-spacing: -0.3px;")
        
        title_container.addStretch()
        title_container.addWidget(title)
        title_container.addStretch()
        
        header_layout.addLayout(title_container)
        header_layout.addStretch()
        
        layout.addWidget(header)
        
        # Divider
        # line = QFrame()
        # line.setFrameShape(QFrame.HLine)
        # line.setStyleSheet("background-color: #121214; margin: 0 20px;")
        # layout.addWidget(line)
        # layout.addSpacing(10)
        
        # Navigation groups
        nav_label = QLabel("MAIN MENU")
        nav_label.setStyleSheet("color: #3F3F46; font-size: 10px; font-weight: 700; letter-spacing: 1px; margin: 10px 24px;")
        layout.addWidget(nav_label)
        
        # Navigation buttons
        self._buttons = {}
        for icon_name, label, page_id in self.PAGES:
            btn = SidebarButton(icon_name, label)
            btn.clicked.connect(lambda checked, p=page_id: self._on_button_clicked(p))
            self._buttons[page_id] = btn
            layout.addWidget(btn)
            
        layout.addStretch()
        
        # Footer
        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(24, 24, 24, 24)
        
        version = QLabel(f"Version {VERSION}")
        version.setStyleSheet("color: #3F3F46; font-size: 11px; font-weight: 500;")
        version.setAlignment(Qt.AlignCenter)
        footer_layout.addWidget(version)
        
        layout.addWidget(footer)
        
        # Set initial active
        self.setActivePage("videos")
        
    def _on_button_clicked(self, page_id):
        self.setActivePage(page_id)
        self.page_changed.emit(page_id)
        
    def setActivePage(self, page_id):
        for pid, btn in self._buttons.items():
            btn.setActive(pid == page_id)
