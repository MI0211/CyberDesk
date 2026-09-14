import shutil
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
)

from apps.base_app import BaseApp
from core.event_bus import event_bus
from services import settings
from ui.paint_utils import round_pixmap

_AVATAR_STORE_DIR = Path("data/avatar")


class SettingsApp(BaseApp):
    """Profil-Einstellungen: Anzeigename + Profilbild. Speichert echt über
    services/settings.py (data/settings.json) — kein Fake-UI, wirkt sich
    direkt auf die Nutzerkarte im Startmenü aus."""

    app_id = "settings"
    title = "Einstellungen"

    def __init__(self):
        super().__init__(app_id="settings", title="Einstellungen", event_bus=event_bus)
        self.setWindowTitle("Einstellungen")

        try:
            with open("assets/styles/cyberpunk.qss", "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Style Datei nicht gefunden!")

    def build_ui(self, layout) -> None:
        self.resize(380, 520)
        self.setMinimumSize(340, 480)  # sonst überlappt das Wallpaper-Grid (3 Spalten)
        self._avatar_path: str | None = settings.get_user_avatar()

        heading = QLabel("PROFIL")
        heading.setObjectName("settingsSectionLabel")
        layout.addWidget(heading)

        avatar_row = QHBoxLayout()
        avatar_row.setSpacing(14)

        self.avatar_preview = QLabel()
        self.avatar_preview.setObjectName("settingsAvatarPreview")
        self.avatar_preview.setFixedSize(64, 64)
        self.avatar_preview.setAlignment(Qt.AlignCenter)
        avatar_row.addWidget(self.avatar_preview)

        # Gleiches violettes Neon-Glühen wie beim Avatar im Startmenü.
        glow = QGraphicsDropShadowEffect(self.avatar_preview)
        glow.setColor(QColor(139, 92, 246, 220))
        glow.setBlurRadius(24)
        glow.setOffset(0, 0)
        self.avatar_preview.setGraphicsEffect(glow)

        choose_btn = QPushButton("Bild wählen...")
        choose_btn.setObjectName("settingsChooseAvatarBtn")
        choose_btn.setCursor(Qt.PointingHandCursor)
        choose_btn.clicked.connect(self._choose_avatar)
        avatar_row.addWidget(choose_btn)
        avatar_row.addStretch()
        layout.addLayout(avatar_row)

        layout.addSpacing(16)

        name_label = QLabel("Anzeigename")
        name_label.setObjectName("settingsFieldLabel")
        layout.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setObjectName("settingsNameInput")
        self.name_input.setText(settings.get_user_name())
        self.name_input.textChanged.connect(self._refresh_avatar_preview)
        layout.addWidget(self.name_input)

        layout.addSpacing(20)

        self.save_btn = QPushButton("Speichern")
        self.save_btn.setObjectName("settingsSaveBtn")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._save)
        layout.addWidget(self.save_btn)

        layout.addSpacing(24)

        bg_heading = QLabel("HINTERGRUND")
        bg_heading.setObjectName("settingsSectionLabel")
        layout.addWidget(bg_heading)

        self._wallpaper_grid = QGridLayout()
        self._wallpaper_grid.setSpacing(10)
        layout.addLayout(self._wallpaper_grid)
        self._populate_wallpaper_grid()

        browse_wp_btn = QPushButton("Durchsuchen...")
        browse_wp_btn.setObjectName("settingsChooseAvatarBtn")
        browse_wp_btn.setCursor(Qt.PointingHandCursor)
        browse_wp_btn.clicked.connect(self._browse_wallpaper)
        layout.addSpacing(8)
        layout.addWidget(browse_wp_btn)

        layout.addSpacing(16)

        self.status_label = QLabel("")
        self.status_label.setObjectName("settingsStatusLabel")
        layout.addWidget(self.status_label)

        layout.addStretch()

        self._refresh_avatar_preview()

    # ------------------------------------------------------------------
    def _refresh_avatar_preview(self) -> None:
        if self._avatar_path and Path(self._avatar_path).exists():
            self.avatar_preview.setPixmap(round_pixmap(QPixmap(self._avatar_path), 60))
            self.avatar_preview.setText("")
        else:
            self.avatar_preview.setPixmap(QPixmap())
            initial = self.name_input.text().strip()[:1].upper() or "V"
            self.avatar_preview.setText(initial)

    def _choose_avatar(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Profilbild wählen", "", "Bilder (*.png *.jpg *.jpeg)"
        )
        if not path:
            return
        # Datei nach data/avatar/ kopieren, statt nur den externen Pfad zu merken —
        # sonst bricht das Profilbild, sobald die Originaldatei verschoben/gelöscht wird.
        try:
            _AVATAR_STORE_DIR.mkdir(parents=True, exist_ok=True)
            dest = _AVATAR_STORE_DIR / f"avatar{Path(path).suffix.lower()}"
            shutil.copyfile(path, dest)
            self._avatar_path = str(dest)
        except OSError:
            self._avatar_path = path  # Fallback: Originalpfad direkt verwenden
        self._refresh_avatar_preview()

    def _save(self) -> None:
        name = self.name_input.text().strip() or "Benutzer"
        settings.set_user_name(name)
        if self._avatar_path:
            settings.set_user_avatar(self._avatar_path)
        self.status_label.setText("Gespeichert.")
        event_bus.publish("profile.updated", {"name": name, "avatar": self._avatar_path})

    def _select_wallpaper(self, path: Path) -> None:
        """Wendet den Hintergrund sofort an (kein Warten auf 'Speichern' — soll sich
        wie eine echte OS-Live-Vorschau anfühlen)."""
        settings.set_wallpaper(str(path))
        event_bus.publish("wallpaper.changed", {"path": str(path)})
        self.status_label.setText("Hintergrund geändert.")

    def _populate_wallpaper_grid(self) -> None:
        """Baut die Vorschau-Kacheln neu aus settings.list_wallpapers() auf
        (Presets aus assets/wallpapers/ + eigene über 'Durchsuchen...' hinzugefügte
        aus data/wallpapers/). Wird auch nach einem Browse-Import erneut aufgerufen,
        damit die neue Datei sofort als Kachel erscheint."""
        while (item := self._wallpaper_grid.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._wallpaper_group = QButtonGroup(self)
        self._wallpaper_group.setExclusive(True)
        current_wallpaper = settings.get_wallpaper()
        for i, wp_path in enumerate(settings.list_wallpapers()):
            thumb = QToolButton()
            thumb.setObjectName("settingsWallpaperThumb")
            thumb.setIcon(QIcon(str(wp_path)))
            thumb.setIconSize(QSize(72, 45))
            thumb.setCheckable(True)
            thumb.setCursor(Qt.PointingHandCursor)
            thumb.setChecked(current_wallpaper == str(wp_path))
            thumb.clicked.connect(lambda _checked, p=wp_path: self._select_wallpaper(p))
            self._wallpaper_group.addButton(thumb)
            self._wallpaper_grid.addWidget(thumb, i // 3, i % 3)

    def _browse_wallpaper(self) -> None:
        """Öffnet den echten Windows-Dateidialog, damit ein beliebiges Bild von der
        Festplatte als Hintergrund gewählt werden kann — nicht nur die 5 Presets."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Hintergrundbild wählen", "", "Bilder (*.png *.jpg *.jpeg)"
        )
        if not path:
            return
        dest = settings.add_custom_wallpaper(path)
        self._select_wallpaper(dest)
        self._populate_wallpaper_grid()
