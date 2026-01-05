"""
Sidebar Navigation Widget for the main window.
Modern navigation sidebar with icons and labels.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, 
    QSizePolicy, QHBoxLayout
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QFont


class SidebarButton(QPushButton):
    """A styled sidebar navigation button."""
    
    def __init__(self, icon_text, label, parent=None):
        super().__init__(parent)
        self._icon_text = icon_text
        self._label = label
        self._active = False
        
        self.setText(f"{icon_text}  {label}")
        self.setCheckable(True)
        self.setFixedHeight(48)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()
        
    def _update_style(self):
        if self._active:
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
        ("📹", "Videos", "videos"),
        ("⚙️", "Settings", "settings"),
        ("📤", "Export", "export"),
        ("🧪", "Advanced", "advanced"),
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
        
        logo = QLabel("🌐")
        logo.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(logo)
        
        title = QLabel("360 Extractor")
        title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: 600;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        layout.addWidget(header)
        
        # Navigation buttons
        self._buttons = {}
        for icon, label, page_id in self.PAGES:
            btn = SidebarButton(icon, label)
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
