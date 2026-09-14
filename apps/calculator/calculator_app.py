import math
from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLineEdit,
    QPushButton,
    QStackedWidget,
)

from apps.base_app import BaseApp
from core.event_bus import event_bus


class CalculatorApp(BaseApp):
    """Taschenrechner mit Standardmodus und einem wissenschaftlichen Modus
    (trigonometrische Funktionen, Logarithmen, Potenzen, Konstanten ...)."""

    app_id = "calculator"
    title = "Taschenrechner"

    def __init__(self):
        super().__init__(app_id="calculator", title="Taschenrechner", event_bus=event_bus)
        self.setWindowTitle("Taschenrechner")

        try:
            with open("assets/styles/cyberpunk.qss", "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Style Datei nicht gefunden!")

    # -----------------------------------------------------------------
    # Aufbau der Gesamt-UI
    # -----------------------------------------------------------------
    def build_ui(self, layout) -> None:
        self.resize(380, 640)
        self.setMinimumSize(320, 480)  # sonst quetschen sich die Tasten im wiss. Modus

        # --- Umschalter Standard / Wissenschaftlich ---
        mode_bar = QHBoxLayout()
        mode_bar.setSpacing(8)

        self.btn_mode_standard = QPushButton("STANDARD")
        self.btn_mode_standard.setObjectName("calcModeBtnActive")
        self.btn_mode_standard.clicked.connect(lambda: self._switch_mode(0))

        self.btn_mode_scientific = QPushButton("WISSENSCHAFT")
        self.btn_mode_scientific.setObjectName("calcModeBtn")
        self.btn_mode_scientific.clicked.connect(lambda: self._switch_mode(1))

        mode_bar.addWidget(self.btn_mode_standard)
        mode_bar.addWidget(self.btn_mode_scientific)
        layout.addLayout(mode_bar)

        # --- Stack mit den beiden Modi ---
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_standard_page())
        self.stack.addWidget(self._build_scientific_page())
        layout.addWidget(self.stack)

    def _switch_mode(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.btn_mode_standard.setObjectName("calcModeBtnActive")
            self.btn_mode_scientific.setObjectName("calcModeBtn")
        else:
            self.btn_mode_standard.setObjectName("calcModeBtn")
            self.btn_mode_scientific.setObjectName("calcModeBtnActive")
        # Objektname wurde geändert -> Style neu anwenden
        for btn in (self.btn_mode_standard, self.btn_mode_scientific):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    @staticmethod
    def _display_style() -> str:
        return (
            "QLineEdit {"
            "background-color: #0A0A14;"
            "color: #00FFD1;"
            "border: 1px solid #FF2BD6;"
            "border-radius: 6px;"
            "padding: 10px 12px;"
            "font-size: 24px;"
            "font-family: 'JetBrains Mono';"
            "}"
        )

    @staticmethod
    def _op_btn_style() -> str:
        return (
            "QPushButton {"
            "background-color: #0A0A14; color: #FF2BD6;"
            "border: 1px solid #00FFD1; font-weight: bold; font-size: 15px;"
            "}"
            "QPushButton:hover {"
            "background-color: #FF2BD6; color: #0A0A14;"
            "}"
        )

    @staticmethod
    def _func_btn_style() -> str:
        return (
            "QPushButton {"
            "background-color: #0A0A14; color: #7A7A8C;"
            "border: 1px solid #7A7A8C; font-size: 13px;"
            "}"
            "QPushButton:hover {"
            "background-color: #7A7A8C; color: #0A0A14;"
            "}"
        )

    @staticmethod
    def _format(value: float) -> str:
        if isinstance(value, complex):
            return "Fehler"
        if value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return f"{value:.10g}"

    # ===================================================================
    # STANDARD-TASCHENRECHNER
    # ===================================================================
    def _build_standard_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 8, 0, 0)
        v.setSpacing(10)

        self._current = "0"
        self._stored_value = None
        self._pending_op = None
        self._reset_on_next_digit = False

        self.display = QLineEdit("0")
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.display.setStyleSheet(self._display_style())
        v.addWidget(self.display)

        grid = QGridLayout()
        grid.setSpacing(6)

        buttons = [
            ("C", 0, 0), ("⌫", 0, 1), ("%", 0, 2), ("/", 0, 3),
            ("7", 1, 0), ("8", 1, 1), ("9", 1, 2), ("*", 1, 3),
            ("4", 2, 0), ("5", 2, 1), ("6", 2, 2), ("-", 2, 3),
            ("1", 3, 0), ("2", 3, 1), ("3", 3, 2), ("+", 3, 3),
            ("±", 4, 0), ("0", 4, 1), (".", 4, 2), ("=", 4, 3),
        ]

        for text, row, col in buttons:
            btn = QPushButton(text)
            btn.setMinimumHeight(52)
            if text in ("/", "*", "-", "+", "="):
                btn.setStyleSheet(self._op_btn_style())
            elif text in ("C", "⌫", "%", "±"):
                btn.setStyleSheet(self._func_btn_style())
            else:
                btn.setStyleSheet("font-size: 16px;")

            btn.clicked.connect(partial(self._on_calc_button, text))
            grid.addWidget(btn, row, col)

        v.addLayout(grid)
        return page

    def _on_calc_button(self, text: str) -> None:
        if text.isdigit():
            self._input_digit(text)
        elif text == ".":
            self._input_decimal()
        elif text == "C":
            self._clear()
        elif text == "⌫":
            self._backspace()
        elif text == "±":
            self._negate()
        elif text == "%":
            self._percent()
        elif text in ("+", "-", "*", "/"):
            self._set_operator(text)
        elif text == "=":
            self._equals()

        self.display.setText(self._current)

    def _input_digit(self, digit: str) -> None:
        if self._current == "0" or self._reset_on_next_digit:
            self._current = digit
            self._reset_on_next_digit = False
        else:
            self._current += digit

    def _input_decimal(self) -> None:
        if self._reset_on_next_digit:
            self._current = "0"
            self._reset_on_next_digit = False
        if "." not in self._current:
            self._current += "."

    def _clear(self) -> None:
        self._current = "0"
        self._stored_value = None
        self._pending_op = None
        self._reset_on_next_digit = False

    def _backspace(self) -> None:
        if self._reset_on_next_digit:
            return
        self._current = self._current[:-1] or "0"

    def _negate(self) -> None:
        if self._current != "0":
            if self._current.startswith("-"):
                self._current = self._current[1:]
            else:
                self._current = "-" + self._current

    def _percent(self) -> None:
        try:
            self._current = self._format(float(self._current) / 100)
        except ValueError:
            pass

    def _set_operator(self, op: str) -> None:
        if self._pending_op and not self._reset_on_next_digit:
            self._equals()
        self._stored_value = float(self._current)
        self._pending_op = op
        self._reset_on_next_digit = True

    def _equals(self) -> None:
        if self._pending_op is None or self._stored_value is None:
            return
        try:
            current_value = float(self._current)
            result = self._apply_op(self._stored_value, current_value, self._pending_op)
            self._current = self._format(result)
        except ZeroDivisionError:
            self._current = "Fehler"
        finally:
            self._pending_op = None
            self._stored_value = None
            self._reset_on_next_digit = True

    @staticmethod
    def _apply_op(a: float, b: float, op: str) -> float:
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise ZeroDivisionError
            return a / b
        return b

    # ===================================================================
    # WISSENSCHAFTLICHER MODUS
    # ===================================================================

    # Button-Beschriftung -> Text, der in den Ausdruck eingefügt wird.
    # Alles ohne eigenen Eintrag wird 1:1 übernommen (Ziffern, Operatoren, Klammern).
    _SCI_INSERTS = {
        "sin": "sin(",
        "cos": "cos(",
        "tan": "tan(",
        "asin": "asin(",
        "acos": "acos(",
        "atan": "atan(",
        "√": "sqrt(",
        "log": "log(",
        "ln": "ln(",
        "π": "pi",
        "e": "e",
        "x^y": "**",
        "x²": "**2",
        "1/x": "**(-1)",
        "mod": "%",
        "EXP": "10**(",
        "!": "factorial(",
        "00": "00",
    }

    def _build_scientific_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 8, 0, 0)
        v.setSpacing(10)

        self._sci_expr = ""
        self._sci_deg_mode = True  # True = Grad (DEG), False = Bogenmaß (RAD)

        self.sci_display = QLineEdit("0")
        self.sci_display.setReadOnly(True)
        self.sci_display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sci_display.setStyleSheet(self._display_style())
        v.addWidget(self.sci_display)

        grid = QGridLayout()
        grid.setSpacing(5)

        # Funktionsblock (5 Reihen x 4 Spalten)
        func_rows = [
            ["sin", "cos", "tan", "DEG"],
            ["asin", "acos", "atan", "√"],
            ["log", "ln", "π", "e"],
            ["x^y", "x²", "1/x", "mod"],
            ["(", ")", "EXP", "!"],
        ]
        for r, row_items in enumerate(func_rows):
            for c, text in enumerate(row_items):
                btn = QPushButton(text)
                btn.setMinimumHeight(40)
                btn.setStyleSheet(self._func_btn_style())
                if text == "DEG":
                    self.btn_deg_toggle = btn
                    btn.clicked.connect(self._toggle_deg_mode)
                else:
                    btn.clicked.connect(partial(self._on_sci_button, text))
                grid.addWidget(btn, r, c)

        # Grundrechenarten-Block (5 Reihen x 4 Spalten), direkt darunter
        calc_rows = [
            ["C", "⌫", "±", "/"],
            ["7", "8", "9", "*"],
            ["4", "5", "6", "-"],
            ["1", "2", "3", "+"],
            ["0", "00", ".", "="],
        ]
        offset = len(func_rows)
        for r, row_items in enumerate(calc_rows):
            for c, text in enumerate(row_items):
                btn = QPushButton(text)
                btn.setMinimumHeight(48)
                if text in ("/", "*", "-", "+", "="):
                    btn.setStyleSheet(self._op_btn_style())
                elif text in ("C", "⌫", "±"):
                    btn.setStyleSheet(self._func_btn_style())
                else:
                    btn.setStyleSheet("font-size: 16px;")
                btn.clicked.connect(partial(self._on_sci_button, text))
                grid.addWidget(btn, offset + r, c)

        v.addLayout(grid)
        return page

    def _toggle_deg_mode(self) -> None:
        self._sci_deg_mode = not self._sci_deg_mode
        self.btn_deg_toggle.setText("DEG" if self._sci_deg_mode else "RAD")

    def _on_sci_button(self, text: str) -> None:
        if text == "C":
            self._sci_expr = ""
        elif text == "⌫":
            self._sci_expr = self._sci_expr[:-1]
        elif text == "±":
            self._sci_expr = self._sci_negate(self._sci_expr)
        elif text == "=":
            self._sci_evaluate()
        else:
            self._sci_expr += self._SCI_INSERTS.get(text, text)

        self.sci_display.setText(self._sci_expr or "0")

    @staticmethod
    def _sci_negate(expr: str) -> str:
        if not expr:
            return expr
        if expr.startswith("-(") and expr.endswith(")"):
            return expr[2:-1]
        return f"-({expr})"

    def _sci_namespace(self) -> dict:
        deg = self._sci_deg_mode

        def sin(x):
            return math.sin(math.radians(x)) if deg else math.sin(x)

        def cos(x):
            return math.cos(math.radians(x)) if deg else math.cos(x)

        def tan(x):
            return math.tan(math.radians(x)) if deg else math.tan(x)

        def asin(x):
            r = math.asin(x)
            return math.degrees(r) if deg else r

        def acos(x):
            r = math.acos(x)
            return math.degrees(r) if deg else r

        def atan(x):
            r = math.atan(x)
            return math.degrees(r) if deg else r

        def factorial(x):
            return math.factorial(int(round(x)))

        return {
            "sin": sin, "cos": cos, "tan": tan,
            "asin": asin, "acos": acos, "atan": atan,
            "sqrt": math.sqrt,
            "log": math.log10,
            "ln": math.log,
            "factorial": factorial,
            "pi": math.pi,
            "e": math.e,
            "__builtins__": {},
        }

    def _sci_evaluate(self) -> None:
        expr = self._sci_expr.strip()
        if not expr:
            return
        try:
            result = eval(expr, self._sci_namespace(), {})  # noqa: S307 - Namespace ist streng eingeschränkt
            self._sci_expr = self._format(result)
        except ZeroDivisionError:
            self._sci_expr = "Fehler"
        except Exception:
            self._sci_expr = "Fehler"
