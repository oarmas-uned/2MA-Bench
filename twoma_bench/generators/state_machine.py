"""
Dimension 2: Procedural Virtual Register Machine Emulation.
Synthesizes a synthetic assembly program executed on a simulated virtual machine.
Tests multi-step state tracking, bitwise operations, and loop invariant reasoning.
"""

import json
import random
import re
from typing import Dict, List, Tuple, Any, Optional
from .base import BaseGenerator, BenchmarkProblem, VerifierResult


class VirtualMachine:
    """Deterministic interpreter for the synthetic 2MA-Bench register machine."""

    def __init__(self, num_registers: int = 4):
        self.registers: Dict[str, int] = {f"R{i}": 0 for i in range(num_registers)}
        self.pc: int = 0
        self.cycles: int = 0
        self.halted: bool = False

    def execute(self, instructions: List[Dict[str, Any]], max_cycles: int = 300) -> Dict[str, int]:
        while not self.halted and 0 <= self.pc < len(instructions) and self.cycles < max_cycles:
            self.cycles += 1
            instr = instructions[self.pc]
            op = instr["op"]

            if op == "SET":
                r, val = instr["r1"], instr["val"]
                self.registers[r] = val % 256
                self.pc += 1
            elif op == "ADD":
                r1, r2 = instr["r1"], instr["r2"]
                self.registers[r1] = (self.registers[r1] + self.registers[r2]) % 256
                self.pc += 1
            elif op == "SUB":
                r1, r2 = instr["r1"], instr["r2"]
                self.registers[r1] = (self.registers[r1] - self.registers[r2]) % 256
                self.pc += 1
            elif op == "XOR":
                r1, r2 = instr["r1"], instr["r2"]
                self.registers[r1] = (self.registers[r1] ^ self.registers[r2]) % 256
                self.pc += 1
            elif op == "INC":
                r = instr["r1"]
                self.registers[r] = (self.registers[r] + 1) % 256
                self.pc += 1
            elif op == "DEC":
                r = instr["r1"]
                self.registers[r] = (self.registers[r] - 1) % 256
                self.pc += 1
            elif op == "SWP":
                r1, r2 = instr["r1"], instr["r2"]
                self.registers[r1], self.registers[r2] = self.registers[r2], self.registers[r1]
                self.pc += 1
            elif op == "JNZ":
                r, target = instr["r1"], instr["target"]
                if self.registers[r] != 0:
                    self.pc = target
                else:
                    self.pc += 1
            elif op == "JZ":
                r, target = instr["r1"], instr["target"]
                if self.registers[r] == 0:
                    self.pc = target
                else:
                    self.pc += 1
            elif op == "HALT":
                self.halted = True
                break
            else:
                self.pc += 1

        return dict(self.registers)


class StateMachineGenerator(BaseGenerator):
    """Procedurally generates virtual register programs with loops and bitwise logic."""

    @property
    def dimension_id(self) -> str:
        return "vm_emulation"

    @property
    def dimension_name(self) -> str:
        return "Virtual Register Machine Emulation"

    def generate(self, seed: int, difficulty: int = 1) -> BenchmarkProblem:
        rng = random.Random(seed)
        num_regs = 4 + (1 if difficulty >= 2 else 0)
        reg_names = [f"R{i}" for i in range(num_regs)]
        vm = VirtualMachine(num_registers=num_regs)

        # Initialize registers with seed-dependent small integers
        initial_regs = {r: rng.randint(1, 8) for r in reg_names}
        vm.registers = dict(initial_regs)

        # Procedurally synthesize an assembly routine
        # We ensure guaranteed loop termination by decrementing counter
        instructions: List[Dict[str, Any]] = []
        assembly_lines: List[str] = []

        # 1. Setup loop counter in R0 and accumulator in R1
        loop_count = rng.randint(3, 6 + difficulty * 2)
        instructions.append({"op": "SET", "r1": "R0", "val": loop_count})
        assembly_lines.append(f"0: SET R0, {loop_count}")

        # 2. Loop body with arithmetic / bitwise / swap operations
        loop_start = 1
        num_body_ops = 4 + difficulty * 2
        for _ in range(num_body_ops):
            op = rng.choice(["ADD", "SUB", "XOR", "INC", "SWP"])
            r1 = rng.choice(reg_names[1:])
            r2 = rng.choice(reg_names[1:])
            if op == "INC":
                instructions.append({"op": "INC", "r1": r1})
                assembly_lines.append(f"{len(instructions)-1}: INC {r1}")
            elif op == "SWP":
                instructions.append({"op": "SWP", "r1": r1, "r2": r2})
                assembly_lines.append(f"{len(instructions)-1}: SWP {r1}, {r2}")
            else:
                instructions.append({"op": op, "r1": r1, "r2": r2})
                assembly_lines.append(f"{len(instructions)-1}: {op} {r1}, {r2}")

        # 3. Decrement loop counter and branch back
        instructions.append({"op": "DEC", "r1": "R0"})
        assembly_lines.append(f"{len(instructions)-1}: DEC R0")

        instructions.append({"op": "JNZ", "r1": "R0", "target": loop_start})
        assembly_lines.append(f"{len(instructions)-1}: JNZ R0, {loop_start}")

        # 4. Final post-loop mutation and HALT
        extra_op = rng.choice(["XOR", "ADD", "INC"])
        if extra_op == "INC":
            instructions.append({"op": "INC", "r1": "R1"})
            assembly_lines.append(f"{len(instructions)-1}: INC R1")
        else:
            instructions.append({"op": extra_op, "r1": "R1", "r2": "R2"})
            assembly_lines.append(f"{len(instructions)-1}: {extra_op} R1, R2")

        instructions.append({"op": "HALT"})
        assembly_lines.append(f"{len(instructions)-1}: HALT")

        # Execute ground truth
        final_registers = vm.execute(instructions, max_cycles=500)

        program_text = "\n".join(assembly_lines)
        init_text = ", ".join(f"{r}={val}" for r, val in initial_regs.items())

        prompt = (
            f"Trace the exact execution of the following synthetic 8-bit Virtual Register Machine program.\n\n"
            f"Machine Architecture Specifications:\n"
            f"- Word size: 8-bit unsigned integer (all operations are strictly modulo 256 in [0, 255]).\n"
            f"- Registers: {', '.join(reg_names)}.\n"
            f"- Initial Register State: {init_text}.\n"
            f"- Program Counter (PC) starts at line 0.\n\n"
            f"Instruction Set Reference:\n"
            f"- SET Rx, val     : Rx = val % 256\n"
            f"- ADD Rx, Ry      : Rx = (Rx + Ry) % 256\n"
            f"- SUB Rx, Ry      : Rx = (Rx - Ry) % 256\n"
            f"- XOR Rx, Ry      : Rx = (Rx ^ Ry) % 256\n"
            f"- INC Rx          : Rx = (Rx + 1) % 256\n"
            f"- DEC Rx          : Rx = (Rx - 1) % 256\n"
            f"- SWP Rx, Ry      : Swap the values of Rx and Ry\n"
            f"- JNZ Rx, line_idx: If Rx != 0, set PC = line_idx; otherwise continue to next line\n"
            f"- HALT            : Stop execution\n\n"
            f"Program Listing:\n"
            f"```assembly\n{program_text}\n```\n\n"
            f"Calculate the EXACT final values of all registers when the machine halts.\n"
            f"Output your answer in a valid JSON block enclosed in ```json and ```:\n"
            f"```json\n"
            f"{{\n"
            + ",\n".join(f'  "{r}": <int>' for r in reg_names)
            + "\n}\n```"
        )

        return BenchmarkProblem(
            id=f"2ma_vm_{seed}_{difficulty}",
            dimension=self.dimension_id,
            dimension_name=self.dimension_name,
            seed=seed,
            difficulty=difficulty,
            title=f"Synthetic 8-Bit VM Emulation ({len(instructions)} opcodes)",
            prompt=prompt,
            expected_format='JSON: {"R0": int, "R1": int, ...}',
            ground_truth=final_registers,
            metadata={"initial_regs": initial_regs, "num_instructions": len(instructions), "cycles": vm.cycles},
        )

    async def verify(self, problem: BenchmarkProblem, model_output: str) -> VerifierResult:
        ground_truth: Dict[str, int] = problem.ground_truth
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", model_output, re.DOTALL)
        
        extracted_data = None
        if json_match:
            try:
                extracted_data = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        if not extracted_data:
            raw_match = re.search(r"\{\s*\"R0\".*?\}", model_output, re.DOTALL)
            if raw_match:
                try:
                    extracted_data = json.loads(raw_match.group(0))
                except json.JSONDecodeError:
                    pass

        if not extracted_data or not isinstance(extracted_data, dict):
            return VerifierResult(
                problem_id=problem.id,
                dimension=self.dimension_id,
                passed=False,
                score=0.0,
                ground_truth=ground_truth,
                failure_reason="Could not extract valid JSON register map from output.",
            )

        correct_count = 0
        total_regs = len(ground_truth)
        mismatches = {}

        for reg, true_val in ground_truth.items():
            user_val = extracted_data.get(reg)
            try:
                user_val_int = int(user_val) if user_val is not None else None
            except (ValueError, TypeError):
                user_val_int = None

            if user_val_int == true_val:
                correct_count += 1
            else:
                mismatches[reg] = {"expected": true_val, "got": user_val}

        passed = (correct_count == total_regs)
        score = round(correct_count / total_regs, 3)

        return VerifierResult(
            problem_id=problem.id,
            dimension=self.dimension_id,
            passed=passed,
            score=score,
            extracted_answer=extracted_data,
            ground_truth=ground_truth,
            failure_reason=None if passed else f"Register mismatches: {mismatches}",
            details={"correct_registers": correct_count, "total_registers": total_regs, "mismatches": mismatches},
        )

    def get_oracle_solution(self, problem: BenchmarkProblem) -> str:
        return f"```json\n{json.dumps(problem.ground_truth, indent=2)}\n```"
