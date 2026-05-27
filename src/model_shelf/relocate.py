"""Find the shelf even if its drive was renamed or remounted under a different name.

Convention-based: if your shelf was at `/Volumes/Lexar/ModelShelf/models` and
that path no longer resolves, scan mounted `/Volumes/*` for any drive whose
`ModelShelf/models` directory exists, and use that. First match wins.

No identity tracking, no marker files — Model Shelf trusts the folder
convention. The simplest thing that could possibly work.
"""

from __future__ import annotations

from pathlib import Path


def _extract_volume_subpath(shelf_root: Path) -> tuple[Path, str] | None:
    """If shelf_root is under /Volumes/<name>/<sub...>, return (/Volumes, sub)."""
    parts = shelf_root.parts
    if len(parts) < 4 or parts[0] != "/" or parts[1] != "Volumes":
        return None
    return Path("/Volumes"), "/".join(parts[3:])


def find_shelf_at_subpath(
    subpath: str,
    volumes_dir: Path | None = None,
) -> Path | None:
    """Return the first mounted /Volumes/* drive that has `<vol>/<subpath>` as a directory."""
    if volumes_dir is None:
        volumes_dir = Path("/Volumes")
    if not volumes_dir.is_dir():
        return None
    for vol in sorted(volumes_dir.iterdir(), key=lambda p: p.name.lower()):
        if vol.is_symlink() or not vol.is_dir():
            continue
        candidate = vol / subpath
        if candidate.is_dir():
            return candidate
    return None


def relocate_shelf(shelf_root: Path) -> Path:
    """Return the effective shelf_root, possibly relocated to a renamed/swapped drive.

    - If shelf_root exists, return it.
    - If shelf_root is under /Volumes/ and some other mounted drive has the same
      subpath, return that drive's path.
    - Otherwise return shelf_root unchanged (downstream code will surface the
      appropriate "not mounted" / "not initialized" error).
    """
    if shelf_root.is_dir():
        return shelf_root
    extracted = _extract_volume_subpath(shelf_root)
    if extracted is None:
        return shelf_root
    volumes_dir, subpath = extracted
    found = find_shelf_at_subpath(subpath, volumes_dir=volumes_dir)
    return found if found is not None else shelf_root
