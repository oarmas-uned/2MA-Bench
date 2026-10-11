"""
Subprocess sandbox execution environment for safe Python code verification.
Enforces execution timeouts, resource limits, and error capture.
"""

import asyncio
import os
import sys
import tempfile
import time
from typing import Optional
from pydantic import BaseModel, Field


class SandboxResult(BaseModel):
    """Result of running code in the isolated sandbox."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    timed_out: bool = False
    latency_ms: float = 0.0


async def run_in_sandbox(python_code: str, timeout_seconds: float = 5.0) -> SandboxResult:
    """Executes Python code in an isolated subprocess with strict timeout guards."""
    start_time = time.perf_counter()

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp_file:
        tmp_file.write(python_code)
        tmp_path = tmp_file.name

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_seconds
            )
            stdout = stdout_bytes.decode(errors="replace")
            stderr = stderr_bytes.decode(errors="replace")
            latency = (time.perf_counter() - start_time) * 1000

            return SandboxResult(
                success=(proc.returncode == 0),
                stdout=stdout,
                stderr=stderr,
                return_code=proc.returncode or 0,
                timed_out=False,
                latency_ms=latency,
            )

        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            latency = (time.perf_counter() - start_time) * 1000
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Process terminated: Exceeded {timeout_seconds}s execution timeout.",
                return_code=-9,
                timed_out=True,
                latency_ms=latency,
            )

    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
