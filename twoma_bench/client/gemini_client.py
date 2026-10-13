"""
Google Gemini client adapter for 2MA-Bench.
Supports Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 1.5 Pro, and custom endpoints.
Uses Google's high-performance OpenAI-compatible v1beta API bridge.
"""

import os
from typing import Dict, Any, Optional
from .base import ClientConfig
from .openai_client import OpenAIClient


class GeminiClient(OpenAIClient):
    """Client adapter for Google Gemini models."""

    def __init__(self, config: ClientConfig):
        # Auto-detect GEMINI_API_KEY if not explicitly provided
        api_key = config.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        
        # Default Gemini base_url to Google's official OpenAI-compatible bridge
        base_url = config.base_url
        if not base_url or base_url == "https://api.openai.com/v1":
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai"

        # Normalize model name
        model = config.model or "gemini-2.5-pro"
        if model.startswith("models/"):
            model = model.replace("models/", "")

        updated_config = config.model_copy(
            update={
                "provider": "gemini",
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
            }
        )
        super().__init__(updated_config)

    def _get_headers(self) -> Dict[str, str]:
        headers = super()._get_headers()
        headers["User-Agent"] = "2MA-Bench-GeminiClient/0.1.0"
        return headers
