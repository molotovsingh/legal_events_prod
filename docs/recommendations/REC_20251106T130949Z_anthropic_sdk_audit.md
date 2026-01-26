# Recommendation — Anthropic SDK: Tool/JSON Reliability

Date: 2025-11-06
Timestamp: 20251106T130949Z (UTC)

## Summary
Audit `core/anthropic_adapter.py` to force JSON outputs via tool use, prevent unintended tool calls, enforce ordering, and pin SDK version.

## Steps
- Define JSON schema as a tool; set tool_choice to force JSON.
- When returning results, set tool_choice {"type": "none"}.
- Ensure tool_result blocks precede text; parse from tool_use.input.
- Pin anthropic SDK version; add tests.

## Validation
- Consistent JSON across docs; adapter tests pass.
