from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsOpacityEffect,
    QLabel,
    QMenu,
    QWidget,
)

from core.event_bus import event_bus
from services import settings
from ui.paint_utils import paint_grid, paint_styled_background, paint_wallpaper
from ui.taskbar import Taskbar
from ui.widgets.app_icon import AppIcon


class CyberDesk(QWidget):
    """Hauptfenster des Desktops, das Apps automatisch aus der Registry lädt."""

    # Gewünschte Reihenfolge von rechts nach links (rechts unten = erster Eintrag).
    # Apps, die nicht in dieser Liste stehen, landen links davon (in Registry-Reihenfolge).
    ICON_ORDER: ClassVar[list[str]] = ["netrunner", "notes", "calculator"]
    ICON_MARGIN_RIGHT = 32
    ICON_MARGIN_BOTTOM = 20
    ICON_COLUMN_SPACING = 116
    ICON_ROW_SPACING = 96
    ICONS_PER_ROW = 8

    def __init__(self, app_instance, registry, on_logout: Callable[[], None] | None = None):
        super().__init__()
        self.setObjectName("CyberDesk")
        self.setAttribute(Qt.WA_StyledBackground, True)

        # WICHTIG: Speichert die Registry als Instanzvariable,
        # damit wir sie später in closeEvent nutzen können.
        self.registry = registry
        self._on_logout = on_logout
        self._icons: list[AppIcon] = []
        self._wallpaper_pixmap: QPixmap | None = None
        self._load_wallpaper()
        event_bus.subscribe("wallpaper.changed", self._on_wallpaper_changed)

        # Fenster ohne Standard-Betriebssystem-Rahmen öffnen
        self.setWindowFlags(Qt.FramelessWindowHint)

        # Shortcut Ctrl+Q zum Beenden des Desktops
        shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        shortcut.activated.connect(app_instance.quit)

        # Apps aus der Registry abrufen und Icon-Widgets erzeugen (Positionierung
        # erfolgt erst in resizeEvent, denn vor dem echten showFullScreen() hat
        # das Fenster noch nicht seine endgültige Größe).
        self._build_icons()

        self.taskbar = Taskbar(self, registry=self.registry, on_logout=self._handle_logout)
        self._position_taskbar()
        self._position_icons()

    def _build_icons(self) -> None:
        """Erzeugt die Desktop-Icon-Widgets frisch aus der Registry (Reihenfolge über
        ICON_ORDER). Wird beim Start UND von 'Aktualisieren' aufgerufen — im Unterschied
        zum echten Windows-Refresh, der nur neu zeichnet, holt unserer die App-Liste
        wirklich neu, damit ein Refresh auch bei geänderten Apps etwas Sichtbares tut."""
        if not self.registry:
            return
        apps = self.registry.get_apps_info()
        order_index = {app_id: i for i, app_id in enumerate(self.ICON_ORDER)}
        apps_sorted = sorted(apps, key=lambda info: order_index.get(info["id"], len(self.ICON_ORDER)))
        for icon in self._icons:
            icon.deleteLater()
        self._icons = []
        for info in apps_sorted:
            icon = AppIcon(info["id"], info["title"], info["icon"])
            icon.setParent(self)
            icon.show()
            self._icons.append(icon)

    def _position_icons(self) -> None:
        """Positioniert die Desktop-Icons unten rechts in einer Reihe, die nach
        links wächst (Reihenfolge über ICON_ORDER); erst nach ICONS_PER_ROW
        Icons beginnt eine neue Reihe darüber."""
        taskbar_height = self.taskbar.height() if hasattr(self, "taskbar") else 0
        base_y = self.height() - taskbar_height - self.ICON_MARGIN_BOTTOM
        for i, icon in enumerate(self._icons):
            row, col_in_row = divmod(i, self.ICONS_PER_ROW)
            x = self.width() - self.ICON_MARGIN_RIGHT - icon.width() - col_in_row * self.ICON_COLUMN_SPACING
            y = base_y - icon.height() - row * self.ICON_ROW_SPACING
            icon.move(x, y)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if self._wallpaper_pixmap and not self._wallpaper_pixmap.isNull():
            paint_wallpaper(painter, self, self._wallpaper_pixmap)
        else:
            paint_styled_background(self, painter)
        paint_grid(painter, self.width(), self.height(), alpha=3)
        painter.end()

    def _load_wallpaper(self) -> None:
        """Lädt das in den Settings gewählte Hintergrundbild (falls vorhanden)."""
        path = settings.get_wallpaper()
        if path and Path(path).exists():
            pixmap = QPixmap(path)
            self._wallpaper_pixmap = pixmap if not pixmap.isNull() else None
        else:
            self._wallpaper_pixmap = None

    def _on_wallpaper_changed(self, _payload: dict) -> None:
        self._load_wallpaper()
        self.update()

    def contextMenuEvent(self, event) -> None:
        """Windows-artiges Rechtsklick-Menü auf dem Desktop: Aktualisieren,
        Datei-Explorer, Einstellungen, Hintergrund ändern (Untermenü mit den
        Wallpapers + Durchsuchen...), Beenden."""
        menu = QMenu(self)
        menu.setObjectName("TaskbarMenu")

        refresh_action = menu.addAction("Aktualisieren")
        menu.addSeparator()
        explorer_action = menu.addAction("Datei-Explorer öffnen")
        settings_action = menu.addAction("Einstellungen")

        wallpaper_menu = menu.addMenu("Hintergrund ändern")
        wallpaper_menu.setObjectName("TaskbarMenu")
        wallpaper_actions = {}
        for wp_path in settings.list_wallpapers():
            action = wallpaper_menu.addAction(wp_path.stem)
            wallpaper_actions[action] = wp_path
        wallpaper_menu.addSeparator()
        browse_action = wallpaper_menu.addAction("Durchsuchen...")

        menu.addSeparator()
        quit_action = menu.addAction("Beenden")

        chosen = menu.exec(event.globalPos())
        if chosen is None:
            return
        if chosen == refresh_action:
            self._refresh_desktop()
        elif chosen == explorer_action:
            event_bus.publish("app.launch", {"app_id": "file_explorer"})
        elif chosen == settings_action:
            event_bus.publish("app.launch", {"app_id": "settings"})
        elif chosen == quit_action:
            QApplication.instance().quit()
        elif chosen == browse_action:
            self._browse_wallpaper()
        elif chosen in wallpaper_actions:
            wp_path = wallpaper_actions[chosen]
            settings.set_wallpaper(str(wp_path))
            event_bus.publish("wallpaper.changed", {"path": str(wp_path)})

    def _refresh_desktop(self) -> None:
        """'Aktualisieren' wie im echten Windows-Kontextmenü — und wirklich mit
        sichtbarer Wirkung, nicht nur ein Neuzeichnen ohne Effekt: lädt das
        Hintergrundbild frisch von der Platte (falls extern ausgetauscht), holt die
        App-Liste erneut aus der Registry (falls sich etwas geändert hat), positioniert
        neu und zeigt kurz eine Bestätigung, damit der Klick spürbar etwas tut."""
        self._load_wallpaper()
        self._build_icons()
        self._position_icons()
        self.update()
        self._show_refresh_toast()

    def _show_refresh_toast(self) -> None:
        """Kurze, selbstverschwindende Bestätigung oben mittig — sonst wirkt
        'Aktualisieren' bei unverändertem Zustand wie ein toter Knopf."""
        toast = QLabel("Desktop aktualisiert", self)
        toast.setObjectName("DesktopRefreshToast")
        toast.setAttribute(Qt.WA_StyledBackground, True)
        toast.adjustSize()
        toast.move((self.width() - toast.width()) // 2, 28)
        toast.show()
        toast.raise_()

        effect = QGraphicsOpacityEffect(toast)
        toast.setGraphicsEffect(effect)
        effect.setOpacity(0.0)

        fade_in = QPropertyAnimation(effect, b"opacity", toast)
        fade_in.setDuration(150)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)

        fade_out = QPropertyAnimation(effect, b"opacity", toast)
        fade_out.setDuration(400)
        fade_out.setEasingCurve(QEasingCurve.InCubic)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.finished.connect(toast.deleteLater)

        fade_in.start()
        # Referenzen am Toast selbst halten, damit die Animationen nicht vom GC
        # eingesammelt werden, bevor sie fertig sind.
        toast._fade_in = fade_in
        toast._fade_out = fade_out
        QTimer.singleShot(1100, fade_out.start)

    def _browse_wallpaper(self) -> None:
        """Öffnet den echten Windows-Dateidialog, damit ein beliebiges Bild von der
        Festplatte als Hintergrund gewählt werden kann — nicht nur die Presets."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Hintergrundbild wählen", "", "Bilder (*.png *.jpg *.jpeg)"
        )
        if not path:
            return
        dest = settings.add_custom_wallpaper(path)
        settings.set_wallpaper(str(dest))
        event_bus.publish("wallpaper.changed", {"path": str(dest)})

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_taskbar()
        self._position_icons()

    def _position_taskbar(self) -> None:
        if hasattr(self, "taskbar"):
            self.taskbar.setGeometry(0, self.height() - self.taskbar.height(), self.width(), self.taskbar.height())

    def _handle_logout(self) -> None:
        """Schließt den Desktop (inkl. aller App-Fenster) und kehrt zum Login zurück."""
        callback = self._on_logout
        self.close()
        if callback:
            callback()

    def closeEvent(self, event):
        """
        Wird aufgerufen, wenn der Desktop geschlossen wird.
        Hier werden alle offenen App-Fenster über den WindowManager sauber beendet.
        """
        event_bus.unsubscribe("wallpaper.changed", self._on_wallpaper_changed)

        # Wir prüfen, ob die Registry und der WindowManager (wm) existieren
        if self.registry and self.registry._wm:
            print("Desktop wird beendet: Schließe alle App-Fenster...")
            # Alle Fenster über den WindowManager schließen
            self.registry._wm.close_all_windows()

        # Bestätigt das Ereignis, damit das Fenster tatsächlich geschlossen wird
        event.accept()
