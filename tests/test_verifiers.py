"""
Tests for subprocess sandbox execution and timeout protection.
"""

import pytest
from twoma_bench.evaluator.sandbox import run_in_sandbox


@pytest.mark.asyncio
async def test_sandbox_normal_execution():
    code = "print('HELLO_2MA')\n"
    res = await run_in_sandbox(code, timeout_seconds=3.0)
    assert res.success is True
    assert "HELLO_2MA" in res.stdout
    assert res.timed_out is False


@pytest.mark.asyncio
async def test_sandbox_timeout_kill():
    # Infinite loop must be killed within timeout
    code = "import time\nwhile True:\n    time.sleep(0.1)\n"
    res = await run_in_sandbox(code, timeout_seconds=1.0)
    assert res.success is False
    assert res.timed_out is True
    assert res.return_code == -9


@pytest.mark.asyncio
async def test_sandbox_syntax_error():
    code = "def invalid_syntax(:\n"
    res = await run_in_sandbox(code, timeout_seconds=2.0)
    assert res.success is False
    assert "SyntaxError" in res.stderr
    assert res.timed_out is False
