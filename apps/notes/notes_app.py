import json
import uuid
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from apps.base_app import BaseApp
from core.event_bus import event_bus

_NOTES_PATH = Path("data/notes.json")
_AUTOSAVE_INTERVAL_MS = 30_000


def _now_str() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M")  # noqa: DTZ005 - nur Anzeige, lokale Zeit ist hier korrekt


class NotesApp(BaseApp):
    """Notizen-Editor mit mehreren Notizen: Neu / Bearbeiten / Speichern / Löschen.

    Persistiert als JSON-Liste unter data/notes.json — es gibt kein VirtualFS im
    Projekt, darum ist diese App bewusst genauso eigenständig wie Calculator/
    File-Explorer.
    """

    app_id = "notes"
    title = "Notizen"

    def __init__(self):
        super().__init__(app_id="notes", title="Notizen", event_bus=event_bus)
        self.setWindowTitle("Notizen")

        try:
            with open("assets/styles/cyberpunk.qss", "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Style Datei nicht gefunden!")

    def build_ui(self, layout) -> None:
        self.resize(680, 460)
        self.setMinimumSize(520, 380)  # 180px feste Sidebar + Platz für die Editor-Buttons
        self._notes: list[dict] = self._load_all()
        self._current_id: str | None = None
        self._dirty = False

        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_editor_area(), 1)
        layout.addLayout(body)

        self._refresh_list()
        if self._notes:
            self._select_note(self._notes[0]["id"])
        else:
            self._new_note()

        self._save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self._save_shortcut.activated.connect(self._save_current)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start(_AUTOSAVE_INTERVAL_MS)

    # ------------------------------------------------------------------
    # Aufbau
    # ------------------------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("notesSidebar")
        panel.setFixedWidth(180)
        v = QVBoxLayout(panel)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        new_btn = QPushButton("+ Neue Notiz")
        new_btn.setObjectName("notesNewBtn")
        new_btn.clicked.connect(self._new_note)
        v.addWidget(new_btn)

        self.note_list = QListWidget()
        self.note_list.setObjectName("notesList")
        self.note_list.setFrameShape(QListWidget.NoFrame)
        self.note_list.currentItemChanged.connect(self._on_selection_changed)
        v.addWidget(self.note_list)

        return panel

    def _build_editor_area(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("notesEditorArea")
        v = QVBoxLayout(panel)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        status_bar = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setObjectName("notesStatusLabel")
        status_bar.addWidget(self.status_label)
        status_bar.addStretch()

        self.delete_btn = QPushButton("Löschen")
        self.delete_btn.setObjectName("notesDeleteBtn")
        self.delete_btn.clicked.connect(self._delete_current)
        status_bar.addWidget(self.delete_btn)

        self.save_btn = QPushButton("Speichern")
        self.save_btn.setObjectName("notesSaveBtn")
        self.save_btn.clicked.connect(self._save_current)
        status_bar.addWidget(self.save_btn)
        v.addLayout(status_bar)

        self.editor = QPlainTextEdit()
        self.editor.setObjectName("notesEditor")
        self.editor.setPlaceholderText("Schreibe hier deine Notizen...")
        self.editor.textChanged.connect(self._on_text_changed)
        v.addWidget(self.editor)

        return panel

    # ------------------------------------------------------------------
    # Datenhaltung (JSON-Liste, kein VirtualFS)
    # ------------------------------------------------------------------
    def _load_all(self) -> list[dict]:
        try:
            raw = _NOTES_PATH.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            pass
        return []

    def _save_all(self) -> None:
        try:
            _NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
            _NOTES_PATH.write_text(
                json.dumps(self._notes, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass

    def _find_note(self, note_id: str) -> dict | None:
        return next((n for n in self._notes if n["id"] == note_id), None)

    # ------------------------------------------------------------------
    # Liste / Auswahl
    # ------------------------------------------------------------------
    def _refresh_list(self) -> None:
        self.note_list.blockSignals(True)
        self.note_list.clear()
        for note in self._notes:
            item = QListWidgetItem(note["title"] or "Ohne Titel")
            item.setData(Qt.UserRole, note["id"])
            self.note_list.addItem(item)
        self.note_list.blockSignals(False)

    def _select_note(self, note_id: str) -> None:
        for i in range(self.note_list.count()):
            if self.note_list.item(i).data(Qt.UserRole) == note_id:
                self.note_list.setCurrentRow(i)
                return

    def _on_selection_changed(self, current, previous) -> None:
        # Vorherige Notiz still sichern, bevor der Editor auf die neue wechselt.
        if previous is not None and self._current_id is not None:
            self._persist_current_note()

        if current is None:
            self._current_id = None
            self.editor.blockSignals(True)
            self.editor.setPlainText("")
            self.editor.blockSignals(False)
            return

        note_id = current.data(Qt.UserRole)
        if note_id == self._current_id:
            # Gleiche Notiz wurde nur neu selektiert — z.B. weil _save_current()
            # (Button/Strg+S/Autosave) die Liste neu aufgebaut und danach wieder
            # angewählt hat. Editor-Inhalt/Cursor hier NICHT anfassen, sonst
            # springt der Cursor beim Autosave alle 30s mitten im Tippen weg.
            return

        note = self._find_note(note_id)
        if note is None:
            return
        self._current_id = note_id
        self.editor.blockSignals(True)
        self.editor.setPlainText(note["content"])
        self.editor.blockSignals(False)
        self._dirty = False
        self._update_status()

    # ------------------------------------------------------------------
    # Aktionen: Neu / Speichern / Löschen
    # ------------------------------------------------------------------
    def _new_note(self) -> None:
        note = {
            "id": str(uuid.uuid4()),
            "title": "Neue Notiz",
            "content": "",
            "updated": _now_str(),
        }
        self._notes.insert(0, note)
        self._save_all()
        self._refresh_list()
        self._select_note(note["id"])

    def _delete_current(self) -> None:
        if self._current_id is None:
            return
        self._notes = [n for n in self._notes if n["id"] != self._current_id]
        self._current_id = None
        self._save_all()
        self._refresh_list()
        if self._notes:
            self._select_note(self._notes[0]["id"])
        else:
            self.editor.setPlainText("")
            self._update_status()

    def _on_text_changed(self) -> None:
        self._dirty = True
        self._update_status()

    def _update_status(self) -> None:
        chars = len(self.editor.toPlainText())
        state = "Ungespeichert" if self._dirty else "Gespeichert"
        self.status_label.setText(f"{state} · {chars} Zeichen")

    def _persist_current_note(self) -> None:
        """Schreibt den Editor-Inhalt ins Notiz-Objekt und speichert die JSON-Datei —
        rührt die QListWidget-Items NICHT an. Dadurch sicher auch aus einem
        currentItemChanged-Handler heraus aufrufbar (siehe _on_selection_changed):
        ein Listen-Rebuild mitten in dessen eigener Signal-Verarbeitung hätte das
        gerade übergebene QListWidgetItem gelöscht -> Absturz beim Zugriff danach."""
        if self._current_id is None:
            return
        note = self._find_note(self._current_id)
        if note is None:
            return
        text = self.editor.toPlainText()
        note["content"] = text
        first_line = text.strip().splitlines()[0][:40] if text.strip() else "Ohne Titel"
        note["title"] = first_line
        note["updated"] = _now_str()
        self._save_all()
        self._dirty = False

    def _save_current(self) -> None:
        """Für Button/Strg+S/Autosave: speichert UND aktualisiert die Titel-Liste
        sichtbar (sicher, weil hier kein currentItemChanged gerade läuft)."""
        if self._current_id is None:
            return
        self._persist_current_note()
        self._refresh_list()
        self._select_note(self._current_id)
        self._update_status()

    def _autosave(self) -> None:
        if self._dirty:
            self._save_current()

    def on_close(self) -> None:
        """Vom WindowManager beim Schließen aufgerufen — letzte Änderungen sichern."""
        if self._dirty:
            self._persist_current_note()
