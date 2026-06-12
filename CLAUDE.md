# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Model Shelf is a local-first resolver for Hugging Face models (GGUF, MLX, safetensors). It is three things in one repo:

1. A Python package (`src/model_shelf/`) exposing the `model-shelf` CLI.
2. A Claude Code **plugin** (`.claude-plugin/plugin.json` + `skills/resolve/SKILL.md` + `hooks/hooks.json`) installed via `/plugin install model-shelf@alexziskind1/model-shelf`. The hook auto-installs the CLI via `uv` on session start; the skill instructs agents to always resolve models through `model-shelf` instead of downloading directly.
3. A Python library (`from model_shelf import resolve_model, ...` — public API re-exported in `__init__.py`).

## Commands

```bash
# Run all tests (no dev-deps file; pull test deps ad hoc with uv)
uv run --with pytest --with huggingface_hub --with questionary pytest tests/ -q

# Run a single test file / test
uv run --with pytest --with huggingface_hub --with questionary pytest tests/test_resolver.py -q
uv run --with pytest --with huggingface_hub --with questionary pytest tests/test_resolver.py::test_name -q

# Install locally for manual CLI testing
uv tool install --force .
```

There is no linter or formatter configured.

## Architecture

Resolution flow (`resolve_model` in [resolver.py](src/model_shelf/resolver.py)):

1. `load_config()` ([config.py](src/model_shelf/config.py)) reads TOML from explicit path → `$MODEL_SHELF_CONFIG` → `~/.config/model-shelf/config.toml` (bootstraps a default if missing). A cwd `./config.toml` is deliberately **not** read.
2. If `shelf_root` is unpinned (the default), `discover_primary_shelf()` picks the first mounted `/Volumes/*/ModelShelf/models` (alphabetical), else `~/.cache/model-shelf/models`. If pinned but missing, `relocate_shelf()` ([relocate.py](src/model_shelf/relocate.py)) scans other mounted volumes for the same subpath (handles drive renames/swaps) — convention-based, no marker files.
3. `list_shelf_candidates()` returns every visible shelf: primary first, then every mounted drive with a `ModelShelf/models` folder, then the internal default. **First hit wins on resolve; downloads always land in the primary.**
4. Format is detected from the repo id by token matching (`detect_format`): `gguf` token → gguf (requires `--quant`), `mlx-community/*` org or `mlx` token → mlx, else safetensors. GGUF resolves to a single file; mlx/safetensors resolve to a directory, where a hit requires the dir to contain a `config.json`.
5. Downloads use `huggingface_hub` with `local_dir` pointed inside the shelf, so files land directly at `shelf_root/<format>/<publisher>/<repo>/...` — the layout mirrors HF Hub and matches LM Studio's expectations. There is no parallel HF cache.

Other modules: [cli.py](src/model_shelf/cli.py) (argparse subcommands `resolve`/`find`/`list`/`init`, exit codes: 0 found/downloaded, 1 missing, 2 storage/usage error, 3 HF/API error), [detect.py](src/model_shelf/detect.py) (ranked storage candidates for interactive `init`), [search.py](src/model_shelf/search.py) (`find` = HF Hub search with format filtering).

## Conventions

- macOS-centric: external drive discovery hardcodes `/Volumes/`; symlinked volume entries (Macintosh HD) are skipped. Tests pass `volumes_dir`/`home` overrides instead of touching the real filesystem.
- Errors: `StorageNotAvailableError` (volume unmounted) and its subclass `ShelfNotInitializedError` carry user-facing messages printed verbatim by the CLI. Refuse to write to an unmounted `/Volumes/<name>/` path rather than silently falling back to internal storage.
- Tests are pure pytest with `tmp_path`/monkeypatch; network calls (`hf_hub_download`, `snapshot_download`, `HfApi`) are stubbed, never hit.
- Version lives in three places — keep them in sync when bumping: `pyproject.toml`, `src/model_shelf/__init__.py` (`__version__`), and `.claude-plugin/plugin.json`.
- `model-shelf list` filters dot-prefixed dirs (e.g. the `.cache/huggingface/` metadata folder HF writes inside the shelf) and `._*` AppleDouble files.
- The bundled skill ([skills/resolve/SKILL.md](skills/resolve/SKILL.md)) is the agent-facing contract: agents must never fall back to `huggingface-cli`/`hf download` and must surface `model-shelf` errors verbatim. Keep it consistent with CLI behavior when changing flags or output.
