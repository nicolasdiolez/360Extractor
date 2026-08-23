"""
Icon and Asset utilities for 360 Extractor Studio.
Provides vector Lucide icons and high-resolution App icon generation.
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap
)
from PySide6.QtSvg import QSvgRenderer

# Lucide Icons (MIT License) - Simplified SVG paths
ICONS = {
    "video": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2" ry="2"/></svg>""",
    "settings": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.1a2 2 0 0 1-1-1.72v-.51a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>""",
    "export": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>""",
    "advanced": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>""",
    "logo": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>""",
    "play": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor" stroke="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>""",
    "refresh": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>""",
    "x": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>""",
    "monitor": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="14" x="2" y="3" rx="2"/><line x1="8" x2="16" y1="21" y2="21"/><line x1="12" x2="12" y1="17" y2="21"/></svg>""",
    "eye": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>""",
    "folder": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>"""
}


def get_icon(name: str, color: str | None = None, size: int = 24) -> QIcon:
    """Generate a QIcon from the internal SVG library."""
    svg_data = ICONS.get(name)
    if not svg_data:
        return QIcon()

    if color:
        svg_data = svg_data.replace("currentColor", color)

    renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)


def get_pixmap(name: str, color: str | None = None, size: int = 24) -> QPixmap:
    """Return QPixmap directly from internal SVG library."""
    icon = get_icon(name, color, size)
    return icon.pixmap(size, size)


def get_app_icon() -> QIcon:
    """Generate a high-res app icon with graphite squircle and warm amber 360 globe."""
    icon = QIcon()
    for size in [16, 32, 64, 128, 256, 512]:
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # macOS Squircle Background
        radius = size * 0.22
        rect = QRectF(size * 0.04, size * 0.04, size * 0.92, size * 0.92)

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        # Dark Graphite Gradient
        grad = QLinearGradient(0, 0, size, size)
        grad.setColorAt(0.0, QColor("#22222A"))
        grad.setColorAt(1.0, QColor("#121216"))
        painter.fillPath(path, QBrush(grad))

        # Subtle Border
        border_pen = QPen(QColor("#363646"), max(1.0, size * 0.02))
        painter.strokePath(path, border_pen)

        # 360° Equirectangular Sphere in Warm Amber
        center_x = size / 2.0
        center_y = size / 2.0
        globe_r = size * 0.30

        # Glowing Outer Ring
        glow_pen = QPen(QColor("#F59E0B"), max(1.5, size * 0.04))
        painter.setPen(glow_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(center_x - globe_r, center_y - globe_r, globe_r * 2, globe_r * 2))

        # Meridian & Parallel lines
        meridian_pen = QPen(QColor("#FBBF24"), max(1.0, size * 0.025))
        painter.setPen(meridian_pen)
        painter.drawEllipse(QRectF(center_x - globe_r * 0.45, center_y - globe_r, globe_r * 0.9, globe_r * 2))
        painter.drawLine(center_x - globe_r, center_y, center_x + globe_r, center_y)

        # Central Lens Core
        painter.setBrush(QBrush(QColor("#D97706")))
        painter.setPen(QPen(QColor("#FFFFFF"), max(1.0, size * 0.02)))
        painter.drawEllipse(QRectF(center_x - size * 0.06, center_y - size * 0.06, size * 0.12, size * 0.12))

        # "360" text for large icons
        if size >= 128:
            painter.setPen(QColor("#FAF9F6"))
            font = QFont("-apple-system", int(size * 0.12), QFont.Bold)
            painter.setFont(font)
            painter.drawText(QRectF(0, size * 0.72, size, size * 0.22), Qt.AlignCenter, "360")

        painter.end()
        icon.addPixmap(pix)

    return icon
