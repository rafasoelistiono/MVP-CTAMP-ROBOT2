import pytest

from task_planning.generator import PlanGenerationError, parse_llm_json


def test_parse_llm_json_accepts_plain_object():
    assert parse_llm_json('{"status":"UNSAT","reason":"blocked"}') == {
        "status": "UNSAT",
        "reason": "blocked",
    }


def test_parse_llm_json_tolerates_fence_but_returns_only_json():
    assert parse_llm_json('```json\n{"status":"UNSAT"}\n```')["status"] == "UNSAT"


def test_parse_llm_json_rejects_non_json():
    with pytest.raises(PlanGenerationError, match="not valid JSON"):
        parse_llm_json("move cube1")
