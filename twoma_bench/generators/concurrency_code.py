"""
Dimension 4: Sandboxed Concurrent Code Synthesis & Race Condition Repair.
Procedurally generates concurrent Python code containing subtle race conditions,
deadlocks, or atomicity bugs, verified via sandboxed multi-threaded stress tests.
"""

import json
import random
import re
from typing import Dict, List, Tuple, Any, Optional
from .base import BaseGenerator, BenchmarkProblem, VerifierResult
from ..evaluator.sandbox import run_in_sandbox


class ConcurrencyBugTemplates:
    """Templates for procedural concurrency challenges."""

    @staticmethod
    def get_token_bucket_problem(seed: int, difficulty: int) -> Dict[str, Any]:
        rng = random.Random(seed)
        class_name = rng.choice(["AtomicRateLimiter", "TokenBucketGuard", "ConcurrencyLimiter", "ThroughputGovernor"])
        capacity = rng.randint(20, 50)

        buggy_code = f"""import time
import threading

class {class_name}:
    \"\"\"Thread-safe rate limiter with capacity {capacity}.\"\"\"
    def __init__(self, capacity={capacity}):
        self.capacity = capacity
        self.tokens = capacity
        self.lock = threading.Lock()

    def acquire(self, amount=1) -> bool:
        # BUG: Check-then-act race condition outside the lock!
        if self.tokens >= amount:
            time.sleep(0.0001)  # Context switch window
            with self.lock:
                self.tokens -= amount
            return True
        return False
"""

        oracle_code = f"""import time
import threading

class {class_name}:
    def __init__(self, capacity={capacity}):
        self.capacity = capacity
        self.tokens = capacity
        self.lock = threading.Lock()

    def acquire(self, amount=1) -> bool:
        with self.lock:
            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False
"""

        test_harness = f"""
import threading
import time

limiter = {class_name}(capacity={capacity})
successful_acquisitions = 0
lock = threading.Lock()

def worker():
    global successful_acquisitions
    if limiter.acquire(1):
        with lock:
            successful_acquisitions += 1

threads = [threading.Thread(target=worker) for _ in range(100)]
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=3.0)

# Critical Assertions:
assert limiter.tokens >= 0, f"Overdrawn tokens: {{limiter.tokens}}"
assert successful_acquisitions <= {capacity}, f"Race condition permitted {{successful_acquisitions}} > {capacity} acquires!"
assert successful_acquisitions == {capacity}, f"Expected {capacity} acquisitions, got {{successful_acquisitions}}"
print("CONCURRENCY_TEST_PASSED")
"""

        return {
            "title": f"Race Condition in {class_name}",
            "class_name": class_name,
            "buggy_code": buggy_code,
            "oracle_code": oracle_code,
            "test_harness": test_harness,
            "bug_description": "A check-then-act race condition permits threads to overdraw tokens because tokens >= amount is checked before acquiring the lock.",
        }

    @staticmethod
    def get_condition_variable_problem(seed: int, difficulty: int) -> Dict[str, Any]:
        rng = random.Random(seed)
        class_name = rng.choice(["ThreadSafeBoundedBuffer", "BlockingTaskQueue", "BoundedEventQueue"])
        capacity = rng.randint(3, 8)

        buggy_code = f"""import threading
import collections

class {class_name}:
    def __init__(self, maxsize={capacity}):
        self.maxsize = maxsize
        self.queue = collections.deque()
        self.cond = threading.Condition()

    def put(self, item):
        with self.cond:
            # BUG: Spurious wakeup / race: 'if' instead of 'while'
            if len(self.queue) >= self.maxsize:
                self.cond.wait()
            self.queue.append(item)
            self.cond.notify_all()

    def get(self):
        with self.cond:
            # BUG: 'if' instead of 'while'
            if len(self.queue) == 0:
                self.cond.wait()
            item = self.queue.popleft()
            self.cond.notify_all()
            return item
"""

        oracle_code = f"""import threading
import collections

class {class_name}:
    def __init__(self, maxsize={capacity}):
        self.maxsize = maxsize
        self.queue = collections.deque()
        self.cond = threading.Condition()

    def put(self, item):
        with self.cond:
            while len(self.queue) >= self.maxsize:
                self.cond.wait()
            self.queue.append(item)
            self.cond.notify_all()

    def get(self):
        with self.cond:
            while len(self.queue) == 0:
                self.cond.wait()
            item = self.queue.popleft()
            self.cond.notify_all()
            return item
"""

        test_harness = f"""
import threading
import time

q = {class_name}(maxsize={capacity})
consumed = []
lock = threading.Lock()

def producer(count):
    for i in range(count):
        q.put(i)

def consumer(count):
    for _ in range(count):
        val = q.get()
        with lock:
            consumed.append(val)

num_producers = 4
num_consumers = 4
items_per_thread = 25

threads = []
for _ in range(num_producers):
    threads.append(threading.Thread(target=producer, args=(items_per_thread,)))
for _ in range(num_consumers):
    threads.append(threading.Thread(target=consumer, args=(items_per_thread,)))

for t in threads:
    t.start()
for t in threads:
    t.join(timeout=4.0)

total_items = num_producers * items_per_thread
assert len(consumed) == total_items, f"Expected {{total_items}} items, got {{len(consumed)}}"
print("CONCURRENCY_TEST_PASSED")
"""

        return {
            "title": f"Spurious Wakeup Bug in {class_name}",
            "class_name": class_name,
            "buggy_code": buggy_code,
            "oracle_code": oracle_code,
            "test_harness": test_harness,
            "bug_description": "Uses 'if' instead of 'while' for condition checks in a multi-producer multi-consumer bounded buffer, leading to queue overflow or popping from an empty queue.",
        }


class ConcurrencyGenerator(BaseGenerator):
    """Generates concurrent code repair problems with sandboxed stress test verification."""

    @property
    def dimension_id(self) -> str:
        return "concurrency"

    @property
    def dimension_name(self) -> str:
        return "Sandboxed Concurrency & Race Condition Repair"

    def generate(self, seed: int, difficulty: int = 1) -> BenchmarkProblem:
        rng = random.Random(seed)
        templates = [
            ConcurrencyBugTemplates.get_token_bucket_problem,
            ConcurrencyBugTemplates.get_condition_variable_problem,
        ]
        chosen = rng.choice(templates)(seed, difficulty)

        prompt = (
            f"The following Python class contains a critical concurrency bug (race condition, improper synchronization, or deadlock).\n\n"
            f"Buggy Implementation:\n"
            f"```python\n{chosen['buggy_code']}\n```\n\n"
            f"Stress Test Suite (executed with 50+ concurrent threads):\n"
            f"```python\n{chosen['test_harness']}\n```\n\n"
            f"Task:\n"
            f"Identify and fix the concurrency bug in `{chosen['class_name']}`.\n"
            f"Your fixed code must pass the high-contention test harness without deadlocks, exceptions, or race conditions.\n"
            f"Provide your complete corrected class implementation inside a single ```python code block."
        )

        return BenchmarkProblem(
            id=f"2ma_concur_{seed}_{difficulty}",
            dimension=self.dimension_id,
            dimension_name=self.dimension_name,
            seed=seed,
            difficulty=difficulty,
            title=chosen["title"],
            prompt=prompt,
            expected_format="Python code block: ```python ... ```",
            ground_truth=chosen["oracle_code"],
            metadata={
                "class_name": chosen["class_name"],
                "test_harness": chosen["test_harness"],
                "bug_description": chosen["bug_description"],
            },
        )

    async def verify(self, problem: BenchmarkProblem, model_output: str) -> VerifierResult:
        # Extract python code block
        code_matches = re.findall(r"```(?:python)?\s*(.*?)```", model_output, re.DOTALL)
        if not code_matches:
            return VerifierResult(
                problem_id=problem.id,
                dimension=self.dimension_id,
                passed=False,
                score=0.0,
                failure_reason="No ```python code block found in response.",
            )

        # Pick the block containing the class definition
        class_name = problem.metadata["class_name"]
        candidate_code = None
        for code in code_matches:
            if f"class {class_name}" in code:
                candidate_code = code
                break

        if not candidate_code:
            candidate_code = code_matches[0]

        # Combine fixed code with test harness
        full_script = f"{candidate_code}\n\n{problem.metadata['test_harness']}"

        # Execute in sandbox
        sandbox_res = await run_in_sandbox(full_script, timeout_seconds=5.0)

        passed = sandbox_res.success and "CONCURRENCY_TEST_PASSED" in sandbox_res.stdout
        score = 1.0 if passed else 0.0

        failure_reason = None
        if not passed:
            if sandbox_res.timed_out:
                failure_reason = "Execution timed out (deadlock or infinite wait detected)."
            elif sandbox_res.stderr:
                failure_reason = f"Execution error: {sandbox_res.stderr.strip()[-300:]}"
            else:
                failure_reason = "Test harness assertions failed under high-concurrency stress."

        return VerifierResult(
            problem_id=problem.id,
            dimension=self.dimension_id,
            passed=passed,
            score=score,
            extracted_answer=candidate_code,
            ground_truth="Thread-safe synchronization implementation",
            failure_reason=failure_reason,
            details={"sandbox_timed_out": sandbox_res.timed_out, "stdout": sandbox_res.stdout, "stderr": sandbox_res.stderr},
        )

    def get_oracle_solution(self, problem: BenchmarkProblem) -> str:
        return f"```python\n{problem.ground_truth}\n```"
