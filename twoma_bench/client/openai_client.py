"""
OpenAI-compatible client adapter for 2MA-Bench.
Supports OpenAI, DeepSeek, vLLM, Ollama, OpenRouter, Groq, Together, Mistral, and more.
"""

import json
import time
import asyncio
import httpx
from typing import Optional, AsyncGenerator, Dict, Any
from .base import BaseLLMClient, ClientConfig, ModelResponse


class OpenAIClient(BaseLLMClient):
    """Client for any OpenAI-compatible /chat/completions API."""

    def __init__(self, config: ClientConfig):
        super().__init__(config)
        self.endpoint = self._resolve_endpoint(config.base_url)

    def _resolve_endpoint(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "2MA-Bench-Client/0.1.0",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        headers.update(self.config.extra_headers)
        return headers

    def _build_payload(self, prompt: str, system_prompt: Optional[str] = None, stream: bool = False) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        is_o_series = any(self.config.model.lower().startswith(prefix) for prefix in ("o1", "o3", "o4"))
        
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "stream": stream,
        }

        if is_o_series:
            # Newer reasoning models use max_completion_tokens
            payload["max_completion_tokens"] = self.config.max_tokens
            if self.config.reasoning_effort:
                payload["reasoning_effort"] = self.config.reasoning_effort
        else:
            payload["max_tokens"] = self.config.max_tokens
            payload["temperature"] = self.config.temperature

        return payload

    async def test_connection(self) -> tuple[bool, str]:
        """Verify that the API key and base URL can connect to the target model."""
        headers = self._get_headers()
        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": "Respond with 'OK'."}],
            "max_tokens": 5,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(self.endpoint, headers=headers, json=payload)
                if res.status_code == 200:
                    return True, "Successfully connected to model."
                return False, f"HTTP {res.status_code}: {res.text[:200]}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> ModelResponse:
        """Execute a non-streaming completion with retries."""
        headers = self._get_headers()
        payload = self._build_payload(prompt, system_prompt=system_prompt, stream=False)

        max_retries = 3
        start_time = time.perf_counter()

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                    resp = await client.post(self.endpoint, headers=headers, json=payload)

                    if resp.status_code == 429:
                        # Rate limit retry
                        await asyncio.sleep(2 ** attempt + 1)
                        continue

                    if resp.status_code >= 500:
                        # Server error retry
                        await asyncio.sleep(1.5 ** attempt)
                        continue

                    if resp.status_code != 200:
                        latency = (time.perf_counter() - start_time) * 1000
                        return ModelResponse(
                            content="",
                            latency_ms=latency,
                            error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                            success=False,
                        )

                    data = resp.json()
                    latency = (time.perf_counter() - start_time) * 1000

                    choice = data.get("choices", [{}])[0]
                    message = choice.get("message", {})
                    content = message.get("content") or ""

                    # Extract DeepSeek / vLLM reasoning content if present
                    thinking = message.get("reasoning_content") or message.get("reasoning")

                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

                    return ModelResponse(
                        content=content,
                        thinking_content=thinking,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        latency_ms=latency,
                        raw_response=data,
                        success=True,
                    )

            except httpx.TimeoutException:
                if attempt == max_retries - 1:
                    latency = (time.perf_counter() - start_time) * 1000
                    return ModelResponse(
                        content="",
                        latency_ms=latency,
                        error=f"Request timed out after {self.config.timeout}s",
                        success=False,
                    )
                await asyncio.sleep(1)
            except Exception as e:
                if attempt == max_retries - 1:
                    latency = (time.perf_counter() - start_time) * 1000
                    return ModelResponse(
                        content="",
                        latency_ms=latency,
                        error=f"Request failed: {str(e)}",
                        success=False,
                    )
                await asyncio.sleep(1)

        latency = (time.perf_counter() - start_time) * 1000
        return ModelResponse(
            content="",
            latency_ms=latency,
            error="Exceeded maximum retries.",
            success=False,
        )

    async def generate_stream(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chunks from the OpenAI-compatible endpoint."""
        headers = self._get_headers()
        payload = self._build_payload(prompt, system_prompt=system_prompt, stream=True)

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream("POST", self.endpoint, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    yield f"[Error: HTTP {response.status_code}]"
                    return

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content_piece = delta.get("content")
                            if content_piece:
                                yield content_piece
                    except json.JSONDecodeError:
                        continue
