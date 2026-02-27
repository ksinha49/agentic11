"""Download GGUF models from HuggingFace for in-process SLM deployment (Stage 2).

Usage:
    python scripts/download_models.py --model smollm3-3b --output-dir ./models/
"""

from __future__ import annotations

# TODO (Stage 2): Implement model download
# Models:
# - SmolLM3 3B (IDP Agent): Q4_K_M GGUF, ~2.2 GB
# - Arcee AFM 4.5B (Validator Agent): Q4_K_M GGUF, ~3 GB
# - Phi-4 Mini 3.8B (Transform Agent): Q4_K_M GGUF, ~2.5 GB
# - Qwen3 0.6B (optional routing): Q4_K_M GGUF, ~400 MB
