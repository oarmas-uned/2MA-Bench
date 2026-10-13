"""
LLM Client registry and factory for 2MA-Bench.
"""

from .base import BaseLLMClient, ClientConfig, ModelResponse, PROVIDER_PRESETS
from .openai_client import OpenAIClient
from .anthropic_client import AnthropicClient
from .gemini_client import GeminiClient
from .mock_client import MockClient


def create_client(config: ClientConfig) -> BaseLLMClient:
    """Factory function to instantiate the proper client based on config."""
    prov = config.provider.lower().strip()
    if prov in ("anthropic", "claude"):
        return AnthropicClient(config)
    elif prov in ("gemini", "google"):
        return GeminiClient(config)
    elif prov == "mock":
        return MockClient(config)
    else:
        # Default to OpenAI-compatible for openai, vllm, ollama, groq, deepseek, openrouter, etc.
        return OpenAIClient(config)


__all__ = [
    "BaseLLMClient",
    "ClientConfig",
    "ModelResponse",
    "PROVIDER_PRESETS",
    "OpenAIClient",
    "AnthropicClient",
    "GeminiClient",
    "MockClient",
    "create_client",
]

