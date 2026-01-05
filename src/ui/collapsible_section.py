"""
Collapsible Section Widget for Qt applications.
Animated expandable/collapsible sections for settings panels.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QFrame, QSizePolicy, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, Property
from PySide6.QtGui import QFont, QIcon


class CollapsibleSection(QWidget):
    """
    A collapsible section with animated expand/collapse.
    """
    
    def __init__(self, title="Section", parent=None):
        super().__init__(parent)
        self._is_expanded = True
        self._animation_duration = 200
        
        # Main layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        
        # Header button
        self._header = QPushButton(f"  ▼  {title}")
        self._header.setObjectName("collapsibleHeader")
        self._header.setCheckable(True)
        self._header.setChecked(True)
        self._header.clicked.connect(self._toggle)
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.setStyleSheet("""
            QPushButton#collapsibleHeader {
                background-color: #1E1E22;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 600;
                padding: 12px 16px;
                text-align: left;
            }
            QPushButton#collapsibleHeader:hover {
                background-color: #252529;
            }
            QPushButton#collapsibleHeader:checked {
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        self._main_layout.addWidget(self._header)
        
        # Content container
        self._content = QFrame()
        self._content.setObjectName("collapsibleContent")
        self._content.setStyleSheet("""
            QFrame#collapsibleContent {
                background-color: #161618;
                border: 1px solid #27272A;
                border-top: none;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                padding: 0px;
            }
        """)
        
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(16, 12, 16, 12)
        self._content_layout.setSpacing(12)
        
        self._main_layout.addWidget(self._content)
        
        # Animation
        self._animation = QPropertyAnimation(self._content, b"maximumHeight")
        self._animation.setDuration(self._animation_duration)
        self._animation.setEasingCurve(QEasingCurve.InOutQuad)
        
    def addWidget(self, widget):
        """Add a widget to the collapsible content."""
        self._content_layout.addWidget(widget)
        
    def addLayout(self, layout):
        """Add a layout to the collapsible content."""
        self._content_layout.addLayout(layout)
        
    def contentLayout(self):
        """Return the content layout for adding widgets."""
        return self._content_layout
        
    def _toggle(self):
        self._is_expanded = not self._is_expanded
        
        # Update header arrow
        title = self._header.text().replace("  ▼  ", "").replace("  ▶  ", "")
        if self._is_expanded:
            self._header.setText(f"  ▼  {title}")
        else:
            self._header.setText(f"  ▶  {title}")
        
        # Animate
        if self._is_expanded:
            self._animation.setStartValue(0)
            self._animation.setEndValue(self._content.sizeHint().height())
            self._content.show()
        else:
            self._animation.setStartValue(self._content.height())
            self._animation.setEndValue(0)
            
        self._animation.start()
        
        if not self._is_expanded:
            self._animation.finished.connect(self._content.hide)
        else:
            try:
                self._animation.finished.disconnect(self._content.hide)
            except:
                pass
                
    def setExpanded(self, expanded):
        if self._is_expanded != expanded:
            self._toggle()
            
    def isExpanded(self):
        return self._is_expanded
