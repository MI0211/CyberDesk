"""tests/test_virtual_fs.py — Pfade auflösen, Dateien/Ordner anlegen und löschen,
ganz ohne Qt (reine Baum-Logik). _VFS_PATH wird pro Test auf eine temporäre Datei
umgebogen, damit nichts die echte data/filesystem.json berührt."""
from pathlib import Path

import pytest

from services import virtual_fs


@pytest.fixture(autouse=True)
def _isolated_vfs(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(virtual_fs, "_VFS_PATH", tmp_path / "filesystem.json")


def _names(path: list[str]) -> set[str]:
    return {entry["name"] for entry in virtual_fs.list_dir(path)}


def test_seed_tree_has_expected_top_level_locations() -> None:
    assert _names([]) == {"Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"}


def test_seed_documents_contains_a_real_navigable_projects_folder() -> None:
    documents = virtual_fs.list_dir(["Documents"])
    projects = next(e for e in documents if e["name"] == "Projects")
    assert projects["is_dir"] is True
    assert virtual_fs.list_dir(["Documents", "Projects"]) == []


def test_create_file_appears_in_list_dir() -> None:
    assert virtual_fs.create_file(["Desktop"], "todo.txt") is True
    entries = virtual_fs.list_dir(["Desktop"])
    assert any(e["name"] == "todo.txt" and not e["is_dir"] for e in entries)


def test_create_file_rejects_name_collision() -> None:
    assert virtual_fs.create_file(["Desktop"], "todo.txt") is True
    assert virtual_fs.create_file(["Desktop"], "todo.txt") is False


def test_create_dir_is_navigable_and_starts_empty() -> None:
    assert virtual_fs.create_dir(["Documents", "Projects"], "CyberDesk") is True
    assert _names(["Documents", "Projects"]) == {"CyberDesk"}
    assert virtual_fs.list_dir(["Documents", "Projects", "CyberDesk"]) == []


def test_create_file_inside_new_subfolder() -> None:
    virtual_fs.create_dir(["Documents", "Projects"], "CyberDesk")
    assert virtual_fs.create_file(["Documents", "Projects", "CyberDesk"], "plan.txt") is True
    assert _names(["Documents", "Projects", "CyberDesk"]) == {"plan.txt"}


def test_delete_entry_removes_file() -> None:
    virtual_fs.create_file(["Desktop"], "todo.txt")
    virtual_fs.delete_entry(["Desktop"], "todo.txt")
    assert _names(["Desktop"]) == set()


def test_delete_entry_on_unknown_name_does_not_raise() -> None:
    virtual_fs.delete_entry(["Desktop"], "does-not-exist.txt")  # darf nicht crashen


def test_list_dir_on_invalid_path_returns_empty() -> None:
    assert virtual_fs.list_dir(["Nonexistent"]) == []
    assert virtual_fs.list_dir(["Desktop", "also-nonexistent"]) == []


def test_changes_persist_across_reloads() -> None:
    virtual_fs.create_file(["Pictures"], "urlaub.png")
    # simuliert einen Neustart: nichts hält den Baum mehr im Speicher, jeder
    # Aufruf liest data/filesystem.json frisch von der (hier temporären) Platte.
    assert "urlaub.png" in _names(["Pictures"])
    assert Path(virtual_fs._VFS_PATH).exists()
