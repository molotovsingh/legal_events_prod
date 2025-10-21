"""
Configuration module for Docling and LangExtract settings
Provides strongly-typed configuration with environment variable overrides
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Literal, Tuple, Any

from .constants import DEFAULT_MODEL


# Helper functions for environment variable parsing
def env_bool(var_name: str, default: bool) -> bool:
    """Parse environment variable as boolean"""
    value = os.getenv(var_name)
    if value is None:
        return default
    return value.lower() in ('true', '1', 'yes', 'on')


def env_int(var_name: str, default: int) -> int:
    """Parse environment variable as integer"""
    value = os.getenv(var_name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_float(var_name: str, default: float) -> float:
    """Parse environment variable as float"""
    value = os.getenv(var_name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def env_str(var_name: str, default: str) -> str:
    """Parse environment variable as string"""
    return os.getenv(var_name, default)


def env_optional_str(var_name: str) -> Optional[str]:
    """Parse environment variable as optional string"""
    value = os.getenv(var_name)
    return value if value else None


@dataclass
class DoclingConfig:
    """Configuration for Docling document processing"""

    # OCR and processing options
    do_ocr: bool = field(default_factory=lambda: env_bool("DOCLING_DO_OCR", True))
    auto_ocr_detection: bool = field(default_factory=lambda: env_bool("DOCLING_AUTO_OCR_DETECTION", True))
    ocr_engine: Literal["tesseract", "easyocr", "ocrmac", "rapidocr"] = field(
        default_factory=lambda: env_str("DOCLING_OCR_ENGINE", "tesseract")
    )
    do_table_structure: bool = field(default_factory=lambda: env_bool("DOCLING_DO_TABLE_STRUCTURE", True))
    table_mode: Literal["FAST", "ACCURATE"] = field(default_factory=lambda: env_str("DOCLING_TABLE_MODE", "FAST"))
    do_cell_matching: bool = field(default_factory=lambda: env_bool("DOCLING_DO_CELL_MATCHING", True))

    # Backend and acceleration
    backend: Literal["default", "v2"] = field(default_factory=lambda: env_str("DOCLING_BACKEND", "default"))
    accelerator_device: Literal["cuda", "mps", "cpu"] = field(default_factory=lambda: env_str("DOCLING_ACCELERATOR_DEVICE", "cpu"))
    accelerator_threads: int = field(default_factory=lambda: env_int("DOCLING_ACCELERATOR_THREADS", 4))

    # Paths and timeouts
    artifacts_path: Optional[str] = field(default_factory=lambda: env_optional_str("DOCLING_ARTIFACTS_PATH"))
    document_timeout: int = field(default_factory=lambda: env_int("DOCLING_DOCUMENT_TIMEOUT", 300))


@dataclass
class LangExtractConfig:
    """Configuration for LangExtract operations

    Default model: gemini-2.0-flash (fast, budget-friendly)
    Premium models available for ground truth creation:
    - gemini-2.5-pro: Google's most intelligent AI model (Jun 2025), 2M context window for long documents
    """

    # Model and API settings
    model_id: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL_ID", DEFAULT_MODEL))
    temperature: float = field(default_factory=lambda: env_float("LANGEXTRACT_TEMPERATURE", 0.0))
    max_workers: int = field(default_factory=lambda: env_int("LANGEXTRACT_MAX_WORKERS", 10))
    debug: bool = field(default_factory=lambda: env_bool("LANGEXTRACT_DEBUG", False))


@dataclass
class OpenRouterConfig:
    """Configuration for OpenRouter API operations

    Supports runtime model override for per-request model selection.
    The active_model property returns runtime_model if set, otherwise falls back to env default.

    Default model: openai/gpt-oss-120b (OSS, Apache 2.0, self-hostable)
    """

    # API settings
    api_key: str = field(default_factory=lambda: env_str("OPENROUTER_API_KEY", ""))
    base_url: str = field(default_factory=lambda: env_str("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    model: str = field(default_factory=lambda: env_str("OPENROUTER_MODEL", "openai/gpt-oss-120b"))  # OSS default
    timeout: int = field(default_factory=lambda: env_int("OPENROUTER_TIMEOUT", 30))

    # Runtime model override (set by UI, takes precedence over env var)
    runtime_model: Optional[str] = None

    @property
    def active_model(self) -> str:
        """Return the active model: runtime override if set, else env default"""
        return self.runtime_model or self.model


@dataclass
class OpenCodeZenConfig:
    """Configuration for OpenCode Zen API operations"""

    # API settings
    api_key: str = field(default_factory=lambda: env_str("OPENCODEZEN_API_KEY", ""))
    base_url: str = field(default_factory=lambda: env_str("OPENCODEZEN_BASE_URL", "https://api.opencode-zen.example/v1"))
    model: str = field(default_factory=lambda: env_str("OPENCODEZEN_MODEL", "opencode-zen/legal-extractor"))
    timeout: int = field(default_factory=lambda: env_int("OPENCODEZEN_TIMEOUT", 30))


@dataclass
class OpenAIConfig:
    """Configuration for OpenAI API operations

    Default model: gpt-4o-mini (budget option)
    Premium models available for ground truth creation:
    - gpt-5: Latest flagship model (Aug 2025), best for coding and reasoning
    - gpt-5-mini: Smaller variant of GPT-5
    - gpt-4o: Previous flagship model
    """

    # API settings
    api_key: str = field(default_factory=lambda: env_str("OPENAI_API_KEY", ""))
    base_url: str = field(default_factory=lambda: env_str("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    model: str = field(default_factory=lambda: env_str("OPENAI_MODEL", "gpt-4o-mini"))
    timeout: int = field(default_factory=lambda: env_int("OPENAI_TIMEOUT", 60))


@dataclass
class AnthropicConfig:
    """Configuration for Anthropic API operations

    Default model: claude-3-haiku-20240307 (budget option)
    Premium models available for ground truth creation:
    - claude-sonnet-4-5: "Best coding model in the world" (Sep 2025), recommended for ground truth
    - claude-opus-4: Highest quality model (May 2025), best for complex reasoning
    - claude-opus-4-1: Enhanced version (Aug 2025)
    - claude-3-5-sonnet-20241022: Quality baseline from Claude 3.5 series
    """

    # API settings
    api_key: str = field(default_factory=lambda: env_str("ANTHROPIC_API_KEY", ""))
    base_url: str = field(default_factory=lambda: env_str("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
    model: str = field(default_factory=lambda: env_str("ANTHROPIC_MODEL", "claude-3-haiku-20240307"))
    timeout: int = field(default_factory=lambda: env_int("ANTHROPIC_TIMEOUT", 60))


@dataclass
class DeepSeekConfig:
    """Configuration for DeepSeek API operations"""

    # API settings
    api_key: str = field(default_factory=lambda: env_str("DEEPSEEK_API_KEY", ""))
    base_url: str = field(default_factory=lambda: env_str("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))
    model: str = field(default_factory=lambda: env_str("DEEPSEEK_MODEL", "deepseek-chat"))
    timeout: int = field(default_factory=lambda: env_int("DEEPSEEK_TIMEOUT", 180))


@dataclass
class GeminiEventConfig:
    """Configuration for direct Google Gemini API event extraction

    Alternative to LangExtract for simple chat-completion style extraction.
    Uses google-generativeai SDK with native JSON mode.

    Default model: gemini-2.0-flash (free tier, 1M context)
    Ground truth option: gemini-2.5-pro (2M context, pending release)
    """

    # API settings
    api_key: str = field(default_factory=lambda: env_str("GEMINI_API_KEY", ""))
    model_id: str = field(default_factory=lambda: env_str("GEMINI_MODEL_ID", "gemini-2.0-flash"))
    temperature: float = 0.0
    max_output_tokens: int = 8192


@dataclass
class ExtractorConfig:
    """Configuration for extractor selection

    Defaults:
    - Document extractor: docling (local OCR, free, fast)
    - Event extractor: openrouter (OSS models, flexible, self-hostable)
    """

    # Extractor type selection
    doc_extractor: str = None
    event_extractor: str = None

    def __post_init__(self):
        """Initialize fields with environment variables after instance creation"""
        if self.doc_extractor is None:
            self.doc_extractor = env_str("DOC_EXTRACTOR", "docling")
        if self.event_extractor is None:
            self.event_extractor = env_str("EVENT_EXTRACTOR", "openrouter")  # OSS default


def load_config() -> Tuple[DoclingConfig, LangExtractConfig, ExtractorConfig]:
    """
    Load configuration for Docling, LangExtract, and extractor selection

    Returns:
        Tuple of (DoclingConfig, LangExtractConfig, ExtractorConfig) instances
    """
    docling_config = DoclingConfig()
    langextract_config = LangExtractConfig()
    extractor_config = ExtractorConfig()

    return docling_config, langextract_config, extractor_config


def load_provider_config(
    provider: str,
    docling_config: Optional[DoclingConfig] = None,
    extractor_config: Optional[ExtractorConfig] = None,
    runtime_model: Optional[str] = None
) -> Tuple[DoclingConfig, Any, ExtractorConfig]:
    """Load configuration with provider-specific event extractor config.

    Args:
        provider: Event extractor provider type.
        docling_config: Optional pre-loaded Docling configuration instance.
        extractor_config: Optional extractor configuration instance to update.
        runtime_model: Optional runtime model override (for OpenRouter multi-model selection).

    Returns:
        Tuple of (DoclingConfig, provider_specific_config, ExtractorConfig) instances.
    """
    docling_config = docling_config or DoclingConfig()
    extractor_config = extractor_config or ExtractorConfig()

    provider_key = (provider or extractor_config.event_extractor or "langextract").strip().lower()
    extractor_config.event_extractor = provider_key

    if provider_key == "openrouter":
        event_config = OpenRouterConfig()
        # Set runtime model override if provided (UI selection takes precedence over env var)
        if runtime_model:
            event_config.runtime_model = runtime_model
    elif provider_key == "opencode_zen":
        event_config = OpenCodeZenConfig()
    elif provider_key == "openai":
        event_config = OpenAIConfig()
        # Apply runtime model override for ground truth model selection
        if runtime_model:
            event_config.model = runtime_model
    elif provider_key == "anthropic":
        event_config = AnthropicConfig()
        # Apply runtime model override for ground truth model selection
        if runtime_model:
            event_config.model = runtime_model
    elif provider_key == "deepseek":
        event_config = DeepSeekConfig()
        # Apply runtime model override if needed
        if runtime_model:
            event_config.model = runtime_model
    elif provider_key == "google":
        event_config = GeminiEventConfig()
        # Apply runtime model override for Gemini model selection
        if runtime_model:
            event_config.model_id = runtime_model
    else:
        # Default to langextract (unified Gemini provider)

        # Adapter switching logic for unified Gemini provider:
        # - If runtime_model is a direct Gemini model ID → use GeminiEventExtractor (simple API)
        # - If runtime_model is "langextract" or None → use LangExtractEventExtractor (structured)
        direct_gemini_models = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]

        if runtime_model in direct_gemini_models:
            # Switch to direct Google Gemini adapter for simple API access
            event_config = GeminiEventConfig()
            event_config.model_id = runtime_model
            extractor_config.event_extractor = "google"
        else:
            # Use LangExtract adapter for structured few-shot extraction
            event_config = LangExtractConfig()
            # If runtime_model=="langextract", use default model (gemini-2.5-flash)
            # Otherwise, apply the runtime_model override (for backward compatibility)
            if runtime_model and runtime_model != "langextract":
                event_config.model_id = runtime_model
            extractor_config.event_extractor = "langextract"

    return docling_config, event_config, extractor_config
