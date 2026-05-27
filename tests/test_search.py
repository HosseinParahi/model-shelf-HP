"""Tests for find_models. HfApi.list_models is mocked — we don't hit the network."""

from dataclasses import dataclass
from unittest.mock import patch

from model_shelf.search import find_models


@dataclass
class _FakeModelInfo:
    id: str
    downloads: int = 0


def _patch_list_models(returns):
    """Patch HfApi.list_models to return the given list."""
    return patch(
        "model_shelf.search.HfApi.list_models",
        return_value=iter(returns),
    )


def test_find_returns_repo_format_and_downloads():
    fakes = [
        _FakeModelInfo("Qwen/Qwen3-14B-GGUF", downloads=8400),
        _FakeModelInfo("mlx-community/Qwen3-14B-4bit", downloads=9200),
        _FakeModelInfo("Qwen/Qwen3-14B", downloads=1_200_000),
    ]
    with _patch_list_models(fakes):
        results = find_models("qwen3", limit=10)

    assert [r.repo_id for r in results] == [
        "Qwen/Qwen3-14B-GGUF",
        "mlx-community/Qwen3-14B-4bit",
        "Qwen/Qwen3-14B",
    ]
    assert [r.format for r in results] == ["gguf", "mlx", "safetensors"]
    assert [r.downloads for r in results] == [8400, 9200, 1_200_000]


def test_find_filters_by_format():
    fakes = [
        _FakeModelInfo("Qwen/Qwen3-14B-GGUF", downloads=8400),
        _FakeModelInfo("mlx-community/Qwen3-14B-4bit", downloads=9200),
        _FakeModelInfo("mlx-community/Qwen3-14B-8bit", downloads=2100),
        _FakeModelInfo("Qwen/Qwen3-14B", downloads=1_200_000),
    ]
    with _patch_list_models(fakes):
        results = find_models("qwen3", format="mlx", limit=10)

    assert [r.repo_id for r in results] == [
        "mlx-community/Qwen3-14B-4bit",
        "mlx-community/Qwen3-14B-8bit",
    ]
    assert all(r.format == "mlx" for r in results)


def test_find_respects_limit():
    fakes = [_FakeModelInfo(f"org/m{i}", downloads=i) for i in range(20)]
    with _patch_list_models(fakes):
        results = find_models("anything", limit=3)
    assert len(results) == 3


def test_find_empty_result():
    with _patch_list_models([]):
        results = find_models("nothing matches", limit=10)
    assert results == []


def test_find_handles_missing_downloads():
    fakes = [_FakeModelInfo("org/m1", downloads=None)]  # type: ignore[arg-type]
    with _patch_list_models(fakes):
        results = find_models("query")
    assert results[0].downloads == 0
