from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QDateTime, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.event_bus import event_bus
from services import settings
from ui.paint_utils import round_pixmap


class _ClickableRow(QWidget):
    """QWidget, das per Klick eine Callback auslöst — für Zeilen, die als Ganzes
    klickbar sein sollen (z.B. die Nutzerkarte), aber keine Button-Optik haben."""

    def __init__(self, on_click: Callable[[], None]) -> None:
        super().__init__()
        self._on_click = on_click
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._on_click()
        super().mousePressEvent(event)


class _StartMenu(QWidget):
    """Popup-Startmenü im Figma-Look: Nutzerkarte, App-Liste (live aus der Registry), Abmelden.

    Läuft als eigenständiges Popup-Fenster (Qt.Popup), damit es sich wie ein
    Kontextmenü verhält — schließt automatisch bei Klick daneben oder Escape.
    """

    def __init__(
        self,
        registry,
        on_launch: Callable[[str], None],
        on_logout: Callable[[], None],
    ) -> None:
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("StartMenu")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(260)
        self._on_launch = on_launch
        self._on_logout = on_logout
        self._build_ui(registry)

    def _build_ui(self, registry) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_user_card())
        layout.addWidget(self._build_divider())

        apps_label = QLabel("APPS")
        apps_label.setObjectName("StartMenuSectionLabel")
        layout.addWidget(apps_label)

        apps = registry.get_apps_info() if registry else []
        if apps:
            for info in apps:
                layout.addWidget(self._build_app_row(info))
        else:
            empty = QLabel("Keine Apps verfügbar")
            empty.setObjectName("StartMenuEmptyLabel")
            layout.addWidget(empty)

        layout.addWidget(self._build_divider())
        layout.addWidget(self._build_action_row("Abmelden", "StartMenuLogoutRow", self._logout))
        layout.addWidget(self._build_action_row("Beenden", "StartMenuQuitRow", self._quit))

    def _build_user_card(self) -> QWidget:
        # Klickbar -> öffnet die echten Profil-Einstellungen (Settings-App).
        row = _ClickableRow(self._open_settings)
        row.setObjectName("StartMenuUserCard")
        row.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(row)
        h.setContentsMargins(16, 14, 16, 14)
        h.setSpacing(10)

        user_name = settings.get_user_name()
        avatar_path = settings.get_user_avatar()

        avatar = QLabel()
        avatar.setObjectName("StartMenuAvatar")
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(Qt.AlignCenter)
        if avatar_path and Path(avatar_path).exists():
            avatar.setPixmap(round_pixmap(QPixmap(avatar_path), 32))
        else:
            avatar.setText((user_name[:1] or "V").upper())

        # Neon-Glühen um den Avatar-Kreis (QSS kennt kein box-shadow, daher
        # über einen echten QGraphicsDropShadowEffect mit Offset 0/0 = ambientes Glühen).
        glow = QGraphicsDropShadowEffect(avatar)
        glow.setColor(QColor(139, 92, 246, 220))
        glow.setBlurRadius(22)
        glow.setOffset(0, 0)
        avatar.setGraphicsEffect(glow)

        name = QLabel(user_name)
        name.setObjectName("StartMenuUserName")

        h.addWidget(avatar)
        h.addWidget(name)
        h.addStretch()
        return row

    def _open_settings(self) -> None:
        self.close()
        self._on_launch("settings")

    def _build_divider(self) -> QWidget:
        divider = QWidget()
        divider.setObjectName("StartMenuDivider")
        divider.setAttribute(Qt.WA_StyledBackground, True)
        divider.setFixedHeight(1)
        return divider

    def _build_app_row(self, info: dict) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("StartMenuAppRow")
        btn.setText(info.get("title", info["id"]))
        if info.get("icon"):
            btn.setIcon(QIcon(info["icon"]))
        btn.setIconSize(QSize(18, 18))
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setCursor(Qt.PointingHandCursor)
        app_id = info["id"]
        btn.clicked.connect(lambda: self._launch(app_id))
        return btn

    def _build_action_row(self, text: str, object_name: str, handler: Callable[[], None]) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName(object_name)
        btn.setText(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(handler)
        return btn

    def _launch(self, app_id: str) -> None:
        self.close()
        self._on_launch(app_id)

    def _logout(self) -> None:
        self.close()
        self._on_logout()

    def _quit(self) -> None:
        self.close()
        QApplication.instance().quit()


class _CalendarPopup(QWidget):
    """Mini-Kalender wie bei Windows — öffnet sich beim Klick auf die Uhr,
    schließt automatisch bei Klick daneben (Qt.Popup)."""

    def __init__(self) -> None:
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("CalendarPopup")
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        calendar = QCalendarWidget()
        calendar.setObjectName("CalendarWidget")
        calendar.setGridVisible(False)
        calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        calendar.setHorizontalHeaderFormat(QCalendarWidget.SingleLetterDayNames)
        calendar.setFirstDayOfWeek(Qt.Monday)  # Montag–Sonntag statt Sonntag–Samstag

        # Ohne explizites Format bleiben die Wochentags-Kürzel in der Kopfzeile auf dem
        # native Qt-Default (hell/kaum lesbar auf dunklem Grund). Gleichzeitig damit die
        # Wochenenden (Sa/So) einheitlich rot einfärben — sowohl im Kopf als auch bei den
        # Datumszahlen selbst.
        weekday_format = QTextCharFormat()
        weekday_format.setForeground(QColor(255, 255, 255, 200))
        weekend_format = QTextCharFormat()
        weekend_format.setForeground(QColor(248, 113, 113))
        for day in (Qt.Monday, Qt.Tuesday, Qt.Wednesday, Qt.Thursday, Qt.Friday):
            calendar.setWeekdayTextFormat(day, weekday_format)
        for day in (Qt.Saturday, Qt.Sunday):
            calendar.setWeekdayTextFormat(day, weekend_format)

        layout.addWidget(calendar)


class _TaskbarAppButton(QToolButton):
    """Ein einzelner Eintrag in der Taskbar: repräsentiert eine laufende und/oder
    angeheftete App. Linksklick öffnet/holt sie nach vorne, Rechtsklick zeigt ein
    Kontextmenü (Schließen / An Taskbar anheften)."""

    def __init__(self, app_id: str, title: str, icon_path: str | None, taskbar: Taskbar) -> None:
        super().__init__()
        self.app_id = app_id
        self._taskbar = taskbar

        self.setObjectName("TaskbarAppButton")
        self.setToolTip(title)
        if icon_path:
            self.setIcon(QIcon(icon_path))
        self.setIconSize(QSize(22, 22))
        self.setFixedSize(44, 38)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.clicked.connect(lambda: self._taskbar.activate_app(self.app_id))
        self.customContextMenuRequested.connect(
            lambda pos: self._taskbar.show_context_menu(self.app_id, self.mapToGlobal(pos))
        )

        self.set_running(False)

    def set_running(self, running: bool) -> None:
        """Steuert per dynamischer Property das Aussehen (aktiv = laufend/minimiert)."""
        self.setProperty("running", "true" if running else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class Taskbar(QWidget):
    """Echte Taskleiste am unteren Bildschirmrand: Startmenü, App-Buttons, Uhr."""

    def __init__(self, parent: QWidget, registry, on_logout: Callable[[], None]) -> None:
        super().__init__(parent)
        self.registry = registry
        self._on_logout = on_logout

        self.setObjectName("Taskbar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(48)

        # app_id -> {"window_id", "title", "icon"} für aktuell laufende (bzw. minimierte) Fenster
        self._running: dict[str, dict] = {}
        # app_id -> Taskbar-Button (sowohl für laufende als auch angeheftete Apps)
        self._buttons: dict[str, _TaskbarAppButton] = {}
        self._pinned: set[str] = set(settings.get_pinned_apps())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 14, 4)
        layout.setSpacing(6)

        self.menu_btn = QPushButton("☰  MENÜ")
        self.menu_btn.setObjectName("TaskbarMenuButton")
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        self.menu_btn.clicked.connect(self._show_main_menu)
        layout.addWidget(self.menu_btn)

        self.apps_row = QHBoxLayout()
        self.apps_row.setSpacing(4)
        layout.addLayout(self.apps_row)
        layout.addStretch()

        self.clock_btn = QPushButton()
        self.clock_btn.setObjectName("TaskbarClock")
        self.clock_btn.setCursor(Qt.PointingHandCursor)
        self.clock_btn.clicked.connect(self._show_calendar)
        layout.addWidget(self.clock_btn)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

        # Event-Bus-Anbindung: die Taskbar reagiert auf alles, was mit Fenstern passiert
        event_bus.subscribe("window.opened", self._on_window_opened)
        event_bus.subscribe("window.minimized", self._on_window_minimized)
        event_bus.subscribe("window.restored", self._on_window_restored)
        event_bus.subscribe("window.closed", self._on_window_closed)

        # Angeheftete Apps sollen schon vor dem ersten Start sichtbar sein
        for app_id in list(self._pinned):
            self._ensure_button(app_id)

    # ------------------------------------------------------------------
    # Uhr
    # ------------------------------------------------------------------
    def _tick(self) -> None:
        now = QDateTime.currentDateTime()
        self.clock_btn.setText(now.toString("HH:mm:ss  ·  ddd, dd.MM.yyyy"))

    def _show_calendar(self) -> None:
        # WICHTIG: Referenz auf self merken (self._calendar_popup)! Ein Qt.Popup-
        # Widget ohne Eltern-Widget wird nur durch eine Python-Referenz am Leben
        # gehalten — eine rein lokale Variable kann vom Garbage Collector
        # eingesammelt werden, sobald die Methode zurückkehrt (bei _StartMenu
        # "funktionierte" das bisher nur zufällig durch einen Referenzzyklus über
        # die verbundenen Lambda-Slots).
        popup = _CalendarPopup()
        self._calendar_popup = popup
        popup.adjustSize()
        btn_top_right = self.clock_btn.mapToGlobal(self.clock_btn.rect().topRight())
        taskbar_top_y = self.mapToGlobal(self.rect().topLeft()).y()
        popup.move(btn_top_right.x() - popup.width(), taskbar_top_y - popup.height())
        popup.show()

    # ------------------------------------------------------------------
    # Startmenü (Nutzerkarte, App-Liste, Abmelden/Beenden)
    # ------------------------------------------------------------------
    def _show_main_menu(self) -> None:
        start_menu = _StartMenu(self.registry, on_launch=self._launch_from_start_menu, on_logout=self._on_logout)
        self._start_menu_popup = start_menu  # Referenz halten, siehe _show_calendar()
        # An der Taskbar selbst ausrichten (nicht am Button!) — sonst überlappt
        # der Innenabstand des Buttons das Popup um ein paar Pixel.
        taskbar_top_left = self.mapToGlobal(self.rect().topLeft())
        # sizeHint() ist vor dem ersten Layout-Durchlauf unzuverlässig (Icons/Font-
        # Metriken sind da noch nicht final) — adjustSize() erzwingt die echte
        # Layout-Berechnung, erst danach ist .height() verlässlich.
        start_menu.adjustSize()
        start_menu.move(taskbar_top_left.x(), taskbar_top_left.y() - start_menu.height())
        start_menu.show()

    def _launch_from_start_menu(self, app_id: str) -> None:
        event_bus.publish("app.launch", {"app_id": app_id})

    # ------------------------------------------------------------------
    # App-Info-Hilfsfunktionen
    # ------------------------------------------------------------------
    def _app_info(self, app_id: str) -> dict:
        """Liefert Titel/Icon einer App: bevorzugt aus laufenden Fenstern, sonst aus der Registry."""
        if app_id in self._running:
            return self._running[app_id]
        for info in self.registry.get_apps_info():
            if info["id"] == app_id:
                return {"title": info["title"], "icon": info["icon"]}
        return {"title": app_id, "icon": None}

    def _ensure_button(self, app_id: str) -> _TaskbarAppButton:
        if app_id in self._buttons:
            return self._buttons[app_id]
        info = self._app_info(app_id)
        btn = _TaskbarAppButton(app_id, info.get("title", app_id), info.get("icon"), self)
        self._buttons[app_id] = btn
        self.apps_row.addWidget(btn)
        return btn

    def _remove_button_if_unneeded(self, app_id: str) -> None:
        """Entfernt den Button nur, wenn die App weder läuft noch angeheftet ist."""
        if app_id in self._running or app_id in self._pinned:
            return
        btn = self._buttons.pop(app_id, None)
        if btn:
            self.apps_row.removeWidget(btn)
            btn.deleteLater()

    # ------------------------------------------------------------------
    # Event-Bus-Handler
    # ------------------------------------------------------------------
    def _on_window_opened(self, payload: dict) -> None:
        app_id = payload.get("app_id")
        if not app_id:
            return
        self._running[app_id] = {
            "window_id": payload.get("window_id"),
            "title": payload.get("title") or app_id,
            "icon": payload.get("icon"),
            "minimized": False,
        }
        self._ensure_button(app_id).set_running(True)

    def _on_window_minimized(self, payload: dict) -> None:
        app_id = payload.get("app_id")
        if not app_id:
            return
        entry = self._running.setdefault(app_id, {})
        entry["window_id"] = payload.get("window_id")
        entry["title"] = payload.get("title") or app_id
        entry["icon"] = payload.get("icon")
        entry["minimized"] = True
        self._ensure_button(app_id).set_running(True)

    def _on_window_restored(self, payload: dict) -> None:
        app_id = payload.get("app_id")
        if app_id in self._running:
            self._running[app_id]["minimized"] = False
        if app_id and app_id in self._buttons:
            self._buttons[app_id].set_running(True)

    def _on_window_closed(self, payload: dict) -> None:
        app_id = payload.get("app_id")
        if not app_id:
            return
        self._running.pop(app_id, None)
        if app_id in self._pinned:
            # Button bleibt bestehen (angeheftet), zeigt aber "nicht laufend"
            if app_id in self._buttons:
                self._buttons[app_id].set_running(False)
        else:
            self._remove_button_if_unneeded(app_id)

    # ------------------------------------------------------------------
    # Klick- / Kontextmenü-Logik
    # ------------------------------------------------------------------
    def activate_app(self, app_id: str) -> None:
        """Linksklick: minimierte App wiederherstellen, sichtbare App minimieren,
        sonst (noch nicht gestartet) neu starten."""
        if app_id in self._running:
            window_id = self._running[app_id]["window_id"]
            if self._running[app_id].get("minimized"):
                event_bus.publish("window.restore", {"window_id": window_id})
            else:
                event_bus.publish("window.minimize", {"window_id": window_id})
        else:
            event_bus.publish("app.launch", {"app_id": app_id})

    def show_context_menu(self, app_id: str, global_pos) -> None:
        """Rechtsklick: Menü mit 'Schließen' und 'An Taskbar anheften/lösen'."""
        menu = QMenu(self)
        menu.setObjectName("TaskbarMenu")

        is_running = app_id in self._running
        is_pinned = app_id in self._pinned

        close_action = menu.addAction("Schließen")
        close_action.setEnabled(is_running)

        pin_action = menu.addAction("Von Taskbar lösen" if is_pinned else "An Taskbar anheften")

        chosen = menu.exec(global_pos)
        if chosen == close_action and is_running:
            event_bus.publish("window.close", {"window_id": self._running[app_id]["window_id"]})
        elif chosen == pin_action:
            self._toggle_pin(app_id)

    def _toggle_pin(self, app_id: str) -> None:
        if app_id in self._pinned:
            self._pinned.discard(app_id)
            settings.unpin_app(app_id)
            self._remove_button_if_unneeded(app_id)
        else:
            self._pinned.add(app_id)
            settings.pin_app(app_id)
            self._ensure_button(app_id)
