import os

from PySide6.QtCore import Qt, QPoint, QSize
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect

class BaseApp(QWidget):
    BORDER_WIDTH = 6

    def __init__(self, app_id: str, title: str, event_bus):
        super().__init__()
        self.app_id = app_id
        self.app_title = title
        self.event_bus = event_bus
        self.window_id: str | None = None  # Wird vom WindowManager beim Öffnen gesetzt
        
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # Generischer Boden gegen zu kleines Zusammenziehen (Text/Buttons würden sich
        # sonst überlappen) - einzelne Apps setzen in ihrem build_ui() einen passenderen,
        # größeren Wert für ihren eigenen Inhalt.
        self.setMinimumSize(260, 180)

        self._dragging = False
        self._resizing = False
        self._resize_edge = None
        self._drag_position = QPoint()
        self._drag_global_pos = QPoint()
        self._normal_geometry = None
        self._is_maximized_custom = False
        
        self.setMouseTracking(True)
        self._init_ui()
        
        # Event-Filter für innere Widgets (z.B. Browser), damit Resize an den Rändern funktioniert
        self.installEventFilter(self)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QWidget(self)
        self.container.setObjectName("AppContainer")
        self.container.setMouseTracking(True)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(Qt.black)
        shadow.setOffset(0, 12)
        self.container.setGraphicsEffect(shadow)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        self.title_bar = QWidget()
        self.title_bar.setObjectName("AppTitleBar")
        self.title_bar.setFixedHeight(40)
        self.title_bar.setMouseTracking(True)
        
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)
        
        icon_path = self._resolve_icon_path()
        if icon_path:
            icon_label = QLabel()
            icon_label.setObjectName("AppTitleIcon")
            icon_label.setPixmap(QIcon(icon_path).pixmap(QSize(15, 15)))
            title_layout.addWidget(icon_label)
            title_layout.addSpacing(8)

        self.title_label = QLabel(self.app_title)
        self.title_label.setObjectName("AppTitleLabel")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        self.btn_min = QPushButton()
        self.btn_min.setObjectName("WindowBtnMin")
        self.btn_min.setFixedSize(12, 12)
        self.btn_min.clicked.connect(self.showMinimized)
        
        self.btn_max = QPushButton()
        self.btn_max.setObjectName("WindowBtnMax")
        self.btn_max.setFixedSize(12, 12)
        self.btn_max.clicked.connect(self._toggle_maximize)
        
        self.btn_close = QPushButton()
        self.btn_close.setObjectName("WindowBtnClose")
        self.btn_close.setFixedSize(12, 12)
        self.btn_close.clicked.connect(self._request_close)
        
        buttons_layout.addWidget(self.btn_min)
        buttons_layout.addWidget(self.btn_max)
        buttons_layout.addWidget(self.btn_close)
        title_layout.addLayout(buttons_layout)
        
        container_layout.addWidget(self.title_bar)
        
        self.content_widget = QWidget()
        self.content_widget.setObjectName("AppContentWidget")
        self.content_widget.setMouseTracking(True)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        
        container_layout.addWidget(self.content_widget)
        main_layout.addWidget(self.container)
        
        self.build_ui(self.content_layout)

    def eventFilter(self, watched, event) -> bool:
        """Leitet Mausereignisse von inneren Browser-Widgets an das Hauptfenster weiter."""
        if event.type() == event.Type.MouseMove:
            global_pos = event.globalPosition().toPoint()
            local_pos = self.mapFromGlobal(global_pos)
            
            if not self._dragging and not self._resizing:
                edge = self._get_resize_edge(local_pos)
                if edge in ("top_left", "bottom_right"):
                    self.setCursor(Qt.SizeFDiagCursor)
                elif edge in ("top_right", "bottom_left"):
                    self.setCursor(Qt.SizeBDiagCursor)
                elif edge in ("left", "right"):
                    self.setCursor(Qt.SizeHorCursor)
                elif edge in ("top", "bottom"):
                    self.setCursor(Qt.SizeVerCursor)
                else:
                    self.unsetCursor()

            if self._resizing and event.buttons() == Qt.LeftButton:
                diff = global_pos - self._drag_global_pos
                self._drag_global_pos = global_pos
                geom = self.geometry()

                if "left" in self._resize_edge:
                    geom.setLeft(geom.left() + diff.x())
                elif "right" in self._resize_edge:
                    geom.setRight(geom.right() + diff.x())

                if "top" in self._resize_edge:
                    geom.setTop(geom.top() + diff.y())
                elif "bottom" in self._resize_edge:
                    geom.setBottom(geom.bottom() + diff.y())

                if geom.width() >= self.minimumWidth() and geom.height() >= self.minimumHeight():
                    self.setGeometry(geom)
                return True

            elif self._dragging and event.buttons() == Qt.LeftButton:
                self.move(global_pos - self._drag_position)
                return True

        elif event.type() == event.Type.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                global_pos = event.globalPosition().toPoint()
                local_pos = self.mapFromGlobal(global_pos)
                edge = self._get_resize_edge(local_pos)
                if edge:
                    self._raise_and_activate()
                    self._resizing = True
                    self._resize_edge = edge
                    self._drag_global_pos = global_pos
                    return True
                elif self.title_bar.geometry().contains(local_pos):
                    self._raise_and_activate()
                    self._dragging = True
                    self._drag_position = global_pos - self.frameGeometry().topLeft()
                    return True

        elif event.type() == event.Type.MouseButtonRelease:
            if self._resizing or self._dragging:
                self._dragging = False
                self._resizing = False
                self._resize_edge = None
                self.unsetCursor()
                return True

        return super().eventFilter(watched, event)

    def _raise_and_activate(self) -> None:
        self.raise_()
        self.activateWindow()

    def _resolve_icon_path(self) -> str | None:
        """Sucht das App-Icon nach demselben Namensschema wie die AppRegistry."""
        candidates = [
            f"assets/images/{self.app_id}.svg",
            f"assets/images/{self.app_id}_icon.png",
            f"assets/images/{self.app_id}.png",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def build_ui(self, layout: QVBoxLayout) -> None:
        pass

    def showMinimized(self) -> None:
        """Blendet das Fenster aus und meldet es der Taskbar als minimiert."""
        self.hide()
        self.event_bus.publish("window.minimized", {
            "window_id": self.window_id,
            "app_id": self.app_id,
            "title": self.app_title,
            "icon": self._resolve_icon_path(),
        })

    def _toggle_maximize(self) -> None:
        if self._is_maximized_custom:
            if self._normal_geometry:
                self.setGeometry(self._normal_geometry)
            self._is_maximized_custom = False
        else:
            self._normal_geometry = self.geometry()
            if self.parent():
                parent_rect = self.parent().rect()
                self.setGeometry(parent_rect)
            self._is_maximized_custom = True

    def _get_resize_edge(self, pos: QPoint) -> str:
        rect = self.rect()
        x, y = pos.x(), pos.y()
        bw = self.BORDER_WIDTH

        left = x < bw
        right = x > rect.width() - bw
        top = y < bw
        bottom = y > rect.height() - bw

        if top and left: return "top_left"
        if top and right: return "top_right"
        if bottom and left: return "bottom_left"
        if bottom and right: return "bottom_right"
        
        if left: return "left"
        if right: return "right"
        if top: return "top"
        if bottom: return "bottom"
        return ""

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._raise_and_activate()
        if event.button() == Qt.LeftButton:
            edge = self._get_resize_edge(event.pos())
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._drag_global_pos = event.globalPosition().toPoint()
                event.accept()
            elif self.title_bar.geometry().contains(event.pos()):
                self._dragging = True
                self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        global_pos = event.globalPosition().toPoint()

        if not self._dragging and not self._resizing:
            edge = self._get_resize_edge(event.pos())
            if edge in ("top_left", "bottom_right"):
                self.setCursor(Qt.SizeFDiagCursor)
            elif edge in ("top_right", "bottom_left"):
                self.setCursor(Qt.SizeBDiagCursor)
            elif edge in ("left", "right"):
                self.setCursor(Qt.SizeHorCursor)
            elif edge in ("top", "bottom"):
                self.setCursor(Qt.SizeVerCursor)
            else:
                self.unsetCursor()

        if self._resizing and event.buttons() == Qt.LeftButton:
            diff = global_pos - self._drag_global_pos
            self._drag_global_pos = global_pos
            geom = self.geometry()

            if "left" in self._resize_edge:
                geom.setLeft(geom.left() + diff.x())
            elif "right" in self._resize_edge:
                geom.setRight(geom.right() + diff.x())

            if "top" in self._resize_edge:
                geom.setTop(geom.top() + diff.y())
            elif "bottom" in self._resize_edge:
                geom.setBottom(geom.bottom() + diff.y())

            if geom.width() >= self.minimumWidth() and geom.height() >= self.minimumHeight():
                self.setGeometry(geom)
            event.accept()

        elif self._dragging and event.buttons() == Qt.LeftButton:
            self.move(global_pos - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False
        self._resizing = False
        self._resize_edge = None
        self.unsetCursor()

    def _request_close(self) -> None:
        """Schließt das Fenster über den WindowManager (Event 'window.close'), statt
        self.close() direkt aufzurufen. Nur der WindowManager entfernt den Eintrag aus
        seiner eigenen Verwaltung und meldet 'window.closed' korrekt an die Taskbar -
        ein direkter self.close() blendet das Fenster nur aus, die App bleibt für
        WindowManager/Taskbar aber weiterhin als offen/laufend eingetragen."""
        self.event_bus.publish("window.close", {"window_id": self.window_id})

    def closeEvent(self, event) -> None:
        """Reines Qt-Aufräumen. on_close() und die 'window.closed'-Meldung übernimmt
        WindowManager.close_window() zentral, damit sie nicht doppelt/mit falscher
        window_id feuern, egal über welchen Weg das Fenster geschlossen wird."""
        super().closeEvent(event)