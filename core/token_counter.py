"""
Token counting utilities for accurate cost estimation.

Supports provider/model-specific tokenizers. For GPT-family models (OpenAI/OpenRouter),
uses tiktoken. For Llama models, expects a HuggingFace tokenizer. For Anthropic (Claude),
expects the anthropic tokenizer. These imports are optional at runtime: if a tokenizer
is not available for a selected model, a NotImplementedError is raised rather than
falling back to approximations.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple, Any
import re


class TokenizerUnavailable(Exception):
    """Raised when a tokenizer for the provider/model is not available."""


def _resolve_gpt_encoding(model_id: str) -> str:
    """Select tiktoken encoding by model id.

    Defaults to cl100k_base; uses o200k_base for GPT-4o family.
    """
    m = model_id.lower()
    if "4o" in m:
        return "o200k_base"
    return "cl100k_base"


def _get_gpt_tokenizer(model_id: str) -> Callable[[str], int]:
    try:
        import tiktoken  # type: ignore
    except Exception as e:
        raise TokenizerUnavailable(
            "tiktoken is required for GPT-family models. Add 'tiktoken' to requirements and install."
        ) from e

    encoding_name = _resolve_gpt_encoding(model_id)
    enc = tiktoken.get_encoding(encoding_name)
    def _count(text: str) -> int:
        return len(enc.encode(text or ""))
    return _count


def _get_llama_tokenizer(model_id: str) -> Callable[[str], int]:
    """Return a counting function for Llama models via transformers.

    Note: Requires local availability of the tokenizer files or auto-download capability.
    """
    try:
        from transformers import AutoTokenizer  # type: ignore
    except Exception as e:
        raise TokenizerUnavailable(
            "transformers is required for Llama models. Add 'transformers' and 'sentencepiece' to requirements."
        ) from e

    # Use a canonical Llama tokenizer id when model_id is an OpenRouter alias
    pretrained_id = "meta-llama/Meta-Llama-3.1-8B"
    tok = AutoTokenizer.from_pretrained(pretrained_id, use_fast=True)
    def _count(text: str) -> int:
        return len(tok.encode(text or ""))
    return _count


def _get_claude_tokenizer(model_id: str) -> Callable[[str], int]:
    try:
        from anthropic_tokenizer import get_tokenizer  # type: ignore
    except Exception as e:
        raise TokenizerUnavailable(
            "anthropic-tokenizer is required for Claude models. Add 'anthropic-tokenizer' to requirements."
        ) from e

    tok = get_tokenizer()
    def _count(text: str) -> int:
        return tok.count_tokens(text or "")
    return _count


def resolve_tokenizer(provider: str, model_id: str) -> Callable[[str], int]:
    """Resolve a tokenizer function for the given provider/model.

    Returns a callable that takes a string and returns token count.
    Raises TokenizerUnavailable if unsupported.
    """
    p = (provider or "").lower()
    m = (model_id or "").lower()

    # GPT-family via OpenRouter/OpenAI
    if p in ("openai", "openrouter") and ("gpt" in m or m.startswith("openai/")):
        return _get_gpt_tokenizer(model_id)

    # Llama family via OpenRouter
    if p in ("openrouter",) and ("llama" in m or m.startswith("meta-llama/")):
        return _get_llama_tokenizer(model_id)

    # Anthropic Claude
    if p in ("anthropic", "openrouter") and ("claude" in m or m.startswith("anthropic/")):
        return _get_claude_tokenizer(model_id)

    raise TokenizerUnavailable(f"No tokenizer mapping for provider='{provider}' model='{model_id}'")


def count_text(text: str, provider: str, model_id: str) -> int:
    """Count tokens in plain text using provider/model-specific tokenizer."""
    fn = resolve_tokenizer(provider, model_id)
    return fn(text or "")


def count_messages(messages: List[Dict[str, Any]], provider: str, model_id: str) -> int:
    """Count tokens for a chat-style messages array.

    For now, we conservatively sum token counts of concatenated contents.
    (Exact per-role overhead can be added later per-model if needed.)
    """
    fn = resolve_tokenizer(provider, model_id)
    total = 0
    for msg in messages or []:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += fn(content)
        elif isinstance(content, list):
            # OpenAI-style content parts: [{"type":"text","text":"..."}, ...]
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += fn(part.get("text", ""))
        # role/system markers can include fixed overhead in future if desired
    return total

