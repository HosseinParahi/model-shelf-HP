"""Tests for convention-based relocation (v0.10).

If the configured shelf_root doesn't resolve (drive renamed or unplugged),
scan /Volumes/* for any drive with the same subpath. First match wins.
No marker file, no identity tracking.
"""

from pathlib import Path

from model_shelf.relocate import (
    find_shelf_at_subpath,
    relocate_shelf,
)


def _make_drive(volumes_dir: Path, name: str, subpath: str = "ModelShelf/models") -> Path:
    drive = volumes_dir / name / subpath
    drive.mkdir(parents=True)
    return drive


def test_relocate_returns_path_when_it_exists(tmp_path: Path):
    existing = tmp_path / "shelf"
    existing.mkdir()
    assert relocate_shelf(existing) == existing


def test_relocate_returns_original_when_not_under_volumes(tmp_path: Path):
    nonexistent = tmp_path / "nope"
    assert relocate_shelf(nonexistent) == nonexistent


def test_find_shelf_at_subpath_matches_drive_with_folder(tmp_path: Path):
    volumes = tmp_path / "Volumes"
    volumes.mkdir()
    real = _make_drive(volumes, "RenamedDrive")

    found = find_shelf_at_subpath("ModelShelf/models", volumes_dir=volumes)
    assert found == real


def test_find_shelf_at_subpath_returns_none_when_no_match(tmp_path: Path):
    volumes = tmp_path / "Volumes"
    volumes.mkdir()
    # Drive exists but has no ModelShelf/models folder.
    (volumes / "EmptyDrive").mkdir()

    found = find_shelf_at_subpath("ModelShelf/models", volumes_dir=volumes)
    assert found is None


def test_find_shelf_at_subpath_skips_symlinks(tmp_path: Path):
    volumes = tmp_path / "Volumes"
    volumes.mkdir()
    (tmp_path / "real-root").mkdir()
    (volumes / "Macintosh HD").symlink_to(tmp_path / "real-root")
    real = _make_drive(volumes, "Lexar")

    found = find_shelf_at_subpath("ModelShelf/models", volumes_dir=volumes)
    assert found == real


def test_find_shelf_at_subpath_picks_first_alphabetically_when_multiple(tmp_path: Path):
    """If two drives both have a ModelShelf folder, pick the first one
    alphabetically. Deterministic, user can override with --config."""
    volumes = tmp_path / "Volumes"
    volumes.mkdir()
    _make_drive(volumes, "B-Drive")
    _make_drive(volumes, "A-Drive")

    found = find_shelf_at_subpath("ModelShelf/models", volumes_dir=volumes)
    assert found == volumes / "A-Drive" / "ModelShelf" / "models"


def test_relocate_handles_renamed_drive(tmp_path: Path, monkeypatch):
    """Configured path /Volumes/Old/ModelShelf/models doesn't exist; drive
    is actually mounted at /Volumes/New/. Relocate must find it."""
    volumes = tmp_path / "Volumes"
    volumes.mkdir()
    new = _make_drive(volumes, "NewName")

    # Patch the volumes_dir used by find_shelf_at_subpath inside relocate_shelf.
    import model_shelf.relocate as relocate_mod
    original_find = relocate_mod.find_shelf_at_subpath
    monkeypatch.setattr(
        relocate_mod,
        "find_shelf_at_subpath",
        lambda subpath, volumes_dir=None: original_find(subpath, volumes_dir=volumes),
    )

    configured = Path("/Volumes/OldName/ModelShelf/models")
    located = relocate_shelf(configured)
    assert located == new


def test_relocate_returns_configured_path_when_no_match(tmp_path: Path, monkeypatch):
    """When no mounted drive has the conventional subpath, return the
    configured path unchanged so downstream code can surface the right error."""
    empty_volumes = tmp_path / "Volumes"
    empty_volumes.mkdir()
    import model_shelf.relocate as relocate_mod
    original_find = relocate_mod.find_shelf_at_subpath
    monkeypatch.setattr(
        relocate_mod,
        "find_shelf_at_subpath",
        lambda subpath, volumes_dir=None: original_find(subpath, volumes_dir=empty_volumes),
    )

    configured = Path("/Volumes/Nonexistent_xyz_123/ModelShelf/models")
    assert relocate_shelf(configured) == configured
