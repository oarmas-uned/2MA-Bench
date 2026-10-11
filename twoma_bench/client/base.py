"""
Base definitions and protocols for 2MA-Bench LLM clients.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncGenerator
from pydantic import BaseModel, Field
import time


class ClientConfig(BaseModel):
    """Configuration for connecting to an LLM provider."""
    provider: str = Field(default="openai", description="'openai', 'anthropic', or 'mock'")
    base_url: str = Field(default="https://api.openai.com/v1", description="API Base URL")
    api_key: str = Field(default="", description="API key or token")
    model: str = Field(default="gpt-4o", description="Target model identifier")
    temperature: float = Field(default=0.0, description="Sampling temperature")
    max_tokens: int = Field(default=4096, description="Maximum tokens for generation")
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
