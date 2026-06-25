"""Tolerant JSON extraction for LLM responses that may wrap JSON in prose or code fences."""
import json
import re


def parse_json_response(text, default=None):
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        brace_match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass
    return default
