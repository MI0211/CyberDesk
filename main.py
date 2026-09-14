import os
# Vermeidet Workarounds wie --disable-gpu, lässt Chromium über ANGLE/DirectX11 laufen
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-gpu-rasterization --enable-zero-copy"

import sys
from PySide6.QtWidgets import QApplication
from ui.auth_screen import AuthScreen
from ui.desktop import CyberDesk
from core.app_registry import AppRegistry
from core.window_manager import WindowManager

def main():
    app = QApplication(sys.argv)

    try:
        with open("assets/styles/cyberpunk.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Fehler: CSS-Datei nicht gefunden!")
    except UnicodeDecodeError:
        print("Fehler: Die CSS-Datei konnte nicht als UTF-8 gelesen werden.")

    # Hält die Referenz auf das aktuell sichtbare Top-Level-Fenster,
    # damit es nicht vom Garbage Collector eingesammelt wird.
    state = {"window": None}

    def show_desktop():
        wm = WindowManager(desktop=None)
        registry = AppRegistry(wm)
        desktop = CyberDesk(app, registry, on_logout=show_auth)
        wm._desktop = desktop
        state["window"] = desktop
        desktop.showFullScreen()

    def show_auth():
        auth = AuthScreen(on_success=show_desktop)
        state["window"] = auth
        auth.showFullScreen()

    show_auth()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()