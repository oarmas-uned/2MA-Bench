"""
Mock LLM client for offline validation, sanity checks, and UI testing.
"""

import asyncio
from typing import Optional, AsyncGenerator, Callable, Any
from .base import BaseLLMClient, ClientConfig, ModelResponse


class MockClient(BaseLLMClient):
    """Configurable mock client that simulates model responses."""

    def __init__(self, config: ClientConfig, oracle_solver: Optional[Callable[[str], str]] = None, mock_mode: str = "oracle"):
        super().__init__(config)
        self.oracle_solver = oracle_solver
        self.mock_mode = mock_mode  # "oracle", "random", "error"

    async def test_connection(self) -> tuple[bool, str]:
        return True, "Mock client online and operational."

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> ModelResponse:
        await asyncio.sleep(0.05)  # Simulate fast inference latency

        if self.mock_mode == "error":
            return ModelResponse(
                content="",
                latency_ms=50.0,
                error="Simulated provider timeout",
                success=False,
            )

        if self.mock_mode == "oracle" and self.oracle_solver:
            content = self.oracle_solver(prompt)
        elif self.mock_mode == "oracle":
            content = "{\"status\": \"mock_answer\"}"
        else:
            content = "This is a hallucinated wrong answer: 42."

        prompt_tokens = len(prompt.split())
        completion_tokens = len(content.split())

        return ModelResponse(
            content=content,
            thinking_content="Simulated chain-of-thought: Analyzed constraints -> derived solution.",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=50.0,
            success=True,
        )

    async def generate_stream(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        res = await self.generate(prompt, system_prompt)
        if not res.success:
            yield f"[Error: {res.error}]"
            return
        
        words = res.content.split(" ")
        for w in words:
            await asyncio.sleep(0.01)
            yield w + " "
