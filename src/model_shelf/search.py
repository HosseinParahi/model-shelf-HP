"""Search Hugging Face Hub for models matching a loose text query.

Lets the agent take a user's natural-language description ("qwen 3 4b mlx
4-bit") and turn it into a concrete `org/repo` id by hitting the Hub's
own search API. Output is sorted by HF's relevance ranking, with download
count surfaced as a sanity check.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from huggingface_hub import HfApi

from model_shelf.resolver import detect_format


@dataclass
class FindResult:
    repo_id: str
    format: str       # "gguf" | "mlx" | "safetensors"
    downloads: int

    def to_dict(self) -> dict:
        return asdict(self)


def find_models(
    query: str,
    *,
    format: str | None = None,
    limit: int = 10,
) -> list[FindResult]:
    """Search the HF Hub. Returns results, optionally filtered to one format."""
    api = HfApi()
    # Over-fetch when format-filtering so we still hit `limit` after filtering.
    fetch_limit = limit * 5 if format else limit
    raw = list(api.list_models(search=query, limit=fetch_limit))

    out: list[FindResult] = []
    for m in raw:
        fmt = detect_format(m.id)
        if format is not None and fmt != format:
            continue
        out.append(
            FindResult(
                repo_id=m.id,
                format=fmt,
                downloads=int(getattr(m, "downloads", 0) or 0),
            )
        )
        if len(out) >= limit:
            break
    return out
