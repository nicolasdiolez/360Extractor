from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, Signal, QMimeData, QSize
from ui.icons import get_icon

class DropZone(QFrame):
    """
    A premium custom widget that accepts drag-and-drop file inputs with visual feedback.
    """
    files_dropped = Signal(list)
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(120)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        
        self.icon_label = QLabel()
        self.icon_label.setPixmap(get_icon("video", color="#52525B", size=32).pixmap(32, 32))
        self.icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_label)
        
        self.text_label = QLabel("Drag & Drop 360° Videos\nor Click to Browse")
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setStyleSheet("color: #52525B; font-size: 13px; font-weight: 500;")
        layout.addWidget(self.text_label)
        
        self.setProperty("dragActive", False)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
            self.setProperty("dragActive", True)
            self.style().polish(self)
            self.text_label.setText("Drop them here!")
            self.text_label.setStyleSheet("color: #3B82F6; font-size: 13px; font-weight: 600;")
            self.icon_label.setPixmap(get_icon("video", color="#3B82F6", size=32).pixmap(32, 32))
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().polish(self)
        self.text_label.setText("Drag & Drop 360° Videos\nor Click to Browse")
        self.text_label.setStyleSheet("color: #52525B; font-size: 13px; font-weight: 500;")
        self.icon_label.setPixmap(get_icon("video", color="#52525B", size=32).pixmap(32, 32))

    def dropEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().polish(self)
        
        files = []
        for url in event.mimeData().urls():
            files.append(url.toLocalFile())
        
        if files:
            self.files_dropped.emit(files)
            self.text_label.setText(f"{len(files)} files added")
        else:
            self.text_label.setText("Drag & Drop 360° Videos\nor Click to Browse")
            
        self.text_label.setStyleSheet("color: #52525B; font-size: 13px; font-weight: 500;")
        self.icon_label.setPixmap(get_icon("video", color="#52525B", size=32).pixmap(32, 32))
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)