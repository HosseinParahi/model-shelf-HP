---
name: resolve
description: Always resolve Hugging Face models via `model-shelf` before any download. Supports GGUF, MLX, and safetensors. Triggers whenever the user asks to load, run, or use a local LLM model (llama.cpp / Ollama / MLX / vLLM / transformers flows).
---

# Resolve a Hugging Face model locally

When the user wants to load, run, or use a Hugging Face model — **always**
go through `model-shelf`. Do not invoke `huggingface-cli download`, `hf
download`, `snapshot_download`, or any other direct download command.

The user does **not** need to give you an exact `org/repo` id. Loose
descriptions ("qwen 3 4b mlx 4-bit", "the latest llama 3.1") are normal
and expected. Do not push back on whether a model exists — your training
data is stale and Model Shelf can search the live Hub.

## Workflow

1. **Decide whether to search first.**
   - If the user gave a clean `org/repo` string (e.g. `Qwen/Qwen3-14B-GGUF`),
     skip to step 2.
   - Otherwise the input is loose — run:
     ```
     model-shelf find "<user's words>" [--format gguf|mlx|safetensors] --json --limit 5
     ```
     Use any format hint from the user (`mlx`, `gguf`, `safetensors`). Pick the
     top result that matches the user's format/quant intent. Use its `repo_id`
     as the input to step 2. If `find` returns nothing, tell the user no
     matching model was found — do **not** invent a repo id.

2. **Resolve the repo to a local path.**
   ```
   model-shelf resolve <repo_id> [--format gguf|mlx|safetensors] [--quant <QUANT>] --json
   ```

   - `--format` is auto-detected from `repo_id` if omitted:
     - `*-GGUF` (case-insensitive) → `gguf`
     - `mlx-community/*` or `*-mlx` → `mlx`
     - everything else → `safetensors`
   - `--quant` is **required for `gguf`** (e.g. `Q4_K_M`); ignored otherwise.

3. **Use the returned `path`** with the user's runtime:
   - **gguf**: file path → `llama.cpp` / `llama-server` / Ollama / LM Studio
   - **mlx**: directory path → `mlx_lm.generate` / `mlx_lm.server` (Apple Silicon)
   - **safetensors**: directory path → `transformers` / `vllm`

4. **Error handling:**
   - If `status == "missing"`, downloads are disabled in their config —
     surface that to the user and stop.
   - If `model-shelf` exits **non-zero with a message on stderr**, surface
     the error verbatim and stop. Do **not** work around it — don't fall
     back to `huggingface-cli`, don't change paths, don't retry. Common causes:
     - **Volume not mounted** — user's external drive isn't connected.
     - **Shelf not initialized** — error tells them to run `model-shelf init`.
       Don't run it for them unless they explicitly ask; the curated shelf
       is a deliberate one-time setup the user owns.

## Examples

Loose user input — search first:
```
User: "fetch qwen 3 4b in mlx 4-bit"
You:  model-shelf find "qwen3 4b 4-bit" --format mlx --json --limit 5
      # pick top result, e.g. mlx-community/Qwen3-4B-4bit
      model-shelf resolve "mlx-community/Qwen3-4B-4bit" --json
```

Explicit repo — resolve directly:
```
User: "load Qwen/Qwen3-14B-GGUF with Q4_K_M"
You:  model-shelf resolve "Qwen/Qwen3-14B-GGUF" --quant Q4_K_M --json
```
