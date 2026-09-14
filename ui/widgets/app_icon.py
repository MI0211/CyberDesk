import os                                                                                # Importiert das Modul für Betriebssystem-Pfadoperationen
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QToolButton                     # Importiert Schaltflächen- und Schatten-Komponenten für Desktop-Icons
from PySide6.QtCore import QSize, Qt                                                     # Importiert Klassen für Größen, Systemkonstanten
from PySide6.QtGui import QColor, QIcon                                                  # Importiert die Klassen zum Laden/Verarbeiten von Grafiken und Farben
from core.event_bus import event_bus                                                     # Importiert den zentralen Event-Bus für das Start-Signal


class AppIcon(QToolButton):                                                              # Definiert die Icon-Klasse, die von QToolButton erbt
    
    def __init__(self, app_id, title, icon_path):                                        # Konstruktor mit App-ID, Anzeigename und Bildpfad
        super().__init__()                                                               # Initialisiert die Basisklasse QToolButton im Qt-System
        
        # Path wird geprintet, um es in die Konsole zu sehen!
        abs_path = os.path.abspath(icon_path)                                            # Konvertiert den relativen Bildpfad in einen absoluten Pfad
        print(f"DEBUG: Suche Icon unter: {abs_path}")                                    # Gibt den gesuchten Pfad zur Fehlersuche in der Konsole aus
        
        if not os.path.exists(icon_path):                                                # Überprüft, ob die Icon-Datei tatsächlich existiert
            print(f"!!! FEHLER: Datei nicht gefunden: {icon_path} !!!")                  # Schlägt Alarm in der Konsole, falls die Datei fehlt

        self.setText(title)                                                              # Setzt den Text, der als Beschriftung unter dem Icon angezeigt wird.
                                                                                         # Selbst Variable "title" muss sich in app.py Datei befinden!
        
        self.app_id = app_id                                                             # Speichert die eindeutige ID direkt im Widget-Objekt
        
        self.setFixedSize(104, 88)                                                       # Breiter als vorher (war 75px) — lange Titel wie "NetRunner v1.0"
                                                                                         # wurden sonst mit "..." abgeschnitten.
        
        self.setIcon(QIcon(icon_path))                                                   # Erstellt das Qt-Icon-Objekt und weist es der Schaltfläche zu
                                                                                         # Selbst variable "icon_path" befindet sich in desktop.py Datei
                                                                                         # und erbt der Name automatisch von "app_id". 
                                                                                         # Icons befinden sich in assets/images und muessen 
                                                                                         # so benannt werden: "app_id"_icon.png 
                                                                                         # und Icon wird automatisch zugewiesen!!
        
        self.setIconSize(QSize(26, 26))                                                  # Kleineres Icon-Glyph mit Luft im Button, analog zum Figma-Verhältnis (24px in 48px Box)
        
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)                              # Platziert den Text zentriert direkt unter dem Bild
        self.setAutoRaise(True)                                                          # Aktiviert den transparenten Flat-Modus mit Hover-Effekt bei Mauszeiger
        self.setObjectName("appIcon")                                                    # Setzt die Objekt-ID für gezieltes Styling via Stylesheet (QSS)
        
        self.clicked.connect(self.on_click)                                              # Verbindet den Klick auf das Icon mit की Methode on_click

        # Dunkler Schlagschatten (wie bei echten Windows-Desktop-Icons) — sorgt dafür,
        # dass Icon-Glyph + Beschriftung auf JEDEM Hintergrundbild lesbar bleiben, auch
        # auf hellen/bunten Wallpaper-Stellen, statt sich mit dem Motiv zu vermischen.
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setColor(QColor(0, 0, 0, 190))
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        # --- ZIEHEN & VERSCHIEBEN INITIALISIERUNG ---
        self._drag_start_pos = None                                                      # Speichert die Startposition für das Verschieben

    def on_click(self):                                                                  # Methode, die beim Klicken auf das Icon ausgeführt wird
        event_bus.publish("app.launch", {"app_id": self.app_id})                         # Sendet das Start-Signal mit की App-ID an den Event-Bus

    def mousePressEvent(self, event):                                                    # Event bei Mausklick
        if event.button() == Qt.MouseButton.LeftButton:                                  # Prüfung auf linke Maustaste
            self._drag_start_pos = event.pos()                                           # Merkt sich den Klickpunkt
            self._is_dragging = False                                                    # Flag zurücksetzen bei neuem Klick
        super().mousePressEvent(event)                                                   # Leitet das Event weiter

    def mouseMoveEvent(self, event):                                                     # Event bei Mausbewegung
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_start_pos:
            # Prüfen, wie weit sich die Maus bewegt hat (Manhattan-Distanz)
            movement = (event.pos() - self._drag_start_pos).manhattanLength()
            if movement > 5:                                                             # Bei mehr als 5 Pixel Bewegung ist es ein Drag
                self._is_dragging = True
                
            if getattr(self, "_is_dragging", False):
                new_pos = self.mapToParent(event.pos()) - self._drag_start_pos
                self.move(new_pos)                                                      # Bewegt das Icon
                return                                                                  # Event blockieren, damit kein Klick ausgelöst wird
        super().mouseMoveEvent(event)                                                   # Reicht das Event weiter

    def mouseReleaseEvent(self, event):                                                  # Event beim Loslassen der Taste
        self._drag_start_pos = None                                                      # Setzt den Startpunkt zurück
        
        if getattr(self, "_is_dragging", False):
            # Es war ein Drag-Vorgang. Event akzeptieren, um on_click zu verhindern
            self._is_dragging = False
            event.accept()
            return
        
        # Wenn nicht gezogen wurde, ganz normalen Klick ausführen
        super().mouseReleaseEvent(event)