"""Fake-Login-Screen: keine echte Authentifizierung, nur der visuelle Einstieg zum Desktop."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    QUrl,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRegion,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.paint_utils import paint_grid, paint_spotlight, paint_styled_background

_TAB_COLOR_ACTIVE = QColor(255, 255, 255, 255)
_TAB_COLOR_RESTING = QColor(255, 255, 255, 89)
_TAB_COLOR_HOVER = QColor(255, 255, 255, 153)


class _AuthBrandPanel(QWidget):
    """Linke Panel-Fläche mit dezentem Gitter-Hintergrund (Figma-Look)."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("AuthBrandPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        paint_styled_background(self, painter)
        paint_grid(painter, self.width(), self.height(), alpha=6)
        screen = self.window()
        if hasattr(screen, "spotlight_pos"):
            paint_spotlight(painter, self, screen.spotlight_pos)
        painter.end()


class _AuthFormPanel(QWidget):
    """Rechte Panel-Fläche — reiner Flachton, bekommt aber ebenfalls den Spotlight ab,
    damit das Glühen beim Wandern über die Trennlinie nicht abrupt aufhört."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("AuthFormPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._exclude_widget: QWidget | None = None

    def set_spotlight_exclusion(self, widget: QWidget) -> None:
        """Bereich (z.B. die Login-Karte), unter dem der Spotlight nie durchscheinen soll —
        dort gibt es kein Gitter, ein Glühen darunter wirkt dort inkonsequent."""
        self._exclude_widget = widget

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        paint_styled_background(self, painter)
        screen = self.window()
        if hasattr(screen, "spotlight_pos"):
            if self._exclude_widget is not None:
                # Abgerundetes Rechteck statt scharfem — sonst entsteht an der Ecke
                # ein harter 90°-Ausbiss im weichen radialen Glühen dahinter.
                exclude_rect = QRectF(self._exclude_widget.geometry())
                path = QPainterPath()
                path.addRoundedRect(exclude_rect, 14, 14)
                exclude_region = QRegion(path.toFillPolygon().toPolygon())
                clip = QRegion(self.rect()).subtracted(exclude_region)
                painter.setClipRegion(clip)
            paint_spotlight(painter, self, screen.spotlight_pos, peak_alpha=45)
        painter.end()


class _GradientLabel(QWidget):
    """Text mit horizontalem Farbverlauf, wie "Cyber-Workspace." im Figma-Entwurf
    (dort per CSS 'background-clip: text' — das gibt es in Qt-Stylesheets nicht,
    darum wird der Text hier direkt mit einem Gradient-Pen gemalt)."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.setObjectName("AuthHeadlineGradient")
        self._text = text

    def sizeHint(self):
        return self.fontMetrics().boundingRect(self._text).size()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(self.font())

        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, QColor("#a78bfa"))
        gradient.setColorAt(0.5, QColor("#818cf8"))
        gradient.setColorAt(1.0, QColor("#67e8f9"))

        painter.setPen(QPen(QBrush(gradient), 0))
        painter.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter, self._text)
        painter.end()


class _HoverFadeButton(QPushButton):
    """Button mit weich animiertem Farbwechsel beim Hover.

    Qt-Stylesheets kennen kein CSS-'transition', darum wird die Textfarbe hier
    manuell per QVariantAnimation zwischen Ruhe- und Hover-Farbe überblendet.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.NoFocus)
        self._resting_color = _TAB_COLOR_RESTING
        self._hover_color = _TAB_COLOR_HOVER
        self._current_color = self._resting_color
        self._anim: QVariantAnimation | None = None
        self._apply_color(self._resting_color)

    def set_colors(self, resting: QColor, hover: QColor) -> None:
        self._resting_color = resting
        self._hover_color = hover
        if not self.underMouse():
            self._apply_color(resting)

    def enterEvent(self, event) -> None:
        self._animate_to(self._hover_color)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_to(self._resting_color)
        super().leaveEvent(event)

    def _animate_to(self, target: QColor) -> None:
        anim = QVariantAnimation(self)
        anim.setDuration(150)
        anim.setStartValue(self._current_color)
        anim.setEndValue(target)
        anim.valueChanged.connect(self._apply_color)
        anim.start()
        self._anim = anim

    def _apply_color(self, color: QColor) -> None:
        self._current_color = color
        self.setStyleSheet(
            f"color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alphaF():.3f});"
        )


class _CollapsibleField(QWidget):
    """Klappt sein Kind-Widget weich ein/aus (maximumHeight-Animation).

    So wirkt der Wechsel Login↔Register nicht wie ein Sprung zwischen zwei
    verschiedenen Formularen, sondern wie ein weiches Erweitern/Schrumpfen
    desselben Formulars.
    """

    def __init__(self, inner: QWidget) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(inner)
        self._inner = inner
        self._anim: QParallelAnimationGroup | None = None

        self._opacity_effect = QGraphicsOpacityEffect(inner)
        self._opacity_effect.setOpacity(0.0)
        inner.setGraphicsEffect(self._opacity_effect)

        self.setMaximumHeight(0)

    def set_expanded(self, expanded: bool, animate: bool) -> None:
        target_height = self._inner.sizeHint().height() if expanded else 0
        target_opacity = 1.0 if expanded else 0.0

        if expanded:
            self._inner.setVisible(True)

        if not animate:
            self.setMaximumHeight(target_height)
            self._opacity_effect.setOpacity(target_opacity)
            if not expanded:
                self._inner.setVisible(False)
            return

        height_anim = QPropertyAnimation(self, b"maximumHeight", self)
        height_anim.setDuration(360)
        height_anim.setEasingCurve(QEasingCurve.InOutCubic)
        height_anim.setStartValue(self.maximumHeight())
        height_anim.setEndValue(target_height)

        opacity_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        opacity_anim.setDuration(360)
        opacity_anim.setEasingCurve(QEasingCurve.InOutCubic)
        opacity_anim.setStartValue(self._opacity_effect.opacity())
        opacity_anim.setEndValue(target_opacity)

        group = QParallelAnimationGroup(self)
        group.addAnimation(height_anim)
        group.addAnimation(opacity_anim)
        if not expanded:
            group.finished.connect(lambda: self._inner.setVisible(False))
        group.start()
        self._anim = group


class AuthScreen(QWidget):
    """Zeigt Login-/Register-Felder an. Jede plausible Eingabe führt direkt zum Desktop —
    es gibt keinen echten Auth-Server und keine Datenbank dahinter (bewusst, siehe Handbuch:
    "keine echte Netzwerkkommunikation")."""

    def __init__(self, on_success: Callable[[], None]) -> None:
        super().__init__()
        self.setObjectName("AuthScreen")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._on_success = on_success
        self._tab = "login"
        self._tab_anim: QPropertyAnimation | None = None

        # Violetter Spotlight, der der Maus mit sanfter Verzögerung folgt (lerp
        # statt direktem Sprung). In globalen Koordinaten gespeichert, weil er
        # über zwei separate Panel-Widgets hinweg gezeichnet wird.
        self.spotlight_pos = QPointF(0, 0)
        self._spotlight_target = QPointF(0, 0)

        self._build_ui()

        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        quit_shortcut.activated.connect(QApplication.instance().quit)

        QApplication.instance().installEventFilter(self)
        self._spotlight_timer = QTimer(self)
        self._spotlight_timer.timeout.connect(self._tick_spotlight)
        self._spotlight_timer.start(20)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._update_tab_highlight(animate=False)
        if self.spotlight_pos == QPointF(0, 0):
            center = self.mapToGlobal(self.rect().center())
            self.spotlight_pos = QPointF(center)
            self._spotlight_target = QPointF(center)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.MouseMove:
            self._spotlight_target = QPointF(event.globalPosition())
        return super().eventFilter(obj, event)

    def _tick_spotlight(self) -> None:
        dx = self._spotlight_target.x() - self.spotlight_pos.x()
        dy = self._spotlight_target.y() - self.spotlight_pos.y()
        if abs(dx) < 0.3 and abs(dy) < 0.3:
            return
        self.spotlight_pos = QPointF(
            self.spotlight_pos.x() + dx * 0.09,
            self.spotlight_pos.y() + dy * 0.09,
        )
        self._brand_panel.update()
        self._form_panel_widget.update()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_brand_panel(), 3)
        root.addWidget(self._build_divider())
        root.addWidget(self._build_form_panel(), 2)

    def _build_divider(self) -> QWidget:
        """Echtes 1px-Trennelement statt einer gemalten Linie, damit es garantiert
        exakt zwischen den beiden Panels sitzt, ohne Rundungs-Konflikt mit dem Gitter."""
        divider = QWidget()
        divider.setObjectName("AuthDivider")
        divider.setAttribute(Qt.WA_StyledBackground, True)
        divider.setFixedWidth(1)
        return divider

    def _build_brand_panel(self) -> QWidget:
        panel = _AuthBrandPanel()
        self._brand_panel = panel

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(64, 56, 64, 56)

        layout.addWidget(self._build_brand_row())

        layout.addStretch()

        eyebrow = QLabel("CYBER DESKTOP · V1.0")
        eyebrow.setObjectName("AuthEyebrow")
        layout.addWidget(eyebrow)

        headline_line1 = QLabel("Dein sicherer")
        headline_line1.setObjectName("AuthHeadline")
        layout.addWidget(headline_line1)

        headline_line2 = _GradientLabel("Cyber-Workspace.")
        layout.addWidget(headline_line2)
        layout.addSpacing(12)

        sub = QLabel(
            "Melde dich an, um auf deine verschlüsselte\n"
            "Desktop-Umgebung zuzugreifen — schnell, privat,\n"
            "immer verfügbar."
        )
        sub.setObjectName("AuthBrandSub")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        layout.addStretch()

        presentation_link = QLabel(
            'Für die Präsentation klicken Sie: '
            '<a href="#presentation" style="color:#a78bfa; text-decoration:underline;">hier</a>'
        )
        presentation_link.setObjectName("AuthPresentationLink")
        presentation_link.setTextFormat(Qt.RichText)
        presentation_link.setOpenExternalLinks(False)
        presentation_link.setCursor(Qt.PointingHandCursor)
        presentation_link.linkActivated.connect(self._open_presentation)
        layout.addWidget(presentation_link)
        layout.addSpacing(10)

        quit_btn = QPushButton("Beenden (Strg+Q)")
        quit_btn.setObjectName("AuthQuitButton")
        quit_btn.setCursor(Qt.PointingHandCursor)
        quit_btn.setFocusPolicy(Qt.NoFocus)
        quit_btn.clicked.connect(QApplication.instance().quit)
        layout.addWidget(quit_btn, alignment=Qt.AlignLeft)

        return panel

    def _build_brand_row(self) -> QWidget:
        """Logo-Badge (violettes Quadrat mit Punkt) + Markenname, wie im Figma-Entwurf."""
        row = QWidget()
        row.setObjectName("AuthBrandRow")
        row.setAttribute(Qt.WA_StyledBackground, True)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        mark = QWidget()
        mark.setObjectName("AuthLogoMark")
        mark.setAttribute(Qt.WA_StyledBackground, True)
        mark.setFixedSize(28, 28)
        mark_layout = QVBoxLayout(mark)
        mark_layout.setContentsMargins(0, 0, 0, 0)
        mark_layout.setAlignment(Qt.AlignCenter)

        dot = QWidget()
        dot.setObjectName("AuthLogoDot")
        dot.setAttribute(Qt.WA_StyledBackground, True)
        dot.setFixedSize(10, 10)
        mark_layout.addWidget(dot)

        brand = QLabel("CyberDesk")
        brand.setObjectName("AuthBrand")

        row_layout.addWidget(mark)
        row_layout.addWidget(brand)
        row_layout.addStretch()
        return row

    def _build_tab_switcher(self) -> QWidget:
        """Anmelden/Registrieren-Umschalter mit gleitendem Highlight (Figma-Look)."""
        container = QWidget()
        container.setObjectName("AuthTabSwitcher")
        container.setAttribute(Qt.WA_StyledBackground, True)
        container.setFixedHeight(38)

        self._tab_highlight = QWidget(container)
        self._tab_highlight.setObjectName("AuthTabHighlight")
        self._tab_highlight.setAttribute(Qt.WA_StyledBackground, True)

        tabs_layout = QHBoxLayout(container)
        tabs_layout.setContentsMargins(4, 4, 4, 4)
        tabs_layout.setSpacing(0)

        self._login_tab_btn = _HoverFadeButton("ANMELDEN")
        self._login_tab_btn.setObjectName("AuthTabButton")
        self._login_tab_btn.setCursor(Qt.PointingHandCursor)
        self._login_tab_btn.clicked.connect(lambda: self._switch_tab("login"))

        self._register_tab_btn = _HoverFadeButton("REGISTRIEREN")
        self._register_tab_btn.setObjectName("AuthTabButton")
        self._register_tab_btn.setCursor(Qt.PointingHandCursor)
        self._register_tab_btn.clicked.connect(lambda: self._switch_tab("register"))

        tabs_layout.addWidget(self._login_tab_btn)
        tabs_layout.addWidget(self._register_tab_btn)

        return container

    def _build_switch_link(self) -> QWidget:
        """Kleiner Zeilentext unten: "Noch kein Account? Registrieren" ↔ umgekehrt."""
        row = QWidget()
        row.setObjectName("AuthSwitchRow")
        row.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignCenter)

        self._switch_label = QLabel("Noch kein Account?")
        self._switch_label.setObjectName("AuthSwitchLabel")

        self._switch_btn = QPushButton("Registrieren")
        self._switch_btn.setObjectName("AuthSwitchButton")
        self._switch_btn.setCursor(Qt.PointingHandCursor)
        self._switch_btn.setFocusPolicy(Qt.NoFocus)
        self._switch_btn.clicked.connect(
            lambda: self._switch_tab("register" if self._tab == "login" else "login")
        )

        layout.addWidget(self._switch_label)
        layout.addWidget(self._switch_btn)
        return row

    def _build_form_panel(self) -> QWidget:
        panel = _AuthFormPanel()
        self._form_panel_widget = panel

        outer = QVBoxLayout(panel)
        outer.setAlignment(Qt.AlignCenter)

        card = QWidget()
        card.setObjectName("AuthCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setFixedWidth(360)
        form = QVBoxLayout(card)
        form.setSpacing(14)

        self.title_label = QLabel("Willkommen zurück")
        self.title_label.setObjectName("AuthTitle")
        form.addWidget(self.title_label)

        self.subtitle_label = QLabel("Melde dich an, um fortzufahren.")
        self.subtitle_label.setObjectName("AuthSubtitle")
        form.addWidget(self.subtitle_label)
        form.addSpacing(6)

        form.addWidget(self._build_tab_switcher())
        form.addSpacing(4)

        self.name_input = QLineEdit()
        self.name_input.setObjectName("AuthInput")
        self.name_input.setPlaceholderText("Vollständiger Name")
        self._name_field = _CollapsibleField(self.name_input)
        form.addWidget(self._name_field)

        self.email_input = QLineEdit()
        self.email_input.setObjectName("AuthInput")
        self.email_input.setPlaceholderText("E-Mail-Adresse")
        form.addWidget(self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setObjectName("AuthInput")
        self.password_input.setPlaceholderText("Passwort")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self._handle_submit)
        form.addWidget(self.password_input)

        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setObjectName("AuthInput")
        self.confirm_password_input.setPlaceholderText("Passwort bestätigen")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.returnPressed.connect(self._handle_submit)
        self._confirm_field = _CollapsibleField(self.confirm_password_input)
        form.addWidget(self._confirm_field)

        self.error_label = QLabel("")
        self.error_label.setObjectName("AuthError")
        self.error_label.hide()
        form.addWidget(self.error_label)

        self.submit_btn = QPushButton("Anmelden")
        self.submit_btn.setObjectName("AuthSubmitButton")
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.submit_btn.clicked.connect(self._handle_submit)
        form.addWidget(self.submit_btn)

        form.addSpacing(4)
        form.addWidget(self._build_switch_link())

        outer.addWidget(card)
        panel.set_spotlight_exclusion(card)
        self._apply_tab_state(animate=False)
        return panel

    def _switch_tab(self, tab: str) -> None:
        if tab == self._tab:
            return
        self._tab = tab
        self.error_label.hide()
        self._apply_tab_state(animate=True)
        self._update_tab_highlight(animate=True)

    def _apply_tab_state(self, animate: bool) -> None:
        is_register = self._tab == "register"

        self._name_field.set_expanded(is_register, animate)
        self._confirm_field.set_expanded(is_register, animate)

        self.title_label.setText("Account erstellen" if is_register else "Willkommen zurück")
        self.subtitle_label.setText(
            "Erstelle deinen CyberDesk-Account." if is_register else "Melde dich an, um fortzufahren."
        )
        self.submit_btn.setText("Account erstellen" if is_register else "Anmelden")

        self._switch_label.setText("Bereits registriert?" if is_register else "Noch kein Account?")
        self._switch_btn.setText("Anmelden" if is_register else "Registrieren")

        self._login_tab_btn.set_colors(
            _TAB_COLOR_ACTIVE if not is_register else _TAB_COLOR_RESTING,
            _TAB_COLOR_ACTIVE if not is_register else _TAB_COLOR_HOVER,
        )
        self._register_tab_btn.set_colors(
            _TAB_COLOR_ACTIVE if is_register else _TAB_COLOR_RESTING,
            _TAB_COLOR_ACTIVE if is_register else _TAB_COLOR_HOVER,
        )

    def _update_tab_highlight(self, animate: bool) -> None:
        target_btn = self._register_tab_btn if self._tab == "register" else self._login_tab_btn
        target_rect = target_btn.geometry()
        if target_rect.isEmpty():
            return

        if animate:
            anim = QPropertyAnimation(self._tab_highlight, b"geometry", self)
            anim.setDuration(220)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.setStartValue(self._tab_highlight.geometry())
            anim.setEndValue(target_rect)
            anim.start()
            self._tab_anim = anim
        else:
            self._tab_highlight.setGeometry(target_rect)

    def _open_presentation(self, _href: str) -> None:
        """Öffnet die eigenständige Präsentations-Datei im System-Standardbrowser."""
        path = Path("CyberDesk_Praesentation.html").resolve()
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            self.error_label.setText("Präsentation nicht gefunden: CyberDesk_Praesentation.html")
            self.error_label.show()

    def _handle_submit(self) -> None:
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if self._tab == "register":
            name = self.name_input.text().strip()
            confirm = self.confirm_password_input.text()
            if not name or not email or not password:
                self.error_label.setText("Bitte alle Felder ausfüllen.")
                self.error_label.show()
                return
            if password != confirm:
                self.error_label.setText("Passwörter stimmen nicht überein.")
                self.error_label.show()
                return
        elif not email or not password:
            self.error_label.setText("Bitte E-Mail und Passwort eingeben.")
            self.error_label.show()
            return

        self.error_label.hide()
        self._on_success()
