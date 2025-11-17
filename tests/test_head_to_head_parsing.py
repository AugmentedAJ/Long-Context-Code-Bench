"""Tests for head_to_head agent judge output parsing.

These tests exercise the private helper that extracts JSON decisions from
chatty agent stdout logs.
"""

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

