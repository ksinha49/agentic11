"""Base agent with common dependency wiring and lifecycle patterns."""

from __future__ import annotations

from typing import Any

from bluestar.core.config import AppSettings
from bluestar.core.protocols import ICacheBackend, IModelProvider, IRulesStore


class BaseAgent:
    """Common base for all BlueStar agents.

    Provides shared dependency injection pattern: model provider, rules store,
    cache backend, and settings are injected at construction time.
    """

    def __init__(
        self,
        *,
        settings: AppSettings,
        model: IModelProvider,
        rules_store: IRulesStore,
        cache: ICacheBackend,
    ) -> None:
        self._settings = settings
        self._model = model
        self._rules = rules_store
        self._cache = cache

    async def health_check(self) -> dict[str, Any]:
        """Return agent health status."""
        return {
            "agent": self.__class__.__name__,
            "status": "healthy",
            "environment": self._settings.environment,
        }
