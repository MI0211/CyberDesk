from __future__ import annotations
import logging
import uuid
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt  
from core.event_bus import event_bus

logger = logging.getLogger(__name__)

class WindowManager:
    """Verwaltet alle offenen Fenster auf dem CyberDesk"""
    
    def __init__(self, desktop: QWidget = None) -> None:
        self._desktop = desktop
        self._windows: dict[str, QWidget] = {}
        event_bus.subscribe("window.close", self._on_close_request)
        event_bus.subscribe("window.restore", self._on_restore_request)
        event_bus.subscribe("window.minimize", self._on_minimize_request)
        
    def open_window(self, app: QWidget) -> str:
        """Oeffnet ein neues Fenster und gibt die Window-ID zurueck."""
        
        app_id = getattr(app, "app_id", None)
        
        # Prüfen, ob GENAU DIESE App-Instanz (gleiche ID) schon offen ist.
        if app_id:
            for window_id, window in self._windows.items():
                if getattr(window, "app_id", None) == app_id:
                    self._show_and_activate(window)
                    logger.info("App %s ist bereits offen, bringe nach vorne.", app_id)
                    return window_id

        # Wenn ein Desktop-Container existiert, binden wir das Fenster direkt als SubWindow ein
        if self._desktop:
            app.setParent(self._desktop)
            
        # Setzen der korrekten Flags, damit es im Workspace bleibt und keine separate OS-Leiste belegt
        app.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        
        # Neues Fenster registrieren
        window_id = str(uuid.uuid4())
        self._windows[window_id] = app 
        app.window_id = window_id  # Damit die App (z.B. beim Minimieren) ihre eigene ID kennt
        
        # Damit sie nicht alle starr aufeinander hocken, geben wir ihnen eine kleine Startposition
        offset = (len(self._windows) - 1) * 30
        app.move(50 + offset, 50 + offset)
        
        self._show_and_activate(app)
        
        icon_path = app._resolve_icon_path() if hasattr(app, "_resolve_icon_path") else None
        event_bus.publish("window.opened", {
            "window_id": window_id,
            "app_id": app_id,
            "title": app.windowTitle(),
            "icon": icon_path,
        })
        logger.info("Fenster geöffnet: %s", app.windowTitle())
        return window_id                    

    @staticmethod
    def _show_and_activate(window: QWidget) -> None:
        window.show()
        window.raise_()
        window.activateWindow()
    
    def close_all_windows(self) -> None:
        """Schließt alle aktuell geöffneten App-Fenster wenn Desktop geschlossen wird."""
        window_ids = list(self._windows.keys())
        
        for window_id in window_ids:
            self.close_window(window_id)
            
        logger.info("Alle Fenster wurden beim Beenden geschlossen.")
    
    def close_window(self, window_id: str) -> None:
        """Schliesst ein Fenster und bereinigt den Speicher."""
        window = self._windows.pop(window_id, None)
        if window is None:
            logger.warning("Unbekanntes Fenster: %s", window_id)
            return
        app_id = getattr(window, "app_id", None)
        if hasattr(window, "on_close"):
            window.on_close()
        window.close()
        window.deleteLater()
        event_bus.publish("window.closed", {"window_id": window_id, "app_id": app_id})    
        logger.info("Fenster geschlossen: %s", window_id)

    def restore_window(self, window_id: str) -> None:
        """Blendet ein minimiertes Fenster wieder ein und holt es in den Vordergrund (z.B. Taskbar-Klick)."""
        window = self._windows.get(window_id)
        if window is None:
            logger.warning("Kann Fenster nicht wiederherstellen, unbekannt: %s", window_id)
            return
        self._show_and_activate(window)
        event_bus.publish("window.restored", {
            "window_id": window_id,
            "app_id": getattr(window, "app_id", None),
        })
    
    def minimize_window(self, window_id: str) -> None:
        """Blendet ein Fenster aus (z.B. Klick auf sein eigenes laufendes Taskbar-Icon).

        Ruft showMinimized() auf dem Fenster auf — BaseApp überschreibt diese
        Methode und publiziert dabei selbst 'window.minimized', darum muss das
        hier nicht zusätzlich passieren.
        """
        window = self._windows.get(window_id)
        if window is None:
            logger.warning("Kann Fenster nicht minimieren, unbekannt: %s", window_id)
            return
        window.showMinimized()

    def _on_close_request(self, payload: dict) -> None:
        """Reagiert auf Event 'window.close'."""
        window_id = payload.get("window_id")
        if window_id:
            self.close_window(window_id)

    def _on_restore_request(self, payload: dict) -> None:
        """Reagiert auf Event 'window.restore'."""
        window_id = payload.get("window_id")
        if window_id:
            self.restore_window(window_id)

    def _on_minimize_request(self, payload: dict) -> None:
        """Reagiert auf Event 'window.minimize'."""
        window_id = payload.get("window_id")
        if window_id:
            self.minimize_window(window_id)
        
    @property
    def open_count(self) -> int:
        """Anzahl aktuell offener Fenster."""
        return len(self._windows)
