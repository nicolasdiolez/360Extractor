from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, 
    QSizePolicy, QHBoxLayout
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QFont

from ui.icons import get_icon

class SidebarButton(QPushButton):
    """A styled sidebar navigation button."""
    
    def __init__(self, icon_name, label, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._label = label
        self._active = False
        
        self.setText(f"  {label}")
        self.setIcon(get_icon(icon_name, color="#A1A1AA", size=20))
        self.setIconSize(QSize(20, 20))
        
        self.setCheckable(True)
        self.setFixedHeight(48)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()
        
    def _update_style(self):
        if self._active:
            # Active State
            self.setIcon(get_icon(self._icon_name, color="#3B82F6", size=20))
            self.setStyleSheet("""
                QPushButton {
                    background-color: rgba(59, 130, 246, 0.15);
                    border: none;
                    border-left: 3px solid #3B82F6;
                    border-radius: 0px;
                    color: #3B82F6;
                    font-size: 14px;
                    font-weight: 500;
                    padding-left: 20px;
                    text-align: left;
                }
            """)
        else:
            # Inactive State
            self.setIcon(get_icon(self._icon_name, color="#A1A1AA", size=20))
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 0px;
                    color: #A1A1AA;
                    font-size: 14px;
                    padding-left: 20px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.05);
                    color: #FFFFFF;
                }
            """)
            
    def setActive(self, active):
        self._active = active
        self.setChecked(active)
        self._update_style()


class Sidebar(QWidget):
    """
    Navigation sidebar with icon buttons.
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
        self.setFixedWidth(200)
        self.setStyleSheet("""
            QWidget#sidebar {
                background-color: #0D0D0F;
                border-right: 1px solid #1E1E22;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Logo / App name
        header = QWidget()
        header.setStyleSheet("background-color: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 20, 20, 30)
        
        logo = QLabel()
        logo.setPixmap(get_icon("logo", color="#3B82F6", size=28).pixmap(28, 28))
        header_layout.addWidget(logo)
        
        title = QLabel("360 Extractor")
        title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: 600;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        layout.addWidget(header)
        
        # Navigation buttons
        self._buttons = {}
        for icon_name, label, page_id in self.PAGES:
            btn = SidebarButton(icon_name, label)
            btn.clicked.connect(lambda checked, p=page_id: self._on_button_clicked(p))
            self._buttons[page_id] = btn
            layout.addWidget(btn)
            
        layout.addStretch()
        
        # Version footer
        version = QLabel("v2.0.0")
        version.setStyleSheet("color: #52525B; font-size: 11px; padding: 20px;")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)
        
        # Set initial active
        self.setActivePage("videos")
        
    def _on_button_clicked(self, page_id):
        self.setActivePage(page_id)
        self.page_changed.emit(page_id)
        
    def setActivePage(self, page_id):
        for pid, btn in self._buttons.items():
            btn.setActive(pid == page_id)
