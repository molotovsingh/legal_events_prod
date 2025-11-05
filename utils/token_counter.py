"""
Token Counter - Exact token counting using OpenAI's tiktoken library

This module provides precise token counting for all supported LLM models.
After Docling extraction (free), use tiktoken to get exact token counts
before making expensive API calls to Gemini, OpenAI, Claude, or DeepSeek.

Architecture:
- MODEL_TO_ENCODING: Maps model IDs to tiktoken encoding names
- count_tokens(): Count tokens for a single text string
- count_tokens_batch(): Sum tokens across multiple documents
- estimate_output_tokens(): Estimate output size based on task type

Precision:
- OpenAI models (gpt-4o, gpt-4o-mini): ±0% error (exact tokenization)
- Other models (Claude, Gemini, Llama): ±2-5% error (approximation with cl100k_base)
"""

import tiktoken
from typing import List, Optional

# ============================================================================
# MODEL → ENCODING MAPPING
# ============================================================================
# Maps each supported model ID to its tiktoken encoding
# o200k_base: GPT-4o, GPT-4o-mini, GPT-5 (OpenAI models)
# cl100k_base: GPT-4, GPT-3.5, Claude (approximate), Gemini (approximate), others

MODEL_TO_ENCODING = {
    # === OpenAI: Direct API (o200k_base) ===
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-5": "o200k_base",

    # === OpenAI: OpenRouter proxy (o200k_base for gpt-, cl100k for others) ===
    "openai/gpt-4o-mini": "o200k_base",
    "openai/gpt-oss-120b": "cl100k_base",  # Open-source GPT, not native OpenAI

    # === Anthropic: Claude models (cl100k_base approximate) ===
    "claude-3-haiku-20240307": "cl100k_base",
    "claude-sonnet-4-5": "cl100k_base",
    "claude-opus-4": "cl100k_base",

    # === Google: Gemini models (cl100k_base approximate) ===
    "gemini-2.0-flash": "cl100k_base",
    "gemini-2.5-flash": "cl100k_base",
    "gemini-2.5-pro": "cl100k_base",

    # === Google via OpenRouter (same encodings) ===
    "google/gemini-2.0-flash": "cl100k_base",
    "google/gemini-2.5-pro": "cl100k_base",
    "google/gemini-2.5-flash": "cl100k_base",

    # === DeepSeek: Direct API (cl100k_base approximate) ===
    "deepseek-chat": "cl100k_base",

    # === DeepSeek via OpenRouter (cl100k_base approximate) ===
    "deepseek/deepseek-r1-distill-llama-70b": "cl100k_base",

    # === Open Source via OpenRouter (cl100k_base approximate) ===
    "meta-llama/llama-3.3-70b-instruct": "cl100k_base",
    "qwen/qwq-32b": "cl100k_base",
    "mistralai/mistral-large-2411": "cl100k_base",
}

# Default encoding if model not in map
DEFAULT_ENCODING = "cl100k_base"

# ============================================================================
# OUTPUT TOKEN ESTIMATION RATIOS
# ============================================================================
# Based on observed patterns from event extraction tasks
# Input text is extracted legal document, output is JSON with events

OUTPUT_RATIOS = {
    "event_extraction": 0.10,  # Events are ~10% of input size (conservative estimate)
    "summarization": 0.05,     # Summary is ~5% of input size
    "chat": 0.20,              # Chat responses are ~20% of input size
}

# ============================================================================
# PUBLIC FUNCTIONS
# ============================================================================


def count_tokens(text: str, model_id: str) -> int:
    """
    Count exact tokens for a model using tiktoken.

    Args:
        text: Input text to tokenize
        model_id: Model identifier (e.g., 'gpt-4o', 'claude-sonnet-4-5')

    Returns:
        Number of tokens in the text

    Raises:
        ValueError: If model_id not supported
        RuntimeError: If tiktoken fails to count

    Example:
        >>> tokens = count_tokens("Hello world", "gpt-4o")
        >>> print(f"Input tokens: {tokens}")
        Input tokens: 2
    """
    # Validate model_id is supported (do not silently fall back to DEFAULT_ENCODING)
    if model_id not in MODEL_TO_ENCODING:
        raise ValueError(
            f"Model '{model_id}' not supported for token counting. "
            f"Supported models: {', '.join(get_supported_models())}"
        )

    encoding_name = MODEL_TO_ENCODING[model_id]

    try:
        enc = tiktoken.get_encoding(encoding_name)
        return len(enc.encode(text))
    except Exception as e:
        raise RuntimeError(f"Failed to count tokens for model '{model_id}': {str(e)}") from e


def count_tokens_batch(texts: List[str], model_id: str) -> int:
    """
    Count total tokens across multiple documents.

    Args:
        texts: List of text strings (e.g., extracted documents)
        model_id: Model identifier

    Returns:
        Total token count across all texts

    Example:
        >>> docs = ["First doc...", "Second doc..."]
        >>> total = count_tokens_batch(docs, "gpt-4o-mini")
        >>> print(f"Total: {total} tokens")
        Total: 1234 tokens
    """
    return sum(count_tokens(text, model_id) for text in texts)


def estimate_output_tokens(
    input_tokens: int,
    task: str = "event_extraction"
) -> int:
    """
    Estimate output token count based on task type and input size.

    For event extraction, output is typically 10% of input:
    - 8000 input tokens → ~800 output tokens (JSON events + metadata)

    Args:
        input_tokens: Number of input tokens
        task: Task type ('event_extraction', 'summarization', 'chat')

    Returns:
        Estimated output tokens

    Example:
        >>> input_tokens = 8000
        >>> output = estimate_output_tokens(input_tokens, "event_extraction")
        >>> print(f"Estimated output: {output} tokens")
        Estimated output: 800 tokens
    """
    ratio = OUTPUT_RATIOS.get(task, OUTPUT_RATIOS["event_extraction"])
    return int(input_tokens * ratio)


# ============================================================================
# UTILITY FUNCTIONS (For Testing & Diagnostics)
# ============================================================================


def get_encoding_for_model(model_id: str) -> str:
    """
    Get the tiktoken encoding name for a model.

    Args:
        model_id: Model identifier

    Returns:
        Encoding name (e.g., 'o200k_base', 'cl100k_base')
    """
    return MODEL_TO_ENCODING.get(model_id, DEFAULT_ENCODING)


def is_model_supported(model_id: str) -> bool:
    """
    Check if a model ID is supported for token counting.

    Args:
        model_id: Model identifier

    Returns:
        True if model has a mapping, False otherwise

    Example:
        >>> if is_model_supported("gpt-4o"):
        ...     tokens = count_tokens(text, "gpt-4o")
    """
    return model_id in MODEL_TO_ENCODING


def get_supported_models() -> List[str]:
    """
    Get list of all supported model IDs.

    Returns:
        List of model identifiers

    Example:
        >>> for model in get_supported_models():
        ...     print(model)
        gpt-4o
        gpt-4o-mini
        ...
    """
    return list(MODEL_TO_ENCODING.keys())


def validate_model_id(model_id: str, raise_on_missing: bool = False) -> bool:
    """
    Validate if a model_id is supported for token counting.

    Args:
        model_id: Model identifier to validate
        raise_on_missing: If True, raise exception if model not found

    Returns:
        True if model is supported

    Raises:
        ValueError: If raise_on_missing=True and model not supported
    """
    is_supported = is_model_supported(model_id)

    if not is_supported and raise_on_missing:
        raise ValueError(
            f"Model '{model_id}' not supported. "
            f"Supported models: {get_supported_models()}"
        )

    return is_supported


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example 1: Count tokens for a single text
    print("\n=== Example 1: Single Text Token Count ===")
    sample_text = """
    This is a legal document excerpt discussing contract terms.
    The agreement was signed on March 15, 2024 and becomes effective
    on April 1, 2024. The parties agree to the following terms...
    """ * 10  # Repeat to simulate longer document

    for model in ["gpt-4o", "claude-sonnet-4-5", "gpt-4o-mini"]:
        tokens = count_tokens(sample_text, model)
        print(f"{model}: {tokens} tokens")

    # Example 2: Batch counting across multiple documents
    print("\n=== Example 2: Batch Token Counting ===")
    documents = [sample_text, sample_text[:500], sample_text[:1000]]
    total_tokens = count_tokens_batch(documents, "gpt-4o")
    print(f"Total tokens across {len(documents)} documents: {total_tokens}")

    # Example 3: Estimate output tokens
    print("\n=== Example 3: Output Token Estimation ===")
    input_tokens = 8000
    output_tokens = estimate_output_tokens(input_tokens, "event_extraction")
    print(f"Input: {input_tokens} tokens")
    print(f"Estimated output: {output_tokens} tokens")
    print(f"Ratio: {output_tokens / input_tokens * 100:.1f}%")

    # Example 4: Check supported models
    print("\n=== Example 4: Supported Models ===")
    all_models = get_supported_models()
    print(f"Total supported models: {len(all_models)}")
    print(f"First 5 models: {all_models[:5]}")
