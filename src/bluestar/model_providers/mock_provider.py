"""Mock model provider for local development and testing.

Returns canned responses. No real LLM calls.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

T = TypeVar("T")


class MockModelProvider:
    """IModelProvider implementation that returns deterministic mock responses."""

    def __init__(self, default_response: str = "Mock LLM response") -> None:
        self._default_response = default_response
        self._canned_responses: dict[str, str] = {}

    def set_response(self, prompt_contains: str, response: str) -> None:
        """Register a canned response for prompts containing a keyword."""
        self._canned_responses[prompt_contains] = response

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        last_content = messages[-1].get("content", "") if messages else ""
        for keyword, response in self._canned_responses.items():
            if keyword in last_content:
                return response
        return self._default_response

    def structured_output(
        self, messages: list[dict[str, str]], response_model: type[T], **kwargs: Any
    ) -> T:
        """Return a default instance of the response model."""
        return response_model()  # type: ignore[call-arg]
