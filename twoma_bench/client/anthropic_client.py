"""
Anthropic Claude client adapter for 2MA-Bench.
Supports Claude 3.5 Sonnet, Claude 3.7 Sonnet, Haiku, Opus, etc.
"""

import json
import time
import asyncio
import httpx
from typing import Optional, AsyncGenerator, Dict, Any
from .base import BaseLLMClient, ClientConfig, ModelResponse


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic /v1/messages API."""

    def __init__(self, config: ClientConfig):
        super().__init__(config)
        self.endpoint = self._resolve_endpoint(config.base_url)

    def _resolve_endpoint(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        if base == "https://api.openai.com/v1" or not base:
            return "https://api.anthropic.com/v1/messages"
        if base.endswith("/messages"):
            return base
        return f"{base}/v1/messages"

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "User-Agent": "2MA-Bench-Client/0.1.0",
        }
        headers.update(self.config.extra_headers)
        return headers

    def _build_payload(self, prompt: str, system_prompt: Optional[str] = None, stream: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": stream,
        }
        if system_prompt:
            payload["system"] = system_prompt
        return payload

    async def test_connection(self) -> tuple[bool, str]:
        """Verify API key and model connectivity with Anthropic."""
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
                    return True, "Successfully connected to Anthropic API."
                return False, f"HTTP {res.status_code}: {res.text[:200]}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> ModelResponse:
        """Execute non-streaming request against Anthropic API."""
        headers = self._get_headers()
        payload = self._build_payload(prompt, system_prompt=system_prompt, stream=False)

        max_retries = 3
        start_time = time.perf_counter()

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                    resp = await client.post(self.endpoint, headers=headers, json=payload)

                    if resp.status_code == 429:
                        await asyncio.sleep(2 ** attempt + 1)
                        continue

                    if resp.status_code >= 500:
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

                    content_blocks = data.get("content", [])
                    content = ""
                    thinking = None
                    for block in content_blocks:
                        if block.get("type") == "text":
                            content += block.get("text", "")
                        elif block.get("type") == "thinking":
                            thinking = block.get("thinking", "")

                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("input_tokens", 0)
                    completion_tokens = usage.get("output_tokens", 0)
                    total_tokens = prompt_tokens + completion_tokens

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
        """Stream chunks from Anthropic Messages API."""
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
                    try:
                        event = json.loads(data_str)
                        event_type = event.get("type")
                        if event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
                    except json.JSONDecodeError:
                        continue
