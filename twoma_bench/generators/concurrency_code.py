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

    @staticmethod
    def get_deadlock_problem(seed: int, difficulty: int) -> Dict[str, Any]:
        rng = random.Random(seed)
        class_name = rng.choice(["AccountTransferManager", "BalanceTransferCoordinator", "FundTransferRouter"])

        buggy_code = f"""import threading
import time

class Account:
    def __init__(self, acc_id: int, balance: int = 1000):
        self.id = acc_id
        self.balance = balance
        self.lock = threading.Lock()

class {class_name}:
    \"\"\"Coordinator for multi-account fund transfers.\"\"\"
    def __init__(self):
        pass

    def transfer(self, from_acc: Account, to_acc: Account, amount: int) -> bool:
        # BUG: Acquiring locks in caller order causes AB-BA deadlocks when transfers are reciprocal
        with from_acc.lock:
            time.sleep(0.0002)  # Window for lock contention
            with to_acc.lock:
                if from_acc.balance >= amount:
                    from_acc.balance -= amount
                    to_acc.balance += amount
                    return True
                return False
"""

        oracle_code = f"""import threading
import time

class Account:
    def __init__(self, acc_id: int, balance: int = 1000):
        self.id = acc_id
        self.balance = balance
        self.lock = threading.Lock()

class {class_name}:
    def __init__(self):
        pass

    def transfer(self, from_acc: Account, to_acc: Account, amount: int) -> bool:
        # Prevent deadlock with consistent global lock ordering by account id
        first, second = (from_acc, to_acc) if from_acc.id < to_acc.id else (to_acc, from_acc)
        with first.lock:
            with second.lock:
                if from_acc.balance >= amount:
                    from_acc.balance -= amount
                    to_acc.balance += amount
                    return True
                return False
"""

        test_harness = f"""
import threading

mgr = {class_name}()
acc1 = Account(1, 10000)
acc2 = Account(2, 10000)

def worker1():
    for _ in range(40):
        mgr.transfer(acc1, acc2, 1)

def worker2():
    for _ in range(40):
        mgr.transfer(acc2, acc1, 1)

threads = [threading.Thread(target=worker1) for _ in range(4)] + [threading.Thread(target=worker2) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=3.0)

assert acc1.balance + acc2.balance == 20000, f"Balance leaked: {{acc1.balance + acc2.balance}}"
print("CONCURRENCY_TEST_PASSED")
"""

        return {
            "title": f"Lock Inversion Deadlock in {class_name}",
            "class_name": class_name,
            "buggy_code": buggy_code,
            "oracle_code": oracle_code,
            "test_harness": test_harness,
            "bug_description": "Acquiring locks in caller parameter order causes reciprocal transfers between accounts to deadlock (AB-BA lock ordering). Must impose consistent lock ordering by account ID.",
        }

    @staticmethod
    def get_atomic_counter_problem(seed: int, difficulty: int) -> Dict[str, Any]:
        rng = random.Random(seed)
        class_name = rng.choice(["ConcurrentHitCounter", "HighThroughputMetricsAggregator", "ThreadSafeRateAuditor"])

        buggy_code = f"""import threading
import time

class {class_name}:
    \"\"\"Aggregator tracking global and per-endpoint request metrics.\"\"\"
    def __init__(self):
        self.total_hits = 0
        self.endpoints = {{}}
        self.lock = threading.Lock()

    def record_hit(self, endpoint: str):
        # BUG: Unsynchronized read-modify-write on total_hits and endpoints dict
        current = self.total_hits
        time.sleep(0.0001)
        self.total_hits = current + 1
        if endpoint not in self.endpoints:
            self.endpoints[endpoint] = 0
        self.endpoints[endpoint] += 1

    def get_total(self) -> int:
        return self.total_hits

    def get_endpoint_hits(self, endpoint: str) -> int:
        return self.endpoints.get(endpoint, 0)
"""

        oracle_code = f"""import threading
import time

class {class_name}:
    def __init__(self):
        self.total_hits = 0
        self.endpoints = {{}}
        self.lock = threading.Lock()

    def record_hit(self, endpoint: str):
        with self.lock:
            self.total_hits += 1
            self.endpoints[endpoint] = self.endpoints.get(endpoint, 0) + 1

    def get_total(self) -> int:
        with self.lock:
            return self.total_hits

    def get_endpoint_hits(self, endpoint: str) -> int:
        with self.lock:
            return self.endpoints.get(endpoint, 0)
"""

        test_harness = f"""
import threading

counter = {class_name}()
num_threads = 8
hits_per_thread = 25
endpoints = ["/api/v1/auth", "/api/v1/data", "/api/v1/health"]

def worker(idx):
    ep = endpoints[idx % len(endpoints)]
    for _ in range(hits_per_thread):
        counter.record_hit(ep)

threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=3.0)

expected_total = num_threads * hits_per_thread
assert counter.get_total() == expected_total, f"Expected {{expected_total}} total hits, got {{counter.get_total()}}"
print("CONCURRENCY_TEST_PASSED")
"""

        return {
            "title": f"Unsynchronized Race Condition in {class_name}",
            "class_name": class_name,
            "buggy_code": buggy_code,
            "oracle_code": oracle_code,
            "test_harness": test_harness,
            "bug_description": "Unsynchronized reads and writes to shared counter and dictionary cause lost updates under concurrent access.",
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
            ConcurrencyBugTemplates.get_deadlock_problem,
            ConcurrencyBugTemplates.get_atomic_counter_problem,
        ]
        chosen = rng.choice(templates)(seed, difficulty)

        prompt = (
            f"The following Python class contains a critical concurrency bug (race condition, improper synchronization, or deadlock).\n\n"
            f"Buggy Implementation:\n"
            f"```python\n{chosen['buggy_code']}\n```\n\n"
            f"Stress Test Suite (executed with 50+ concurrent threads):\n"
            f"```python\n{chosen['test_harness']}\n```\n\n"
            f"Task & Submission Guidelines:\n"
            f"1. Identify and repair the concurrency bug in `{chosen['class_name']}`.\n"
            f"2. Your solution must safely pass the high-contention test harness without deadlocks, exceptions, or race conditions.\n"
            f"3. Preserve the original class name and all method signatures.\n"
            f"4. Provide your complete corrected code inside a single ```python and ``` block."
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
        class_name = problem.metadata["class_name"]

        # Extract python code blocks (including unclosed fences)
        code_matches = re.findall(r"```(?:python)?\s*([\s\S]*?)(?:```|$)", model_output)
        code_matches = [c.strip() for c in code_matches if c.strip()]

        candidate_code = None
        for code in code_matches:
            if f"class {class_name}" in code:
                candidate_code = code
                break

        # Fallback: scan raw model output if backticks were omitted
        if not candidate_code and f"class {class_name}" in model_output:
            raw_match = re.search(rf"(class {re.escape(class_name)}[\s\S]*?)(?=\n\n\n|\Z)", model_output)
            if raw_match:
                candidate_code = raw_match.group(1).strip()

        if not candidate_code:
            if code_matches:
                candidate_code = code_matches[0]
            else:
                return VerifierResult(
                    problem_id=problem.id,
                    dimension=self.dimension_id,
                    passed=False,
                    score=0.0,
                    failure_reason="No ```python code block found in response.",
                )

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
