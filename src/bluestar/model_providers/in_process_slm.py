"""In-process SLM provider via llama-cpp-python (Stage 2).

Loads GGUF model directly into agent process memory.
Zero HTTP overhead, zero network hops.
"""

from __future__ import annotations

# TODO (Stage 2): Implement InProcessSLM using llama-cpp-python
# - Load GGUF model at container startup
# - Warm up with dummy inference
# - Provide chat() and structured_output() via llama_cpp.Llama
# - Models: SmolLM3 3B (IDP), Arcee AFM 4.5B (Validator), Phi-4 Mini 3.8B (Transform)
