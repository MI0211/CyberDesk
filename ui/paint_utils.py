"""Gemeinsame QPainter-Hilfsfunktionen für den Cyberpunk-Look."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QStyle, QStyleOption, QWidget

SPOTLIGHT_VIOLET = QColor(139, 92, 246)


def paint_styled_background(widget: QWidget, painter: QPainter) -> None:
    """Zeichnet den QSS-Hintergrund des Widgets (nötig, sobald paintEvent überschrieben wird)."""
    opt = QStyleOption()
    opt.initFrom(widget)
    widget.style().drawPrimitive(QStyle.PE_Widget, opt, painter, widget)


def paint_grid(painter: QPainter, width: int, height: int, spacing: int = 48, alpha: int = 14) -> None:
    """Zeichnet ein feines 1px-Gitter (das Figma-Raster hinter Desktop/Login).

    Die Zellgröße wird pro Achse leicht an width/height angepasst (statt fix
    48px), damit eine ganze Zahl Zellen exakt bis zum Rand passt — die letzte
    Linie landet immer exakt auf der Kante, kein abgeschnittener Rest.
    """
    pen = QPen(QColor(255, 255, 255, alpha))
    pen.setWidth(1)
    painter.setPen(pen)

    cols = max(1, round(width / spacing))
    col_step = width / cols
    for i in range(cols + 1):
        x = round(i * col_step)
        painter.drawLine(x, 0, x, height)

    rows = max(1, round(height / spacing))
    row_step = height / rows
    for i in range(rows + 1):
        y = round(i * row_step)
        painter.drawLine(0, y, width, y)


def paint_spotlight(
    painter: QPainter,
    widget: QWidget,
    global_pos: QPointF,
    radius: float = 260.0,
    color: QColor = SPOTLIGHT_VIOLET,
    peak_alpha: int = 60,
) -> None:
    """Zeichnet ein weiches violettes Glühen, zentriert auf `global_pos` (Bildschirm-
    koordinaten), im lokalen Koordinatensystem von `widget`. Der weiche Verlauf über
    mehrere Stops (statt eines harten Kreises) gibt dem Licht ein Gefühl von Tiefe."""
    local_pos = widget.mapFromGlobal(global_pos.toPoint())

    gradient = QRadialGradient(QPointF(local_pos), radius)
    center = QColor(color)
    center.setAlpha(peak_alpha)
    mid = QColor(color)
    mid.setAlpha(int(peak_alpha * 0.35))
    edge = QColor(color)
    edge.setAlpha(0)
    gradient.setColorAt(0.0, center)
    gradient.setColorAt(0.5, mid)
    gradient.setColorAt(1.0, edge)

    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawRect(widget.rect())
    painter.restore()


def round_pixmap(pixmap: QPixmap, size: int) -> QPixmap:
    """Schneidet ein Pixmap kreisförmig zurecht (QSS border-radius allein clippt
    keine Pixmap-Inhalte, nur Rahmen/Hintergrund des Widgets)."""
    scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    rounded = QPixmap(size, size)
    rounded.fill(Qt.transparent)

    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    x = (scaled.width() - size) // 2
    y = (scaled.height() - size) // 2
    painter.drawPixmap(-x, -y, scaled)
    painter.end()
    return rounded


def paint_wallpaper(painter: QPainter, widget: QWidget, pixmap: QPixmap, overlay_alpha: int = 110) -> None:
    """Zeichnet ein Hintergrundbild im 'cover'-Zuschnitt (füllt die ganze Fläche,
    Seitenverhältnis bleibt erhalten, zentriert beschnitten) + ein dunkles Overlay,
    damit Icons/Taskbar-Text unabhängig vom Bildinhalt lesbar bleiben."""
    target = widget.rect()
    scaled = pixmap.scaled(target.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = (target.width() - scaled.width()) // 2
    y = (target.height() - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)

    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(6, 6, 15, overlay_alpha))
    painter.drawRect(target)
    painter.restore()
