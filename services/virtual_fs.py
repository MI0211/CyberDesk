"""Simuliertes, gemeinsames Dateisystem als JSON-Baum (Handbuch, Kapitel 2 + 11).

Jeder Knoten ist entweder ein Ordner ({"type": "dir", "children": {...}}) oder eine
Datei ({"type": "file", "content": str, "size_bytes": int, "modified": "YYYY-MM-DD"}).
Aktuell genutzt vom Datei-Explorer (apps/file_explorer/file_explorer_app.py), der damit
echte Unterordner navigieren kann statt nur eine feste Liste pro Top-Level-Ordner.
"""
from __future__ import annotations

import copy
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_VFS_PATH = Path("data/filesystem.json")

# Anfangszustand beim allerersten Start (danach übernimmt data/filesystem.json).
# Entspricht den bisherigen Demo-Dateien des Datei-Explorers — "Projects" ist jetzt
# aber ein echter, navigierbarer Unterordner statt nur einer Zeile mit type="Folder".
_SEED_TREE: dict[str, Any] = {
    "type": "dir",
    "children": {
        "Desktop": {"type": "dir", "children": {}},
        "Documents": {
            "type": "dir",
            "children": {
                "Projects": {"type": "dir", "children": {}},
                "CyberDesk_v1.pptx": {
                    "type": "file", "content": "", "size_bytes": 4404019, "modified": "2026-07-21",
                },
                "Budget_2026.xlsx": {
                    "type": "file", "content": "", "size_bytes": 1153434, "modified": "2026-07-19",
                },
                "Q2_Report.pdf": {
                    "type": "file", "content": "", "size_bytes": 839680, "modified": "2026-07-15",
                },
                "notes_draft.txt": {
                    "type": "file", "content": "", "size_bytes": 12288, "modified": "2026-07-22",
                },
            },
        },
        "Downloads": {
            "type": "dir",
            "children": {
                "backup_july.zip": {
                    "type": "file", "content": "", "size_bytes": 245366784, "modified": "2026-07-10",
                },
                "install_setup.exe": {
                    "type": "file", "content": "", "size_bytes": 152043520, "modified": "2026-06-28",
                },
            },
        },
        "Pictures": {
            "type": "dir",
            "children": {
                "wallpaper.png": {
                    "type": "file", "content": "", "size_bytes": 3984588, "modified": "2026-07-01",
                },
            },
        },
        "Music": {"type": "dir", "children": {}},
        "Videos": {"type": "dir", "children": {}},
    },
}


def _load_tree() -> dict[str, Any]:
    try:
        raw = _VFS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("type") == "dir":
            return data
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        pass
    return copy.deepcopy(_SEED_TREE)


def _save_tree(tree: dict[str, Any]) -> None:
    try:
        _VFS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _VFS_PATH.write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.exception("Konnte filesystem.json nicht schreiben.")


def _resolve_dir(tree: dict[str, Any], path: list[str]) -> dict[str, Any] | None:
    """Läuft path (Ordnernamen ab Wurzel) im Baum ab, gibt den Verzeichnis-Knoten
    zurück oder None, wenn der Pfad nicht existiert oder kein Ordner ist."""
    node = tree
    for segment in path:
        if node.get("type") != "dir":
            return None
        node = node.get("children", {}).get(segment)
        if node is None:
            return None
    return node if node.get("type") == "dir" else None


def _infer_type(name: str) -> str:
    return name.rsplit(".", 1)[-1].upper() if "." in name else "FILE"


def list_dir(path: list[str]) -> list[dict[str, Any]]:
    """Gibt die Einträge eines Ordners zurück, je mit name/is_dir/type/size_bytes/modified."""
    node = _resolve_dir(_load_tree(), path)
    if node is None:
        return []
    entries = []
    for name, child in node.get("children", {}).items():
        is_dir = child.get("type") == "dir"
        entries.append(
            {
                "name": name,
                "is_dir": is_dir,
                "type": "Folder" if is_dir else _infer_type(name),
                "size_bytes": -1 if is_dir else child.get("size_bytes", 0),
                "modified": child.get("modified", ""),
            }
        )
    return entries


def create_file(path: list[str], name: str) -> bool:
    """Legt eine leere Datei im angegebenen Ordner an. False bei Namenskollision
    oder wenn der Pfad kein gültiger Ordner ist."""
    tree = _load_tree()
    node = _resolve_dir(tree, path)
    if node is None:
        return False
    children = node.setdefault("children", {})
    if name in children:
        return False
    children[name] = {
        "type": "file",
        "content": "",
        "size_bytes": 0,
        "modified": datetime.now().strftime("%Y-%m-%d"),  # noqa: DTZ005 - nur Anzeige
    }
    _save_tree(tree)
    return True


def create_dir(path: list[str], name: str) -> bool:
    """Legt einen neuen, leeren Unterordner an. False bei Namenskollision."""
    tree = _load_tree()
    node = _resolve_dir(tree, path)
    if node is None:
        return False
    children = node.setdefault("children", {})
    if name in children:
        return False
    children[name] = {"type": "dir", "children": {}}
    _save_tree(tree)
    return True


def delete_entry(path: list[str], name: str) -> None:
    """Entfernt eine Datei oder einen Unterordner (inkl. seines gesamten Inhalts)."""
    tree = _load_tree()
    node = _resolve_dir(tree, path)
    if node is None:
        return
    node.get("children", {}).pop(name, None)
    _save_tree(tree)
