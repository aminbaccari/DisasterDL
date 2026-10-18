"""Unit tests for lenient JSON extraction from VLM text responses."""

import json
import pytest

from src.llm.json_utils import parse_json_lenient


def test_parse_clean_json():
    result = parse_json_lenient('{"class": "fire", "description": "x", "evidence": []}')
    assert result == {"class": "fire", "description": "x", "evidence": []}


def test_parse_json_with_markdown_fence():
    text = '```json\n{"class": "flood", "description": "y", "evidence": ["water"]}\n```'
    result = parse_json_lenient(text)
    assert result["class"] == "flood"


def test_parse_json_with_plain_fence_no_lang():
    text = '```\n{"class": "normal", "description": "z", "evidence": []}\n```'
    result = parse_json_lenient(text)
    assert result["class"] == "normal"


def test_parse_json_with_surrounding_prose():
    text = 'Here is the result: {"class": "fire", "description": "x", "evidence": []} Hope that helps!'
    result = parse_json_lenient(text)
    assert result["class"] == "fire"


def test_parse_json_with_leading_trailing_whitespace():
    result = parse_json_lenient('  \n  {"class": "normal", "description": "x", "evidence": []}  \n ')
    assert result["class"] == "normal"


def test_parse_invalid_json_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_json_lenient("this is not json at all")


def test_parse_nested_json_object():
    text = '{"class": "fire", "description": "x", "evidence": ["a", "b"], "meta": {"k": 1}}'
    result = parse_json_lenient(text)
    assert result["meta"]["k"] == 1
