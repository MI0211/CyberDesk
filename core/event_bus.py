from __future__ import annotations     # fuer TypeHints
import logging                         # fuer Logs
from collections import defaultdict    # Ein intelligentes Dictionary, das automatisch eine leere Liste erstellt, falls der Schlüssel noch nicht existiert
from collections.abc import Callable   # Typ für aufrufbare Objekte (Funktionen), um sie als Typannotation zu nutzen
from typing import Any                 # Universeller Datentyp "Beliebig" für flexible Werte und Dictionaries


logger = logging.getLogger(__name__)   # Erstellt einen Logger, um Fehler und Ereignisse in der Anwendung aufzuzeichnen

EventHandler = Callable[[dict[str, Any]], None] # Ein Typ-Alias für Listener-Funktionen, die ein Dictionary entgegennehmen und nichts zurückgeben.


class EventBus:
    """Einfaches Publish/Subscribe-System."""
    
    def __init__(self) -> None:                                                  # Konstruktor der Klasse, der beim Erstellen der Instanz aufgerufen wird.
        self._subscribers: dict[str,list[EventHandler]] = defaultdict(list)      # Dictionary für Abonnenten; 
                                                                                 # falls das Event noch nicht existiert, wird automatisch eine leere Liste erstellt.
    
    
    def subscribe(self, event_name: str, handler: EventHandler) -> None:         # Methode zur Registrierung eines neuen Abonnenten für ein Event.
        """Registriert einen Handler fuer ein Event."""
        self._subscribers[event_name].append(handler)                            # Fügt die Handler-Funktion am Ende der Abonnentenliste hinzu.
        
        
    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:      # Methode zum Entfernen eines Abonnenten.
        """Entfernt einen Handler."""
        if handler in self._subscribers[event_name]:                            # Sicherheitsprüfung, ob der Handler in der Liste vorhanden ist.
            self._subscribers[event_name].remove(handler)                       # Entfernt den Handler aus der Liste.
            
            
    def publish(self, event_name: str, payload: dict[str, Any] | None = None) -> None:   # Methode zum Senden eines Events an alle Abonnenten mit optionalen Daten.
        """Sendet ein Event an alle Abonnenten."""
        payload = payload or {}                                                          # Falls keine Daten übergeben wurden, wird ein leeres Dictionary verwendet.
        for handler in list(self._subscribers[event_name]):                              # Schleife über alle Abonnenten des jeweiligen Events.
            try:                                                                         # Einleitung des Schutzblocks gegen Laufzeitfehler.
                handler(payload)                                                         # Ausführung der jeweiligen Handler-Funktion mit den Daten.
            except Exception:                                                            # Fängt unerwartete Fehler ab, falls ein Handler abstürzt.
                logger.exception("Handler fuer '%s' fehlgeschlagen", event_name)         # Protokolliert den Fehler im Log, ohne dass die gesamte Anwendung abstürzt.
                
                
                
event_bus = EventBus()                                                                  # Erstellung einer globalen Instanz des Event-Busses für das gesamte Projekt.
                          