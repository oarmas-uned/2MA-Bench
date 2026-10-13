"""
Base definitions and protocols for 2MA-Bench LLM clients.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncGenerator
from pydantic import BaseModel, Field
import time


PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "provider": "openai",
        "name": "OpenAI (GPT-4o)",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "env_var": "OPENAI_API_KEY",
    },
    "anthropic": {
        "provider": "anthropic",
        "name": "Anthropic Claude (3.7 Sonnet)",
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-3-7-sonnet-20250219",
        "env_var": "ANTHROPIC_API_KEY",
    },
    "gemini": {
        "provider": "gemini",
        "name": "Google Gemini (2.5 Pro)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.5-pro",
        "env_var": "GEMINI_API_KEY",
    },
    "deepseek": {
        "provider": "openai",
        "name": "DeepSeek (R1 Reasoner)",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-reasoner",
        "env_var": "DEEPSEEK_API_KEY",
    },
    "ollama": {
        "provider": "openai",
        "name": "Local Ollama",
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.3:70b",
        "env_var": "",
    },
    "vllm": {
        "provider": "openai",
        "name": "Local vLLM",
        "base_url": "http://localhost:8000/v1",
        "model": "default",
        "env_var": "",
    },
    "openrouter": {
        "provider": "openai",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "anthropic/claude-3.7-sonnet",
        "env_var": "OPENROUTER_API_KEY",
    },
    "mock": {
        "provider": "mock",
        "name": "Mock Oracle (Offline)",
        "base_url": "http://localhost:8088",
        "model": "mock-oracle-v1",
        "env_var": "",
    },
}


class ClientConfig(BaseModel):
    """Configuration for connecting to an LLM provider."""
    provider: str = Field(default="openai", description="'openai', 'anthropic', 'gemini', or 'mock'")
    base_url: str = Field(default="https://api.openai.com/v1", description="API Base URL")
    api_key: str = Field(default="", description="API key or token")
    model: str = Field(default="gpt-4o", description="Target model identifier")
    temperature: float = Field(default=0.0, description="Sampling temperature")
    max_tokens: int = Field(default=8192, description="Maximum tokens for generation")
    timeout: float = Field(default=120.0, description="Request timeout in seconds")
    reasoning_effort: Optional[str] = Field(default=None, description="Optional reasoning effort (e.g. low/medium/high)")
    extra_headers: Dict[str, str] = Field(default_factory=dict, description="Additional HTTP headers")


class ModelResponse(BaseModel):
    """Standardized response from an LLM call."""
    content: str = ""
    thinking_content: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    success: bool = True


class BaseLLMClient(ABC):
    """Abstract base class for all LLM providers in 2MA-Bench."""

    def __init__(self, config: ClientConfig):
        self.config = config

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Test whether the endpoint is reachable and authenticated."""
        pass

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> ModelResponse:
        """Generate a complete completion for a given prompt."""
        pass

    @abstractmethod
    async def generate_stream(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Yield tokens asynchronously as they stream from the model."""
        pass
