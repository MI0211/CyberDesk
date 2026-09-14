# 1. Stdlib (Standard-Bibliotheken):

from __future__ import annotations
import importlib          # Zum dynamischen Laden der App-Module während der Laufzeit
import logging
import pkgutil            # Zum Durchsuchen des 'apps'-Verzeichnisses nach neuen Anwendungen
import os


# 2. Third-party (Externe Bibliotheken – falls vorhanden):



# 3. Eigene Module (Lokale Projekt-Dateien):

import apps               # Importiert das 'apps'-Paket, damit pkgutil den Pfad finden kann
from apps.base_app import BaseApp
from core.event_bus import event_bus
from core.window_manager import WindowManager

logger = logging.getLogger(__name__)

class AppRegistry:
    """Kennt alle Apps und kann sie starten."""

    def __init__(self, window_manager: WindowManager) -> None:
        self._apps: dict[str, type[BaseApp]] = {}
        self._wm = window_manager
        event_bus.subscribe("app.launch", self._on_launch)

        self.discover_apps() # Automatische Suche und Registrierung aller Apps im 'apps'-Ordner beim Start

    
    

    def get_apps_info(self) -> list[dict]:
        """Gibt eine Liste aller Apps für die UI-Generierung zurück."""
        apps_info = []
        for app_id, app_class in self._apps.items():
            # Prüfen, ob das Icon als SVG oder in verschiedenen PNG-Formaten existiert
            svg_path = f"assets/images/{app_id}.svg"
            png_path = f"assets/images/{app_id}_icon.png"
            fallback_png = f"assets/images/{app_id}.png"

            if os.path.exists(svg_path):
                icon_path = svg_path
            elif os.path.exists(png_path):
                icon_path = png_path
            elif os.path.exists(fallback_png):
                icon_path = fallback_png
            else:
                logger.warning("Kein Icon gefunden für App: '%s'", app_id)
                icon_path = None  # Kein blindes Fallback, damit fehlende Icons auffallen

            apps_info.append({
                "id": app_id,
                "title": getattr(app_class, "title", app_class.__name__),
                "icon": icon_path
            })
        return apps_info
     

    
    def discover_apps(self) -> None: # Durchsucht der Ordner 'apps' und uebernimmt die Direkt in registry ohne die in Main separat zu eintragen!
        for _, name, ispkg in pkgutil.iter_modules(apps.__path__):
            if ispkg:
                try:
                    module = importlib.import_module(f"apps.{name}.{name}_app") # Dynamischer Import der App-Module basierend auf der Ordnerstruktur

                    for attr_name in dir(module):         # Durchsucht das Modul nach Klassen, die von BaseApp erben
                        attr = getattr(module, attr_name)

                        if(isinstance(attr, type) and    # Überprüfung, ob es eine App-Klasse ist (erbt von BaseApp, aber nicht die BaseApp selbst)
                        issubclass(attr, BaseApp) and
                        attr is not BaseApp):
                    
                            self.register(attr) # Registrierung der gefundenen App in der Registry

                except (ImportError, AttributeError) as e:
                    logger.warning("Koennte App '%s' nicht laden: '%s", name, e)

    
    
    def register(self, app_class: type[BaseApp]) -> None:
        """Registriert eine App-Klasse."""
        self._apps[app_class.app_id] = app_class
        logger.info("App registriert: '%s'", app_class.app_id)  
        
    def launch(self, app_id: str) -> None:
        """Startet eine App anhand ihrer ID."""
        print(f"DEBUG: Registry versucht App zu starten: {app_id}")
        app_class = self._apps.get(app_id)
        if app_class is None:
            logger.error("Unbekannte App: '%s'", app_id)
            return      
        try:
            instance = app_class()
            print(f"DEBUG: App-Instanz erstellt für: {app_id}")
            self._wm.open_window(instance)
        except Exception as e:
            print(f"!!! FEHLER beim Start von App {app_id}: {e} !!!")
            logger.exception("Fehler beim Instanziieren der App %s", app_id)
        
    def available_apps(self) -> list[str]:
        """Gibt eine Liste aller registrierten App-IDs zuueck."""
        return sorted(self._apps.keys())
    
    def _on_launch(self, payload: dict) -> None:
        """Reagiert auf Event 'app.launch'."""
        app_id = payload.get("app_id")
        if app_id:
            self.launch(app_id)    