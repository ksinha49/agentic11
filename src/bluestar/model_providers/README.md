# `bluestar/model_providers` — LLM Abstraction

Pluggable model providers behind the `IModelProvider` protocol. Agents call `chat()` or `structured_output()` without knowing which backend serves the response.

## Providers

| File | Class | When Used |
|------|-------|-----------|
| `mock_provider.py` | `MockModelProvider` | Unit tests and local dev |
| `bedrock_provider.py` | `BedrockModelProvider` | Production (Claude Sonnet/Haiku via LiteLLM) |
| `in_process_slm.py` | `InProcessSLM` | Production (GGUF models via llama-cpp-python) |

## Protocol

```python
class IModelProvider(Protocol):
    def chat(self, messages: list[dict], **kwargs) -> str: ...
    def structured_output(self, messages: list[dict], response_model: type[T], **kwargs) -> T: ...
```

## Usage

```python
# In tests
from bluestar.model_providers.mock_provider import MockModelProvider

mock = MockModelProvider()
mock.set_response("schema", '{"columns": [...]}')
result = mock.chat([{"role": "user", "content": "infer schema for this file"}])

# In production — selected by BLUESTAR_LLM_PROVIDER env var
```

## Model Assignments

| Agent | Model | Provider |
|-------|-------|----------|
| Orchestrator | Claude Sonnet | Bedrock (via LiteLLM) |
| IDP | SmolLM3 3B | In-process SLM |
| Validator | Arcee AFM 4.5B | In-process SLM |
| Transform | Phi-4 Mini 3.8B | In-process SLM |
| Compliance | Claude Sonnet | Bedrock (via LiteLLM) |

## Current Status

- **MockModelProvider:** Fully implemented — canned responses for testing
- **BedrockModelProvider:** Stage 2 placeholder (routes through LiteLLM proxy)
- **InProcessSLM:** Stage 2 placeholder (loads GGUF via llama-cpp-python)
