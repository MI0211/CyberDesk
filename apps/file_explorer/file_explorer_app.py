from datetime import datetime

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from apps.base_app import BaseApp
from core.event_bus import event_bus
from services import virtual_fs

_FOLDERS = ["Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"]


def _format_size(size_bytes: float) -> str:
    if size_bytes < 0:
        return "—"
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            text = f"{value:.0f}" if value == int(value) else f"{value:.1f}"
            return f"{text} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _format_date(iso_date: str) -> str:
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")  # noqa: DTZ007 - nur Anzeige, kein Vergleich
    except ValueError:
        return iso_date


class _SortableItem(QTableWidgetItem):
    """QTableWidgetItem, das nach einem eigenen Schlüssel vergleicht statt nach dem
    angezeigten Text — sonst würde z.B. "820 KB" alphabetisch vor "4.2 MB" landen
    (Textvergleich) statt nach echter Byte-Größe / echtem Datum sortiert zu werden."""

    def __init__(self, text: str, sort_key) -> None:
        super().__init__(text)
        self._sort_key = sort_key

    def __lt__(self, other) -> bool:
        if isinstance(other, _SortableItem):
            return self._sort_key < other._sort_key
        return super().__lt__(other)


class FileExplorerApp(BaseApp):
    """Zeigt Ordner-Sidebar + Dateiliste, gestützt auf services/virtual_fs.py — ein
    echter, gemeinsamer JSON-Baum (data/filesystem.json) statt einer eigenen, flachen
    Liste pro App. Ordner wie "Projects" lassen sich per Doppelklick wirklich öffnen;
    Dateien anlegen/löschen und Spalten sortieren (auf-/absteigend, echter Größen-/
    Datumsvergleich statt Textvergleich) funktionieren wie zuvor."""

    app_id = "file_explorer"
    title = "Datei-Explorer"

    def __init__(self):
        super().__init__(app_id="file_explorer", title="Datei-Explorer", event_bus=event_bus)
        self.setWindowTitle("Datei-Explorer")

        try:
            with open("assets/styles/cyberpunk.qss", "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Style Datei nicht gefunden!")

    def build_ui(self, layout) -> None:
        self.resize(740, 500)
        self.setMinimumSize(600, 380)  # 150px feste Sidebar + Tabelle mit 4 Spalten + Toolbar
        layout.setSpacing(0)
        self._current_path: list[str] = ["Documents"]  # ab Wurzel, erster Eintrag = Location

        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_main_area(), 1)
        layout.addLayout(body)

        self._navigate_to(self._current_path)

    # ------------------------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("explorerSidebar")
        panel.setFixedWidth(150)

        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 10, 0, 10)
        v.setSpacing(0)

        heading = QLabel("LOCATIONS")
        heading.setObjectName("explorerSidebarHeading")
        v.addWidget(heading)

        self.folder_list = QListWidget()
        self.folder_list.setObjectName("explorerFolderList")
        self.folder_list.setFrameShape(QListWidget.NoFrame)
        for name in _FOLDERS:
            self.folder_list.addItem(QListWidgetItem(name))
        self.folder_list.setCurrentRow(1)  # "Documents" ist der Startordner
        self.folder_list.currentTextChanged.connect(self._on_location_changed)
        v.addWidget(self.folder_list)

        return panel

    def _build_main_area(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("explorerMainArea")
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        toolbar_widget = QWidget()
        toolbar_widget.setObjectName("explorerToolbar")
        toolbar = QHBoxLayout(toolbar_widget)
        toolbar.setContentsMargins(14, 8, 14, 8)
        toolbar.setSpacing(8)

        self.up_btn = QPushButton("↑ Nach oben")
        self.up_btn.setObjectName("explorerUpBtn")
        self.up_btn.clicked.connect(self._go_up)
        toolbar.addWidget(self.up_btn)

        self.path_label = QLabel()
        self.path_label.setObjectName("explorerPathLabel")
        toolbar.addWidget(self.path_label)
        toolbar.addStretch()

        new_folder_btn = QPushButton("+ Neuer Ordner")
        new_folder_btn.setObjectName("explorerNewBtn")
        new_folder_btn.clicked.connect(self._new_folder)
        toolbar.addWidget(new_folder_btn)

        new_btn = QPushButton("+ Neue Datei")
        new_btn.setObjectName("explorerNewBtn")
        new_btn.clicked.connect(self._new_file)
        toolbar.addWidget(new_btn)

        self.delete_btn = QPushButton("Löschen")
        self.delete_btn.setObjectName("explorerDeleteBtn")
        self.delete_btn.clicked.connect(self._delete_selected)
        toolbar.addWidget(self.delete_btn)

        v.addWidget(toolbar_widget)

        self.table = QTableWidget(0, 4)
        self.table.setObjectName("explorerTable")
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Size", "Modified"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)  # Klick auf Spaltenkopf sortiert auf-/absteigend
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)

        self.table.itemSelectionChanged.connect(self._update_status)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        v.addWidget(self.table, 1)

        self.status_label = QLabel()
        self.status_label.setObjectName("explorerStatusLabel")
        v.addWidget(self.status_label)

        return panel

    # ------------------------------------------------------------------
    # Navigation im VirtualFS-Baum (services/virtual_fs.py)
    # ------------------------------------------------------------------
    def _current_entries(self) -> list[dict]:
        return virtual_fs.list_dir(self._current_path)

    def _entry_by_name(self, name: str) -> dict | None:
        return next((e for e in self._current_entries() if e["name"] == name), None)

    def _navigate_to(self, path: list[str]) -> None:
        self._current_path = path
        self.path_label.setText("CyberDesk / " + " / ".join(self._current_path))
        self.up_btn.setEnabled(len(self._current_path) > 1)
        self._populate_table()

    def _go_up(self) -> None:
        if len(self._current_path) > 1:
            self._navigate_to(self._current_path[:-1])

    def _on_location_changed(self, name: str) -> None:
        if name:
            self._navigate_to([name])

    def _on_row_double_clicked(self, row: int, _column: int) -> None:
        name = self.table.item(row, 0).text()
        entry = self._entry_by_name(name)
        if entry and entry["is_dir"]:
            self._navigate_to([*self._current_path, name])

    # ------------------------------------------------------------------
    # Tabelle
    # ------------------------------------------------------------------
    def _populate_table(self) -> None:
        entries = self._current_entries()
        self.table.setSortingEnabled(False)  # während des Befüllens Sortierung aus
        self.table.setRowCount(len(entries))
        for row, info in enumerate(entries):
            self.table.setItem(row, 0, _SortableItem(info["name"], info["name"].lower()))
            self.table.setItem(row, 1, _SortableItem(info["type"], info["type"].lower()))
            self.table.setItem(row, 2, _SortableItem(_format_size(info["size_bytes"]), info["size_bytes"]))
            self.table.setItem(row, 3, _SortableItem(_format_date(info["modified"]), info["modified"]))
        self.table.setSortingEnabled(True)
        self._update_status()

    def _selected_row_name(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.table.item(rows[0].row(), 0).text()

    def _update_status(self) -> None:
        name = self._selected_row_name()
        selection_text = f"Selected: {name}" if name else "Nothing selected"
        self.status_label.setText(f"{self.table.rowCount()} items · {selection_text}")

    # ------------------------------------------------------------------
    def _new_file(self) -> None:
        name, ok = QInputDialog.getText(self, "Neue Datei", "Dateiname:")
        name = name.strip()
        if not ok or not name:
            return
        if not virtual_fs.create_file(self._current_path, name):
            self.status_label.setText(f"„{name}“ existiert hier bereits.")
            return
        self._populate_table()

    def _new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "Neuer Ordner", "Ordnername:")
        name = name.strip()
        if not ok or not name:
            return
        if not virtual_fs.create_dir(self._current_path, name):
            self.status_label.setText(f"„{name}“ existiert hier bereits.")
            return
        self._populate_table()

    def _delete_selected(self) -> None:
        name = self._selected_row_name()
        if name is None:
            return
        virtual_fs.delete_entry(self._current_path, name)
        self._populate_table()
