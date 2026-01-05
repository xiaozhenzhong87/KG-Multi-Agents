"""Backward-compatible Deepseek client built on top of ModelClient."""
from __future__ import annotations

import os
from typing import Optional

from src.config.settings import settings
from .model_client import ModelClient


class DeepseekClient(ModelClient):
    """Thin wrapper that preserves the older Deepseek-specific API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        request_timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        super().__init__(
            provider="deepseek",
            api_key=api_key or settings.DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY"),
            base_url=base_url or settings.DEEPSEEK_BASE_URL or os.getenv("DEEPSEEK_BASE_URL"),
            model=model or settings.DEEPSEEK_MODEL or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            request_timeout=request_timeout,
            max_retries=max_retries,
        )
