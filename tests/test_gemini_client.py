"""
Unit tests for GeminiClient and provider presets.
"""

import os
import pytest
from twoma_bench.client import create_client, GeminiClient
from twoma_bench.client.base import ClientConfig, PROVIDER_PRESETS


def test_provider_presets_registry():
    assert "gemini" in PROVIDER_PRESETS
    assert "openai" in PROVIDER_PRESETS
    assert "anthropic" in PROVIDER_PRESETS
    assert "deepseek" in PROVIDER_PRESETS
    assert "ollama" in PROVIDER_PRESETS

    gemini_preset = PROVIDER_PRESETS["gemini"]
    assert "generativelanguage.googleapis.com" in gemini_preset["base_url"]
    assert gemini_preset["model"] == "gemini-2.5-pro"


def test_gemini_client_instantiation():
    config = ClientConfig(
        provider="gemini",
        api_key="test-gemini-key",
        model="gemini-2.5-flash",
    )
    client = create_client(config)
    assert isinstance(client, GeminiClient)
    assert client.config.model == "gemini-2.5-flash"
    assert "generativelanguage.googleapis.com" in client.endpoint
    assert client.config.api_key == "test-gemini-key"
    assert "Authorization" in client._get_headers()
    assert client._get_headers()["Authorization"] == "Bearer test-gemini-key"


def test_gemini_client_prefix_stripping():
    config = ClientConfig(
        provider="gemini",
        api_key="test-key",
        model="models/gemini-2.5-pro",
    )
    client = GeminiClient(config)
    assert client.config.model == "gemini-2.5-pro"
