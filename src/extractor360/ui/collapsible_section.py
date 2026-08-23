"""
Collapsible Section & Drawer Widgets for 360 Extractor Studio.
Provides clean collapsible cards and progressive disclosure sub-drawers.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFrame
)
from PySide6.QtCore import Qt


class CollapsibleDrawer(QFrame):
    """
    A lightweight, minimalist collapsible drawer for progressive disclosure.
    Default state is collapsed (checked=False).
    """
    def __init__(self, title="Advanced Options", parent=None, is_open=False):
        super().__init__(parent)
        self.setObjectName("advancedDrawer")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 0)
        self._layout.setSpacing(4)

        self._title_text = title

        # Header Toggle Button
        arrow = "▼" if is_open else "▶"
        self.toggle_btn = QPushButton(f"{arrow}  {title}")
        self.toggle_btn.setObjectName("disclosureBtn")
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(is_open)
        self.toggle_btn.clicked.connect(self._on_toggled)
        self._layout.addWidget(self.toggle_btn)

        # Content container
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(6, 4, 2, 2)
        self.content_layout.setSpacing(6)
        self.content_widget.setVisible(is_open)
        self._layout.addWidget(self.content_widget)

    def _on_toggled(self, checked: bool):
        self.content_widget.setVisible(checked)
        arrow = "▼" if checked else "▶"
        self.toggle_btn.setText(f"{arrow}  {self._title_text}")

    def addWidget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def addLayout(self, layout):
        self.content_layout.addLayout(layout)

    def setExpanded(self, expanded: bool):
        self.toggle_btn.setChecked(expanded)
        self._on_toggled(expanded)

    def isExpanded(self) -> bool:
        return self.toggle_btn.isChecked()


class CollapsibleSection(QWidget):
    """
    A card-style collapsible section for inspector groups.
    """
    def __init__(self, title="Section", parent=None, is_open=True):
        super().__init__(parent)
        self._is_expanded = is_open
        self._title_text = title

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Header button
        arrow = "▼" if is_open else "▶"
        self._header = QPushButton(f"  {arrow}  {title}")
        self._header.setObjectName("collapsibleHeader")
        self._header.setCheckable(True)
        self._header.setChecked(is_open)
        self._header.clicked.connect(self._toggle)
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.setStyleSheet("""
            QPushButton#collapsibleHeader {
                background-color: #1F1F26;
                border: 1px solid #2C2C38;
                border-radius: 6px;
                color: #E8E8EE;
                font-size: 11px;
                font-weight: 600;
                padding: 8px 12px;
                text-align: left;
            }
            QPushButton#collapsibleHeader:hover {
                background-color: #262630;
                border-color: #F59E0B;
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
                background-color: #1D1D24;
                border: 1px solid #292934;
                border-top: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                padding: 6px 10px;
            }
        """)

        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(10, 8, 10, 8)
        self._content_layout.setSpacing(8)
        self._content.setVisible(is_open)

        self._main_layout.addWidget(self._content)

    def addWidget(self, widget: QWidget):
        self._content_layout.addWidget(widget)

    def addLayout(self, layout):
        self._content_layout.addLayout(layout)

    def contentLayout(self):
        return self._content_layout

    def _toggle(self):
        self._is_expanded = not self._is_expanded
        arrow = "▼" if self._is_expanded else "▶"
        self._header.setText(f"  {arrow}  {self._title_text}")
        self._content.setVisible(self._is_expanded)

    def setExpanded(self, expanded: bool):
        if self._is_expanded != expanded:
            self._toggle()

    def isExpanded(self) -> bool:
        return self._is_expanded
