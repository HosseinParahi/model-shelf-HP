from pathlib import Path

import pytest

from model_shelf.resolver import (
    Config,
    ShelfNotInitializedError,
    StorageNotAvailableError,
    check_storage_available,
    detect_format,
    hf_filename,
    init_shelf,
    list_shelf_candidates,
    resolve_model,
    shelf_dirname,
    shelf_filename,
)


# --- filename / dirname helpers --------------------------------------------

def test_shelf_filename_qwen():
    assert shelf_filename("Qwen/Qwen3-14B-GGUF", "Q4_K_M") == "qwen3-14b-q4_k_m.gguf"


def test_shelf_filename_llama():
    assert (
        shelf_filename("meta-llama/Llama-3.1-8B-Instruct", "Q5_K_M")
        == "llama-3.1-8b-instruct-q5_k_m.gguf"
    )


def test_hf_filename_preserves_case():
    assert hf_filename("Qwen/Qwen3-14B-GGUF", "Q4_K_M") == "Qwen3-14B-Q4_K_M.gguf"


def test_filenames_dont_double_append_quant_when_already_in_name():
    """Repos like `rippertnt/Qwen3-0.6B-Q4_K_M-GGUF` already carry the quant
    in the name; appending it again produces a nonexistent file on HF."""
    assert (
        hf_filename("rippertnt/Qwen3-0.6B-Q4_K_M-GGUF", "Q4_K_M")
        == "Qwen3-0.6B-Q4_K_M.gguf"
    )
    assert (
        shelf_filename("rippertnt/Qwen3-0.6B-Q4_K_M-GGUF", "Q4_K_M")
        == "qwen3-0.6b-q4_k_m.gguf"
    )


def test_shelf_dirname_mlx_community():
    assert shelf_dirname("mlx-community/Qwen3-14B-4bit") == "qwen3-14b-4bit"


def test_shelf_dirname_strips_trailing_mlx():
    assert shelf_dirname("mlx-community/Qwen3-14B-4bit-mlx") == "qwen3-14b-4bit"


def test_shelf_dirname_safetensors():
    assert shelf_dirname("Qwen/Qwen3-14B") == "qwen3-14b"


# --- format detection -------------------------------------------------------

def test_detect_format_gguf():
    assert detect_format("Qwen/Qwen3-14B-GGUF") == "gguf"
    assert detect_format("bartowski/Qwen_Qwen3-14B-gguf") == "gguf"


def test_detect_format_mlx():
    assert detect_format("mlx-community/Qwen3-14B-4bit") == "mlx"
    assert detect_format("Qwen/Qwen3-14B-MLX") == "mlx"
    # MLX token appears mid-name, not as a suffix.
    assert detect_format("Qwen/Qwen3-4B-MLX-4bit") == "mlx"
    assert detect_format("lmstudio-community/Qwen3-4B-MLX-4bit") == "mlx"


def test_detect_format_safetensors_default():
    assert detect_format("Qwen/Qwen3-14B") == "safetensors"
    assert detect_format("meta-llama/Llama-3.1-8B-Instruct") == "safetensors"


# --- resolver: gguf path ----------------------------------------------------

def _config(tmp_path: Path, *, allow_downloads: bool = False) -> Config:
    shelf = tmp_path / "shelf"
    shelf.mkdir(parents=True, exist_ok=True)
    return Config(shelf_root=shelf, allow_downloads=allow_downloads)


def test_gguf_shelf_hit(tmp_path: Path):
    cfg = _config(tmp_path)
    gguf = cfg.shelf_root / "gguf"
    gguf.mkdir(parents=True)
    (gguf / "qwen3-14b-q4_k_m.gguf").write_bytes(b"x")

    result = resolve_model(cfg, "Qwen/Qwen3-14B-GGUF", quant="Q4_K_M")

    assert result.status == "found"
    assert result.source == "local_shelf"
    assert result.format == "gguf"
    assert result.path == gguf / "qwen3-14b-q4_k_m.gguf"
    assert result.checks == [
        {"location": "shelf", "root": str(gguf), "result": "hit"},
    ]


def test_gguf_missing_when_downloads_disabled(tmp_path: Path):
    cfg = _config(tmp_path)
    result = resolve_model(cfg, "Qwen/Qwen3-14B-GGUF", quant="Q4_K_M")

    assert result.status == "missing"
    assert result.format == "gguf"
    # Multi-shelf lookup may check several shelves; all should miss.
    assert result.checks  # at least one check happened
    assert all(c["result"] == "miss" for c in result.checks)


def test_gguf_requires_quant(tmp_path: Path):
    cfg = _config(tmp_path)
    with pytest.raises(ValueError, match="quant"):
        resolve_model(cfg, "Qwen/Qwen3-14B-GGUF")


# --- resolver: mlx path -----------------------------------------------------

def test_mlx_shelf_hit_requires_config_json(tmp_path: Path):
    cfg = _config(tmp_path)
    mlx = cfg.shelf_root / "mlx" / "qwen3-14b-4bit"
    mlx.mkdir(parents=True)
    (mlx / "config.json").write_text("{}")

    result = resolve_model(cfg, "mlx-community/Qwen3-14B-4bit")

    assert result.status == "found"
    assert result.source == "local_shelf"
    assert result.format == "mlx"
    assert result.path == mlx


def test_mlx_empty_dir_does_not_count(tmp_path: Path):
    cfg = _config(tmp_path)
    mlx = cfg.shelf_root / "mlx" / "qwen3-14b-4bit"
    mlx.mkdir(parents=True)
    # No config.json on purpose.

    result = resolve_model(cfg, "mlx-community/Qwen3-14B-4bit")

    assert result.status == "missing"


# --- resolver: safetensors path --------------------------------------------

def test_safetensors_shelf_hit(tmp_path: Path):
    cfg = _config(tmp_path)
    st = cfg.shelf_root / "safetensors" / "qwen3-14b"
    st.mkdir(parents=True)
    (st / "config.json").write_text("{}")

    result = resolve_model(cfg, "Qwen/Qwen3-14B")

    assert result.status == "found"
    assert result.format == "safetensors"
    assert result.path == st


# --- explicit --format override --------------------------------------------

def test_format_override(tmp_path: Path):
    cfg = _config(tmp_path)
    # User asks for safetensors of a repo we'd otherwise detect as gguf.
    st = cfg.shelf_root / "safetensors" / "qwen3-14b-gguf"
    st.mkdir(parents=True)
    (st / "config.json").write_text("{}")

    result = resolve_model(cfg, "Qwen/Qwen3-14B-GGUF", format="safetensors")

    assert result.status == "found"
    assert result.format == "safetensors"


# --- storage availability precheck -----------------------------------------

NONEXISTENT_VOLUME = Path("/Volumes/__model_shelf_test_xyz_does_not_exist__")


def test_storage_check_passes_for_initialized_shelf(tmp_path: Path):
    check_storage_available(Config(shelf_root=tmp_path))


def test_storage_check_errors_for_uninitialized_shelf(tmp_path: Path):
    cfg = Config(shelf_root=tmp_path / "nope")
    with pytest.raises(ShelfNotInitializedError, match="doesn't exist"):
        check_storage_available(cfg)


def test_storage_check_errors_for_unmounted_volume():
    cfg = Config(shelf_root=NONEXISTENT_VOLUME / "models")
    with pytest.raises(StorageNotAvailableError, match="not mounted"):
        check_storage_available(cfg)


def test_volume_check_runs_before_shelf_check():
    """When both fail, the more specific unmounted-volume error should win."""
    cfg = Config(shelf_root=NONEXISTENT_VOLUME / "models")
    with pytest.raises(StorageNotAvailableError) as exc:
        check_storage_available(cfg)
    assert "not mounted" in str(exc.value)


def test_resolve_model_errors_when_volume_unmounted():
    cfg = Config(shelf_root=NONEXISTENT_VOLUME / "models", allow_downloads=False)
    with pytest.raises(StorageNotAvailableError):
        resolve_model(cfg, "Qwen/Qwen3-14B-GGUF", quant="Q4_K_M")


# --- multi-shelf lookup ---------------------------------------------------


def _patch_candidates(monkeypatch, paths: list):
    """Replace list_shelf_candidates with a fixed return so tests don't see the real /Volumes."""
    import model_shelf.resolver as resolver_mod
    monkeypatch.setattr(
        resolver_mod,
        "list_shelf_candidates",
        lambda cfg: list(paths),
    )


def test_gguf_lookup_hits_additional_shelf(tmp_path: Path, monkeypatch):
    primary = tmp_path / "primary"
    extra = tmp_path / "extra"
    primary.mkdir()
    (extra / "gguf").mkdir(parents=True)
    (extra / "gguf" / "qwen3-14b-q4_k_m.gguf").write_bytes(b"x")
    _patch_candidates(monkeypatch, [primary, extra])

    cfg = Config(shelf_root=primary, allow_downloads=False)
    result = resolve_model(cfg, "Qwen/Qwen3-14B-GGUF", quant="Q4_K_M")

    assert result.status == "found"
    assert result.source == "local_shelf"
    assert result.path == extra / "gguf" / "qwen3-14b-q4_k_m.gguf"
    # Both shelves were checked, primary missed, additional hit.
    assert [c["result"] for c in result.checks] == ["miss", "hit"]


def test_gguf_lookup_prefers_primary_when_both_have_file(tmp_path: Path, monkeypatch):
    primary = tmp_path / "primary"
    extra = tmp_path / "extra"
    for parent in (primary, extra):
        (parent / "gguf").mkdir(parents=True)
        (parent / "gguf" / "qwen3-14b-q4_k_m.gguf").write_bytes(b"x")
    _patch_candidates(monkeypatch, [primary, extra])

    cfg = Config(shelf_root=primary, allow_downloads=False)
    result = resolve_model(cfg, "Qwen/Qwen3-14B-GGUF", quant="Q4_K_M")

    assert result.path == primary / "gguf" / "qwen3-14b-q4_k_m.gguf"
    # Lookup stopped at the primary; extra not checked.
    assert len(result.checks) == 1


def test_mlx_lookup_hits_additional_shelf(tmp_path: Path, monkeypatch):
    primary = tmp_path / "primary"
    extra = tmp_path / "extra"
    primary.mkdir()
    model_dir = extra / "mlx" / "qwen3-14b-4bit"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}")
    _patch_candidates(monkeypatch, [primary, extra])

    cfg = Config(shelf_root=primary, allow_downloads=False)
    result = resolve_model(cfg, "mlx-community/Qwen3-14B-4bit")

    assert result.status == "found"
    assert result.path == model_dir


# --- init_shelf -----------------------------------------------------------

def test_init_shelf_creates_subfolders(tmp_path: Path):
    cfg = Config(shelf_root=tmp_path / "newshelf")
    created = init_shelf(cfg)
    assert len(created) == 4  # shelf_root + 3 format subdirs
    assert (cfg.shelf_root / "gguf").is_dir()
    assert (cfg.shelf_root / "mlx").is_dir()
    assert (cfg.shelf_root / "safetensors").is_dir()


def test_init_shelf_is_idempotent(tmp_path: Path):
    cfg = Config(shelf_root=tmp_path / "newshelf")
    init_shelf(cfg)
    assert init_shelf(cfg) == []


def test_init_shelf_errors_on_unmounted_volume():
    cfg = Config(shelf_root=NONEXISTENT_VOLUME / "models")
    with pytest.raises(StorageNotAvailableError):
        init_shelf(cfg)


# --- backwards compat: old config with hf_cache_root still loads -----------

def test_load_config_ignores_legacy_hf_cache_root(tmp_path: Path):
    """An old config with hf_cache_root must still load without raising."""
    from model_shelf.config import load_config
    cfg_file = tmp_path / "old.toml"
    cfg_file.write_text(
        'shelf_root      = "/tmp/old/shelf"\n'
        'hf_cache_root   = "/tmp/old/hf-cache"\n'
        "allow_downloads = false\n"
    )
    cfg = load_config(cfg_file)
    assert str(cfg.shelf_root) == "/tmp/old/shelf"
    assert cfg.allow_downloads is False
    assert not hasattr(cfg, "hf_cache_root")
