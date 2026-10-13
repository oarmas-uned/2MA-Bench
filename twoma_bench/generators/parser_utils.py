"""
Robust parser and sanitization utilities for LLM benchmark responses.
Handles long reasoning chains, truncated tokens, relaxed JSON, inline comments,
and multiple markdown code blocks across frontier and reasoning models.
"""

import re
import json
from typing import Any, Dict, List, Optional, Sequence


def strip_reasoning_tags(text: str) -> str:
    """
    Strips explicit thinking/scratchpad tags like <think>...</think>,
    <thought>...</thought>, <scratchpad>...</scratchpad>.
    Returns cleaned text, preserving anything after the final closing tag.
    """
    if not text:
        return ""

    # Remove standard <think>...</think> blocks
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<thought>[\s\S]*?</thought>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<scratchpad>[\s\S]*?</scratchpad>", "", cleaned, flags=re.IGNORECASE)
    
    # If stripping left empty text (e.g. model output entirely inside think tags), return original
    if not cleaned.strip():
        return text

    return cleaned


def clean_relaxed_json(text: str) -> str:
    """
    Transforms relaxed JSON (comments, trailing commas, single quotes) into standard JSON.
    """
    s = text.strip()

    # Strip single-line comments // ...
    # Be careful not to strip http:// or inside strings
    s = re.sub(r"(?<![:\"'])\/\/.*$", "", s, flags=re.MULTILINE)

    # Strip multi-line comments /* ... */
    s = re.sub(r"\/\*[\s\S]*?\*\/", "", s)

    # Remove trailing commas before } or ]
    s = re.sub(r",\s*([}\]])", r"\1", s)

    # Fix unquoted keys e.g. { R0: 0, R1: 1 } -> { "R0": 0, "R1": 1 }
    s = re.sub(r'(?<=[{,])\s*([A-Za-z0-9_]+)\s*:', r' "\1":', s)

    # Convert single-quoted strings to double quotes: 'key': 'val'
    # Simple regex replacing '...' where no double quote is adjacent
    def replace_single_quotes(match):
        val = match.group(0)
        inner = val[1:-1].replace('"', '\\"')
        return f'"{inner}"'

    s = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", replace_single_quotes, s)

    return s.strip()


def repair_truncated_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Attempts to repair a JSON object truncated mid-stream due to max_token limits.
    """
    # Find the last open brace
    last_open = text.rfind("{")
    if last_open == -1:
        return None

    snippet = text[last_open:].strip()
    
    # Strip any trailing code fence
    snippet = re.sub(r"```.*$", "", snippet).strip()

    # If it ends with an unclosed string or colon/comma, trim it back to the last valid key-value
    # Try closing the braces progressively
    candidates = [
        snippet + "}",
        snippet + '"}}',
        snippet + '"}',
        re.sub(r",\s*$", "", snippet) + "}",
        re.sub(r":\s*[^,}]*$", "", snippet) + "}",
    ]

    for cand in candidates:
        try:
            cleaned = clean_relaxed_json(cand)
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and len(parsed) > 0:
                return parsed
        except Exception:
            continue

    return None


def extract_all_json_blocks(text: str) -> List[str]:
    """
    Finds all potential JSON block candidates enclosed in ``` ``` or raw braces.
    """
    candidates = []

    # 1. Matches enclosed in ```json ... ``` or ``` ... ```
    fenced_matches = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    for block in fenced_matches:
        block = block.strip()
        if block.startswith("{") and block.endswith("}"):
            candidates.append(block)
        else:
            # Check if there is a { ... } inside the fence
            inner = re.search(r"(\{[\s\S]*\})", block)
            if inner:
                candidates.append(inner.group(1).strip())

    # 2. Balanced brace scanner for any un-fenced JSON objects
    brace_depth = 0
    start_idx = None
    for i, ch in enumerate(text):
        if ch == "{":
            if brace_depth == 0:
                start_idx = i
            brace_depth += 1
        elif ch == "}":
            if brace_depth > 0:
                brace_depth -= 1
                if brace_depth == 0 and start_idx is not None:
                    obj_candidate = text[start_idx : i + 1].strip()
                    if obj_candidate not in candidates:
                        candidates.append(obj_candidate)
                    start_idx = None

    return candidates


def unpack_nested_dict(d: Dict[str, Any], target_keys: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """
    Unpacks nested wrapper dictionaries like {"registers": {...}} or {"assignment": {...}}.
    If target_keys are given, finds the sub-dict containing the most target keys.
    """
    if not isinstance(d, dict):
        return {}

    if target_keys:
        target_set = set(target_keys)
        # Check current level
        if target_set.issubset(set(d.keys())) or any(k in d for k in target_keys):
            return d

        # Check immediate children
        best_child = d
        best_match_count = sum(1 for k in target_keys if k in d)
        for _, val in d.items():
            if isinstance(val, dict):
                count = sum(1 for k in target_keys if k in val)
                if count > best_match_count:
                    best_match_count = count
                    best_child = val
        return best_child

    # Common wrapper keys
    for wrapper in ("assignment", "registers", "final_registers", "state", "final_state", "result", "answer", "output"):
        if wrapper in d and isinstance(d[wrapper], dict):
            return d[wrapper]

    return d


def extract_json_dict(
    text: str,
    target_keys: Optional[Sequence[str]] = None,
    prefer_last: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Extracts a dictionary from model output, prioritizing the final answer block
    and tolerating reasoning traces, comments, trailing commas, and wrappers.
    """
    if not text or not text.strip():
        return None

    # Step 1: Strip thinking blocks if text after thinking exists
    search_texts = []
    stripped = strip_reasoning_tags(text)
    if stripped != text and stripped.strip():
        search_texts.append(stripped)
    search_texts.append(text)

    for search_text in search_texts:
        blocks = extract_all_json_blocks(search_text)
        if prefer_last:
            blocks = list(reversed(blocks))

        for block in blocks:
            # Try raw parse first
            try:
                parsed = json.loads(block)
                if isinstance(parsed, dict):
                    unpacked = unpack_nested_dict(parsed, target_keys)
                    if target_keys is None or any(k in unpacked for k in target_keys):
                        return unpacked
            except Exception:
                pass

            # Try relaxed JSON cleanup
            try:
                cleaned = clean_relaxed_json(block)
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    unpacked = unpack_nested_dict(parsed, target_keys)
                    if target_keys is None or any(k in unpacked for k in target_keys):
                        return unpacked
            except Exception:
                pass

        # Try repairing truncated JSON at the end of the text
        repaired = repair_truncated_json(search_text)
        if repaired:
            unpacked = unpack_nested_dict(repaired, target_keys)
            if target_keys is None or any(k in unpacked for k in target_keys):
                return unpacked

    return None


def extract_key_value_assignments(
    text: str,
    target_keys: Sequence[str],
) -> Optional[Dict[str, int]]:
    """
    Robust fallback scanner: extracts integer assignments directly from text
    even if the model did not format valid JSON (e.g. text lists, markdown tables, plain assignments).
    Takes the LAST assignment of each key in the document (final state over intermediate states).
    """
    if not text or not target_keys:
        return None

    extracted: Dict[str, int] = {}

    # Strip thinking tags so we prioritize final conclusion text
    cleaned_text = strip_reasoning_tags(text)

    for key in target_keys:
        # Multiple regex patterns for key-value assignment:
        # 1. "R0": 42 or 'R0': 42 or R0: 42
        # 2. R0 = 42
        # 3. | R0 | 42 | (markdown table)
        # 4. R0 is 42 or R0 -> 42
        patterns = [
            rf'(?:["\']?{re.escape(key)}["\']?)\s*[:=]\s*(-?\d+)',
            rf'\|\s*{re.escape(key)}\s*\|\s*(-?\d+)\s*\|',
            rf'\b{re.escape(key)}\b\s*(?:is|->|becomes)\s*(-?\d+)',
        ]

        found_val = None
        for pat in patterns:
            # Find all occurrences in cleaned text
            matches = list(re.finditer(pat, cleaned_text, re.IGNORECASE))
            if not matches:
                # Fallback to full text if not found in cleaned
                matches = list(re.finditer(pat, text, re.IGNORECASE))

            if matches:
                # Take the LAST match in the text (final state)
                last_match = matches[-1]
                try:
                    found_val = int(last_match.group(1))
                    break
                except (ValueError, TypeError):
                    continue

        if found_val is not None:
            extracted[key] = found_val

    # If we found at least one of the target keys, return the extracted map
    if extracted:
        return extracted

    return None
