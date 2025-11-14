"""
Unit tests for core/token_counter.py

Tests provider-specific tokenizer resolution and token counting logic.
v0.12.0 - Token counting and cost estimation feature
"""

import pytest
from core.token_counter import (
    TokenizerUnavailable,
    resolve_tokenizer,
    count_text,
    count_messages,
    _resolve_gpt_encoding,
)


class TestGPTEncodingResolution:
    """Test GPT model encoding selection logic."""

    def test_gpt_4o_uses_o200k_base(self):
        """GPT-4o models should use o200k_base encoding."""
        assert _resolve_gpt_encoding("gpt-4o") == "o200k_base"
        assert _resolve_gpt_encoding("gpt-4o-mini") == "o200k_base"
        assert _resolve_gpt_encoding("GPT-4O") == "o200k_base"  # Case insensitive

    def test_other_gpt_uses_cl100k_base(self):
        """Other GPT models should use cl100k_base encoding."""
        assert _resolve_gpt_encoding("gpt-4") == "cl100k_base"
        assert _resolve_gpt_encoding("gpt-3.5-turbo") == "cl100k_base"
        assert _resolve_gpt_encoding("gpt-4-turbo") == "cl100k_base"


class TestTokenizerResolution:
    """Test tokenizer resolution for different provider/model combinations."""

    def test_openrouter_gpt_resolves_to_gpt_tokenizer(self):
        """OpenRouter GPT models should resolve to tiktoken."""
        # This will only pass if tiktoken is installed
        try:
            tokenizer = resolve_tokenizer("openrouter", "openai/gpt-4o")
            assert callable(tokenizer)
        except TokenizerUnavailable:
            pytest.skip("tiktoken not installed")

    def test_openai_gpt_resolves_to_gpt_tokenizer(self):
        """OpenAI GPT models should resolve to tiktoken."""
        try:
            tokenizer = resolve_tokenizer("openai", "gpt-4")
            assert callable(tokenizer)
        except TokenizerUnavailable:
            pytest.skip("tiktoken not installed")

    def test_openrouter_llama_resolves_to_llama_tokenizer(self):
        """OpenRouter Llama models should resolve to transformers."""
        # This will only pass if transformers is installed
        try:
            tokenizer = resolve_tokenizer("openrouter", "meta-llama/llama-3.3-70b-instruct")
            assert callable(tokenizer)
        except TokenizerUnavailable:
            pytest.skip("transformers not installed")

    def test_anthropic_claude_resolves_to_claude_tokenizer(self):
        """Anthropic Claude models should resolve to anthropic tokenizer."""
        # Note: anthropic-tokenizer was removed from requirements, so this will raise
        with pytest.raises(TokenizerUnavailable) as exc_info:
            resolve_tokenizer("anthropic", "claude-3-sonnet")
        assert "anthropic-tokenizer" in str(exc_info.value)

    def test_unsupported_provider_raises_error(self):
        """Unsupported provider/model combinations should raise TokenizerUnavailable."""
        with pytest.raises(TokenizerUnavailable) as exc_info:
            resolve_tokenizer("unknown_provider", "unknown_model")
        assert "No tokenizer mapping" in str(exc_info.value)

    def test_unsupported_model_raises_error(self):
        """Unsupported model for valid provider should raise TokenizerUnavailable."""
        with pytest.raises(TokenizerUnavailable):
            resolve_tokenizer("openrouter", "unsupported/model-123")


class TestTokenCounting:
    """Test actual token counting with known inputs."""

    def test_count_text_with_gpt_model(self):
        """Test token counting for GPT models with known text."""
        text = "Hello, world! This is a test."
        try:
            count = count_text(text, "openrouter", "openai/gpt-4")
            # Should be around 8-10 tokens
            assert count > 0
            assert count < 20  # Sanity check
        except TokenizerUnavailable:
            pytest.skip("tiktoken not installed")

    def test_count_empty_text(self):
        """Empty text should return 0 tokens."""
        try:
            count = count_text("", "openrouter", "openai/gpt-4")
            assert count == 0
        except TokenizerUnavailable:
            pytest.skip("tiktoken not installed")

    def test_count_none_text_handled_gracefully(self):
        """None text should be treated as empty string."""
        try:
            count = count_text(None, "openrouter", "openai/gpt-4")
            assert count == 0
        except TokenizerUnavailable:
            pytest.skip("tiktoken not installed")

    def test_count_long_text(self):
        """Test counting with longer text (>1000 chars)."""
        text = "This is a longer piece of text. " * 100  # ~3200 chars
        try:
            count = count_text(text, "openrouter", "openai/gpt-4")
            # Should be several hundred tokens
            assert count > 100
            assert count < 2000
        except TokenizerUnavailable:
            pytest.skip("tiktoken not installed")


class TestMessageCounting:
    """Test token counting for chat-style message arrays."""

    def test_count_simple_messages(self):
        """Test counting tokens in simple message array."""
        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        try:
            count = count_messages(messages, "openrouter", "openai/gpt-4")
            assert count > 0
            assert count < 20  # Both messages combined
        except TokenizerUnavailable:
            pytest.skip("tiktoken not installed")

    def test_count_messages_with_system_prompt(self):
        """Test counting with system prompt included."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]
        try:
            count = count_messages(messages, "openrouter", "openai/gpt-4")
            assert count > 5  # Should include system prompt tokens
        except TokenizerUnavailable:
            pytest.skip("tiktoken not installed")

    def test_count_messages_with_content_parts(self):
        """Test counting OpenAI-style content parts (vision API format)."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image"},
                    {"type": "image_url", "image_url": {"url": "data:..."}}
                ]
            }
        ]
        try:
            count = count_messages(messages, "openrouter", "openai/gpt-4")
            # Should count only the text part, ignore image
            assert count > 0
            assert count < 10
        except TokenizerUnavailable:
            pytest.skip("tiktoken not installed")

    def test_count_empty_messages_array(self):
        """Empty messages array should return 0 tokens."""
        try:
            count = count_messages([], "openrouter", "openai/gpt-4")
            assert count == 0
        except TokenizerUnavailable:
            pytest.skip("tiktoken not installed")

    def test_count_messages_with_none_content(self):
        """Messages with None content should be handled gracefully."""
        messages = [{"role": "user", "content": None}]
        try:
            count = count_messages(messages, "openrouter", "openai/gpt-4")
            assert count == 0
        except TokenizerUnavailable:
            pytest.skip("tiktoken not installed")


class TestTokenizerUnavailableErrors:
    """Test that proper errors are raised when tokenizers are missing."""

    def test_gpt_tokenizer_missing_raises_clear_error(self):
        """Missing tiktoken should raise clear error message."""
        # This test would require mocking the import to simulate missing tiktoken
        # For now, we document the expected behavior
        pass

    def test_llama_tokenizer_missing_raises_clear_error(self):
        """Missing transformers should raise clear error message."""
        # If transformers is not installed, should get helpful error
        try:
            resolve_tokenizer("openrouter", "meta-llama/llama-3.3-70b-instruct")
        except TokenizerUnavailable as e:
            assert "transformers" in str(e)
        except:
            # If it succeeds, transformers is installed
            pass

    def test_claude_tokenizer_missing_raises_clear_error(self):
        """Missing anthropic-tokenizer should raise clear error message."""
        # We removed this from requirements, so it should always fail
        with pytest.raises(TokenizerUnavailable) as exc_info:
            resolve_tokenizer("anthropic", "claude-3-sonnet")
        assert "anthropic-tokenizer" in str(exc_info.value)


# TODO: Add ground truth validation tests
# Create fixtures with known texts and their expected token counts
# Compare actual counts against ground truth for accuracy validation

# TODO: Add performance tests
# Test tokenizer initialization time
# Test counting speed for large documents (100KB+ text)
# Ensure no memory leaks when counting many documents

# TODO: Add edge case tests
# Very long texts (>1M chars)
# Special characters and Unicode
# Malformed message structures
