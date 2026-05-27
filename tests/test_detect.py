from pathlib import Path

from model_shelf.detect import detect_storage_candidates


def _make_external_drive(volumes_dir: Path, name: str, with_shelf: bool = False) -> Path:
    drive = volumes_dir / name
    drive.mkdir(parents=True)
    if with_shelf:
        (drive / "ModelShelf" / "models").mkdir(parents=True)
    return drive


def test_detects_external_drive_without_shelf(tmp_path: Path):
    volumes = tmp_path / "Volumes"
    home = tmp_path / "home"
    home.mkdir()
    _make_external_drive(volumes, "Lexar")

    candidates = detect_storage_candidates(volumes_dir=volumes, home=home)

    paths = [c.path for c in candidates]
    assert volumes / "Lexar" / "ModelShelf" / "models" in paths
    lexar = next(c for c in candidates if c.label == "Lexar")
    assert lexar.existing is False
    assert lexar.is_external is True


def test_detects_existing_shelf_on_external_drive(tmp_path: Path):
    volumes = tmp_path / "Volumes"
    home = tmp_path / "home"
    home.mkdir()
    _make_external_drive(volumes, "Lexar", with_shelf=True)

    candidates = detect_storage_candidates(volumes_dir=volumes, home=home)

    lexar = next(c for c in candidates if c.label == "Lexar")
    assert lexar.existing is True


def test_internal_default_always_present(tmp_path: Path):
    volumes = tmp_path / "Volumes"
    home = tmp_path / "home"
    home.mkdir()

    candidates = detect_storage_candidates(volumes_dir=volumes, home=home)

    internal = next(c for c in candidates if not c.is_external)
    assert internal.path == home / ".cache" / "model-shelf" / "models"
    assert internal.label == "internal"


def test_skips_symlinks(tmp_path: Path):
    volumes = tmp_path / "Volumes"
    volumes.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    # Macintosh HD symlink simulation
    (tmp_path / "real-root").mkdir()
    (volumes / "Macintosh HD").symlink_to(tmp_path / "real-root")
    _make_external_drive(volumes, "Lexar")

    candidates = detect_storage_candidates(volumes_dir=volumes, home=home)

    labels = [c.label for c in candidates]
    assert "Macintosh HD" not in labels
    assert "Lexar" in labels


def test_existing_shelves_ranked_first(tmp_path: Path):
    volumes = tmp_path / "Volumes"
    home = tmp_path / "home"
    home.mkdir()
    _make_external_drive(volumes, "AAA_New")
    _make_external_drive(volumes, "ZZZ_Existing", with_shelf=True)

    candidates = detect_storage_candidates(volumes_dir=volumes, home=home)

    # Existing should come before new, even though alphabetical would put AAA first.
    assert candidates[0].label == "ZZZ_Existing"


def test_handles_missing_volumes_dir(tmp_path: Path):
    volumes = tmp_path / "Volumes"  # never created
    home = tmp_path / "home"
    home.mkdir()

    candidates = detect_storage_candidates(volumes_dir=volumes, home=home)

    # Should still get the internal default.
    assert len(candidates) == 1
    assert not candidates[0].is_external
