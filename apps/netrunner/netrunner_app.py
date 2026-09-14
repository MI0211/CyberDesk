from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget, QSizePolicy
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Qt
from apps.base_app import BaseApp
from core.event_bus import event_bus

class NetrunnerApp(BaseApp):
    app_id = "netrunner"
    title = "NetRunner v1.0"

    def __init__(self):
        super().__init__(app_id="netrunner", title="NetRunner v1.0", event_bus=event_bus)
        self.setWindowTitle("NetRunner v1.0")
        
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        if hasattr(self, 'container') and self.container.graphicsEffect():
            self.container.setGraphicsEffect(None)

        # Kleinerer Radius nur für dieses Fenster: bei 12px (Standard) bräuchte
        # der Browser-Rand zu viel Abstand, um nicht "über" die Rundung zu ragen.
        # Bei 4px reicht ein schmaler Abstand für eine echte dünne Linie.
        # WICHTIG: mit Selektor "#AppContainer { ... }" statt einer nackten Regel -
        # eine nackte Regel ohne Selektor bricht sonst die QSS-Kaskade für alle
        # Kind-Widgets (die runden Fensterknöpfe wurden dadurch eckig).
        self.container.setStyleSheet("#AppContainer { border-radius: 4px; }")

        try:
            with open("assets/styles/cyberpunk.qss", "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Style Datei nicht gefunden!")

    def build_ui(self, layout) -> None:
        self.resize(1000, 700)

        # QWebEngineView ist ein zusammengesetztes Widget (Chromium), setMask() darauf ist
        # unzuverlässig (das Resizing der inneren Ebene läuft asynchron und hinkt dem
        # Qt-Layout hinterher). Deshalb wird die Ecken-Rundung stattdessen über einen
        # kleinen Container-Radius (4px, siehe __init__) + minimalen Abstand gelöst -
        # so liest sich die Kante als dünne Linie statt als Rahmen.
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        nav_bar = QHBoxLayout()
        nav_bar.setContentsMargins(0, 0, 0, 0)
        nav_bar.setSpacing(4)

        back_btn = QPushButton("←")
        back_btn.setObjectName("NetNavIconButton")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(lambda: self.browser.back())

        forward_btn = QPushButton("→")
        forward_btn.setObjectName("NetNavIconButton")
        forward_btn.setCursor(Qt.PointingHandCursor)
        forward_btn.clicked.connect(lambda: self.browser.forward())

        reload_btn = QPushButton("↻")
        reload_btn.setObjectName("NetNavIconButton")
        reload_btn.setCursor(Qt.PointingHandCursor)
        reload_btn.clicked.connect(lambda: self.browser.reload())

        nav_bar.addWidget(back_btn)
        nav_bar.addWidget(forward_btn)
        nav_bar.addWidget(reload_btn)
        nav_bar.addSpacing(6)

        self.url_bar = QLineEdit()
        self.url_bar.setObjectName("NetUrlBar")
        self.url_bar.setPlaceholderText("Enter URL (e.g. google.com)...")
        self.url_bar.returnPressed.connect(self.load_url)

        go_btn = QPushButton("Go")
        go_btn.setObjectName("NetConnectButton")
        go_btn.setCursor(Qt.PointingHandCursor)
        go_btn.clicked.connect(self.load_url)

        nav_bar.addWidget(self.url_bar)
        nav_bar.addWidget(go_btn)

        nav_container = QWidget()
        nav_container.setObjectName("NetNavBar")
        nav_container.setLayout(nav_bar)
        layout.addWidget(nav_container)

        self.browser = QWebEngineView()
        self.browser.setObjectName("NetBrowserView")
        self.browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.browser.setMinimumSize(200, 150)

        self.browser.setUrl(QUrl("https://www.google.com"))
        layout.addWidget(self.browser)

        self.browser.setFocus()

    def load_url(self):
        url_text = self.url_bar.text().strip()
        if not url_text:
            return
            
        if not url_text.startswith("http://") and not url_text.startswith("https://"):
            url_text = "https://" + url_text
            
        self.browser.setUrl(QUrl(url_text))