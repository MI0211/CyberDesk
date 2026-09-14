from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path("data/settings.json")
_WALLPAPERS_DIR = Path("assets/wallpapers")
_CUSTOM_WALLPAPERS_DIR = Path("data/wallpapers")

_DEFAULTS: dict[str, Any] = {
    "pinned_apps": [],
    "user_name": "Benutzer",
    "user_avatar": None,
    "wallpaper": None,
}


def _load_raw() -> dict[str, Any]:
    """Liest die settings.json ein. Liefert bei Fehlern/leerer Datei die Standardwerte."""
    try:
        text = _SETTINGS_PATH.read_text(encoding="utf-8").strip()
        if not text:
            return dict(_DEFAULTS)
        data = json.loads(text)
        if not isinstance(data, dict):
            return dict(_DEFAULTS)
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
    except FileNotFoundError:
        return dict(_DEFAULTS)
    except json.JSONDecodeError:
        logger.warning("settings.json ist beschädigt, verwende Standardwerte.")
        return dict(_DEFAULTS)


def _save_raw(data: dict[str, Any]) -> None:
    try:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        logger.exception("Konnte settings.json nicht schreiben.")


def get_pinned_apps() -> list[str]:
    """Gibt die Liste der an die Taskbar angehefteten App-IDs zurück."""
    return list(_load_raw().get("pinned_apps", []))


def set_pinned_apps(app_ids: list[str]) -> None:
    """Speichert die komplette Liste der angehefteten App-IDs."""
    data = _load_raw()
    data["pinned_apps"] = list(dict.fromkeys(app_ids))  # Duplikate raus, Reihenfolge bleibt
    _save_raw(data)


def pin_app(app_id: str) -> None:
    """Heftet eine einzelne App an die Taskbar an."""
    pinned = get_pinned_apps()
    if app_id not in pinned:
        pinned.append(app_id)
        set_pinned_apps(pinned)


def unpin_app(app_id: str) -> None:
    """Löst eine einzelne App von der Taskbar."""
    pinned = get_pinned_apps()
    if app_id in pinned:
        pinned.remove(app_id)
        set_pinned_apps(pinned)


def get_user_name() -> str:
    """Gibt den gespeicherten Anzeigenamen zurück (Default: 'Benutzer')."""
    return str(_load_raw().get("user_name") or "Benutzer")


def set_user_name(name: str) -> None:
    data = _load_raw()
    data["user_name"] = name
    _save_raw(data)


def get_user_avatar() -> str | None:
    """Pfad zum gespeicherten Profilbild, oder None wenn keins gesetzt ist."""
    return _load_raw().get("user_avatar")


def set_user_avatar(path: str) -> None:
    data = _load_raw()
    data["user_avatar"] = path
    _save_raw(data)


def get_wallpaper() -> str | None:
    """Pfad zum gewählten Desktop-Hintergrundbild, oder None (Standardverlauf)."""
    return _load_raw().get("wallpaper")


def set_wallpaper(path: str) -> None:
    data = _load_raw()
    data["wallpaper"] = path
    _save_raw(data)


def list_wallpapers() -> list[Path]:
    """Findet alle Bilder in assets/wallpapers/ (mitgelieferte Presets) und
    data/wallpapers/ (vom Nutzer über 'Durchsuchen...' hinzugefügte), sortiert
    nach Dateiname."""
    found: list[Path] = []
    for directory in (_WALLPAPERS_DIR, _CUSTOM_WALLPAPERS_DIR):
        if directory.exists():
            found.extend(
                p for p in directory.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")
            )
    return sorted(found, key=lambda p: p.name)


def add_custom_wallpaper(source_path: str) -> Path:
    """Kopiert ein über einen echten Dateidialog gewähltes Bild nach data/wallpapers/,
    damit es unabhängig vom Ursprungsort dauerhaft als Hintergrund-Option zur Verfügung
    steht (gleiches Prinzip wie beim Kopieren des Profilbilds nach data/avatar/).

    Wird dieselbe Quelldatei erneut ausgewählt (z.B. beim wiederholten Durchsuchen),
    wird die bereits kopierte Datei wiederverwendet statt ein Duplikat anzulegen —
    Vergleich über Dateigröße + Inhalt, nicht nur über den Dateinamen."""
    _CUSTOM_WALLPAPERS_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(source_path)
    src_bytes = src.read_bytes()

    dest = _CUSTOM_WALLPAPERS_DIR / src.name
    counter = 1
    while dest.exists() and dest.resolve() != src.resolve():
        if dest.stat().st_size == len(src_bytes) and dest.read_bytes() == src_bytes:
            return dest  # bereits importiert, keine Kopie nötig
        dest = _CUSTOM_WALLPAPERS_DIR / f"{src.stem}_{counter}{src.suffix}"
        counter += 1
    if dest.resolve() != src.resolve():
        dest.write_bytes(src_bytes)
    return dest
