"""Tests for head_to_head agent judge output parsing.

These tests exercise the private helper that extracts JSON decisions from
chatty agent stdout logs.
"""

import json

from long_context_bench.stages.head_to_head import _parse_agent_judge_output


def test_parse_pure_json():
    stdout = '{"winner": "A", "rationale": "ok"}'
    parsed = _parse_agent_judge_output(stdout)
    assert parsed["winner"] == "A"
    assert parsed["rationale"] == "ok"


def test_parse_json_code_block_with_context():
    stdout = """
Tool output and analysis...
```json
{
  "winner": "B",
  "rationale": "B is better",
  "raw_scores": {
    "A": {"correctness": 0.0},
    "B": {"correctness": 1.0}
  }
}
```
More trailing commentary.
"""
    parsed = _parse_agent_judge_output(stdout)
    assert parsed["winner"] == "B"
    assert parsed["raw_scores"]["B"]["correctness"] == 1.0


def test_parse_auggie_like_transcript_multiple_code_blocks():
    """Simulate an Auggie log with tool calls plus a final JSON block.

    Earlier code blocks (diffs, code excerpts) must not confuse the parser.
    """

    stdout = """
\ud83d\udd27 Tool call: view
... (many lines of tool output omitted) ...
```diff
- old line
+ new line
```
\ud83e\udd16 Now let me compare submissions...
```json
{
  "winner": "A",
  "correctness_preference": "A",
  "completeness_preference": "A",
  "code_quality_preference": "A",
  "integration_preference": "A",
  "rationale": "A is clearly better",
  "raw_scores": {
    "A": {"correctness": 7.0, "completeness": 3.0, "code_quality": 8.0, "integration": 6.0},
    "B": {"correctness": 0.0, "completeness": 0.0, "code_quality": 0.0, "integration": 0.0}
  }
}
```
"""
    parsed = _parse_agent_judge_output(stdout)
    assert parsed["winner"] == "A"
    assert parsed["raw_scores"]["A"]["correctness"] == 7.0


def test_parse_multiple_json_objects_extra_data():
    """Simulate a factory log where two JSON objects appear back-to-back.

    The parser should successfully extract the first valid object instead of
    raising a JSON Extra data error.
    """

    stdout = """
Some leading text
```json
{"winner": "A", "rationale": "first"}
{"winner": "B", "rationale": "second"}
```
Trailing notes.
"""
    parsed = _parse_agent_judge_output(stdout)
    assert parsed["winner"] == "A"
    assert parsed["rationale"] == "first"


def test_parse_stream_json_with_embedded_code_block():
    """Stream-json stdout with a final result field containing a JSON block.

    This simulates the claude-code CLI --output-format stream-json behavior
    where the actual judge decision is embedded as a ```json code block inside
    the ``result`` text of the final event.
    """

    system = {"type": "system", "subtype": "init"}

    result_text = (
        "I'll analyze both submissions.\n\n"
        "```json\n"
        "{\n"
        "  \"winner\": \"B\",\n"
        "  \"correctness_preference\": \"B\",\n"
        "  \"completeness_preference\": \"B\",\n"
        "  \"code_reuse_preference\": \"B\",\n"
        "  \"best_practices_preference\": \"B\",\n"
        "  \"unsolicited_docs_preference\": \"tie\",\n"
        "  \"rationale\": \"human diff is clearly better\",\n"
        "  \"raw_scores\": {\n"
        "    \"A\": {\n"
        "      \"correctness\": -0.3,\n"
        "      \"completeness\": -0.5,\n"
        "      \"code_reuse\": 0.0,\n"
        "      \"best_practices\": -0.4,\n"
        "      \"unsolicited_docs\": 0.0\n"
        "    },\n"
        "    \"B\": {\n"
        "      \"correctness\": 1.0,\n"
        "      \"completeness\": 1.0,\n"
        "      \"code_reuse\": 0.9,\n"
        "      \"best_practices\": 1.0,\n"
        "      \"unsolicited_docs\": 0.0\n"
        "    }\n"
        "  }\n"
        "}\n"
        "```\n"
    )

    result = {"type": "result", "subtype": "success", "result": result_text}

    stdout = json.dumps(system) + "\n" + json.dumps(result)

    parsed = _parse_agent_judge_output(stdout)
    assert parsed["winner"] == "B"
    assert parsed["raw_scores"]["A"]["correctness"] == -0.3
    assert parsed["raw_scores"]["B"]["correctness"] == 1.0

