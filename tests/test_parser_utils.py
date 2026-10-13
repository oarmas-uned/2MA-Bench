"""
Tests for robust parser and sanitization utilities.
Verifies extraction from real-world frontier model output formats.
"""

import pytest
from twoma_bench.generators.parser_utils import (
    strip_reasoning_tags,
    clean_relaxed_json,
    extract_json_dict,
    extract_key_value_assignments,
)


def test_strip_reasoning_tags():
    raw = "<think>\nLet's trace R0: 4\n</think>\nFinal answer:\n```json\n{\"R0\": 0}\n```"
    stripped = strip_reasoning_tags(raw)
    assert "<think>" not in stripped
    assert '{"R0": 0}' in stripped


def test_clean_relaxed_json():
    # Trailing commas and comments
    relaxed = """{
        // loop count
        "R0": 0,
        /* accumulator */
        "R1": 15,
        R2: 42,
    }"""
    cleaned = clean_relaxed_json(relaxed)
    import json
    parsed = json.loads(cleaned)
    assert parsed == {"R0": 0, "R1": 15, "R2": 42}


def test_extract_json_dict_multiple_blocks_prefers_last():
    # Model traces steps with intermediate JSON, then outputs final JSON
    output = """
    Step 1:
    ```json
    {"R0": 4, "R1": 2}
    ```
    Step 2:
    ```json
    {"R0": 3, "R1": 5}
    ```
    Therefore, the final register states are:
    ```json
    {
      "R0": 0,
      "R1": 15,
      "R2": 42,
      "R3": 99
    }
    ```
    """
    target_keys = ["R0", "R1", "R2", "R3"]
    extracted = extract_json_dict(output, target_keys=target_keys)
    assert extracted is not None
    assert extracted["R0"] == 0
    assert extracted["R1"] == 15
    assert extracted["R2"] == 42
    assert extracted["R3"] == 99


def test_extract_json_dict_with_wrapper():
    output = """
    ```json
    {
      "final_registers": {
        "R0": 0,
        "R1": 15
      }
    }
    ```
    """
    extracted = extract_json_dict(output, target_keys=["R0", "R1"])
    assert extracted is not None
    assert extracted.get("R0") == 0
    assert extracted.get("R1") == 15


def test_extract_json_dict_with_trailing_comma_and_comments():
    output = """
    Here is the final state:
    ```json
    {
      "Flux": 12, // final flux
      "Chrono": 7,
      "Aether": 0, // decayed
      "Entropy": 15,
    }
    ```
    """
    extracted = extract_json_dict(output, target_keys=["Flux", "Chrono", "Aether", "Entropy"])
    assert extracted is not None
    assert extracted["Flux"] == 12
    assert extracted["Chrono"] == 7
    assert extracted["Aether"] == 0
    assert extracted["Entropy"] == 15


def test_extract_key_value_assignments_text_fallback():
    # Plain text without any JSON code block
    output = """
    Tracing complete. The final register values are:
    - R0 = 0
    - R1: 15
    - R2 is 42
    - R3 -> 99
    """
    target_keys = ["R0", "R1", "R2", "R3"]
    extracted = extract_key_value_assignments(output, target_keys)
    assert extracted is not None
    assert extracted["R0"] == 0
    assert extracted["R1"] == 15
    assert extracted["R2"] == 42
    assert extracted["R3"] == 99


def test_extract_key_value_assignments_markdown_table():
    # Markdown table format
    output = """
    | Register | Final Value |
    | :--- | :--- |
    | R0 | 0 |
    | R1 | 15 |
    | R2 | 42 |
    | R3 | 99 |
    """
    target_keys = ["R0", "R1", "R2", "R3"]
    extracted = extract_key_value_assignments(output, target_keys)
    assert extracted is not None
    assert extracted["R0"] == 0
    assert extracted["R1"] == 15
    assert extracted["R2"] == 42
    assert extracted["R3"] == 99


def test_extract_key_value_assignments_takes_last_occurrence():
    # Intermediate steps vs final answer
    output = """
    Cycle 1: R0 = 4, R1 = 2
    Cycle 2: R0 = 3, R1 = 5
    Cycle 3: R0 = 0, R1 = 15
    """
    extracted = extract_key_value_assignments(output, ["R0", "R1"])
    assert extracted is not None
    assert extracted["R0"] == 0
    assert extracted["R1"] == 15
