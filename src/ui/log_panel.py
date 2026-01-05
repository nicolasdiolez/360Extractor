"""
Log Panel Widget for displaying application logs in the UI.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel
)
from PySide6.QtCore import Qt, Signal, Slot, QObject
from PySide6.QtGui import QTextCursor, QColor
import logging
from datetime import datetime


class LogHandler(logging.Handler, QObject):
    """
    Custom logging handler that emits signals for UI updates.
    """
    log_signal = Signal(str, str)  # message, level
    
    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        
    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg, record.levelname)


class LogPanel(QWidget):
    """
    A collapsible log panel that displays application logs.
    """
    
    LEVEL_COLORS = {
        "DEBUG": "#6B7280",
        "INFO": "#A1A1AA",
        "WARNING": "#F59E0B",
        "ERROR": "#EF4444",
        "CRITICAL": "#DC2626"
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._max_lines = 500
        
        self.setObjectName("logPanel")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header bar (always visible)
        self.header = QWidget()
        self.header.setObjectName("logHeader")
        self.header.setFixedHeight(32)
        self.header.setCursor(Qt.PointingHandCursor)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        
        self.title_label = QLabel("📋 Logs")
        self.title_label.setStyleSheet("color: #A1A1AA; font-size: 12px;")
        
        self.toggle_btn = QPushButton("▲")
        self.toggle_btn.setFixedSize(24, 24)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #52525B;
                border: none;
                font-size: 10px;
            }
            QPushButton:hover {
                color: #A1A1AA;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_expanded)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedSize(50, 20)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #27272A;
                color: #71717A;
                border: none;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background: #3B82F6;
                color: white;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_logs)
        
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.clear_btn)
        header_layout.addWidget(self.toggle_btn)
        
        layout.addWidget(self.header)
        
        # Log content (expandable)
        self.log_content = QWidget()
        self.log_content.setObjectName("logContent")
        content_layout = QVBoxLayout(self.log_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("logText")
        self.log_text.setStyleSheet("""
            QTextEdit#logText {
                background-color: #0D0D0F;
                color: #A1A1AA;
                border: none;
                font-family: "SF Mono", "Consolas", "Monaco", monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)
        content_layout.addWidget(self.log_text)
        
        layout.addWidget(self.log_content)
        
        # Start collapsed
        self.log_content.setFixedHeight(0)
        self.log_content.hide()
        
        # Style the header
        self.header.setStyleSheet("""
            QWidget#logHeader {
                background-color: #18181B;
                border-top: 1px solid #27272A;
            }
        """)
        
        # Setup logging handler
        self._setup_logging()
        
    def _setup_logging(self):
        """Install our custom handler on the root logger."""
        self.log_handler = LogHandler()
        self.log_handler.setFormatter(
            logging.Formatter('[%(levelname)s] %(message)s')
        )
        self.log_handler.log_signal.connect(self._append_log)
        
        # Add to root logger and Application360 logger
        logging.getLogger().addHandler(self.log_handler)
        logging.getLogger("Application360").addHandler(self.log_handler)
        
    @Slot(str, str)
    def _append_log(self, message, level):
        """Append a log message with appropriate color."""
        color = self.LEVEL_COLORS.get(level, "#A1A1AA")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        html = f'<span style="color: #52525B;">{timestamp}</span> <span style="color: {color};">{message}</span><br>'
        
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html)
        
        # Auto-scroll to bottom
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()
        
        # Limit lines
        doc = self.log_text.document()
        if doc.blockCount() > self._max_lines:
            cursor = QTextCursor(doc.firstBlock())
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # Remove newline
            
        # Update title with count if collapsed
        if not self._expanded:
            self.title_label.setText(f"📋 Logs ({doc.blockCount()})")
    
    def toggle_expanded(self):
        """Toggle the expanded state of the log panel."""
        self._expanded = not self._expanded
        
        if self._expanded:
            self.log_content.show()
            self.log_content.setFixedHeight(150)
            self.toggle_btn.setText("▼")
            self.title_label.setText("📋 Logs")
        else:
            self.log_content.hide()
            self.log_content.setFixedHeight(0)
            self.toggle_btn.setText("▲")
            
    def clear_logs(self):
        """Clear all logs."""
        self.log_text.clear()
        self.title_label.setText("📋 Logs")
        
    def log(self, message, level="INFO"):
        """Manually add a log message."""
        self._append_log(f"[{level}] {message}", level)
