"""
Configuration module for Docling and LangExtract settings
Provides strongly-typed configuration with environment variable overrides
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Literal, Tuple, Any

from .constants import GEMINI_DEFAULT_MODEL


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
    model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", GEMINI_DEFAULT_MODEL))
    temperature: float = field(default_factory=lambda: env_float("LANGEXTRACT_TEMPERATURE", 0.0))
    max_workers: int = field(default_factory=lambda: env_int("LANGEXTRACT_MAX_WORKERS", 10))
    debug: bool = field(default_factory=lambda: env_bool("LANGEXTRACT_DEBUG", False))


@dataclass
class OpenRouterConfig:
    """Configuration for OpenRouter API operations

    Default model: meta-llama/llama-3.3-70b-instruct (standardized across system)
    Model can be overridden per-request by setting config.model before extraction.
    """

    # API settings
    api_key: str = field(default_factory=lambda: env_str("OPENROUTER_API_KEY", ""))
    base_url: str = field(default_factory=lambda: env_str("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    model: str = field(default_factory=lambda: env_str("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct"))
    timeout: int = field(default_factory=lambda: env_int("OPENROUTER_TIMEOUT", 30))


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
    model: str = field(default_factory=lambda: env_str("GEMINI_MODEL", "gemini-2.0-flash"))
    temperature: float = 0.0
    max_output_tokens: int = 8192


@dataclass
class RetryConfig:
    """Configuration for document retry mechanism

    Controls automatic and manual retry behavior for failed and stuck documents.

    Default stuck threshold: 1 hour
    Configurable via STUCK_DOCUMENT_HOURS environment variable

    Valid range: 1-72 hours
    """

    # Stuck document detection threshold (in hours)
    stuck_document_hours: int = field(default_factory=lambda: env_int("STUCK_DOCUMENT_HOURS", 1))

    # Future enhancements: max retry count, exponential backoff, etc.
    # max_retry_count: int = field(default_factory=lambda: env_int("MAX_RETRY_COUNT", 3))
    # retry_backoff_seconds: int = field(default_factory=lambda: env_int("RETRY_BACKOFF_SECONDS", 60))

    def __post_init__(self):
        """Validate configuration values on initialization"""
        if not 1 <= self.stuck_document_hours <= 72:
            raise ValueError(
                f"STUCK_DOCUMENT_HOURS must be between 1 and 72 hours (got {self.stuck_document_hours}). "
                f"This ensures reasonable retry intervals for stuck documents."
            )


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

    Simplified config loading with dictionary dispatch pattern.
    Removed magic provider swapping - caller specifies exact provider to use.

    Args:
        provider: Event extractor provider type (openrouter, openai, anthropic).
        docling_config: Optional pre-loaded Docling configuration instance.
        extractor_config: Optional extractor configuration instance to update.
        runtime_model: Optional runtime model override for per-request model selection.

    Returns:
        Tuple of (DoclingConfig, provider_specific_config, ExtractorConfig) instances.

    Raises:
        ValueError: If provider is unknown or not enabled.
    """
    docling_config = docling_config or DoclingConfig()
    extractor_config = extractor_config or ExtractorConfig()

    # Use openrouter as default (standardized across system)
    provider_key = (provider or extractor_config.event_extractor or "openrouter").strip().lower()
    extractor_config.event_extractor = provider_key

    # Dictionary dispatch: provider ID → config class
    config_registry = {
        "openrouter": OpenRouterConfig,
        "openai": OpenAIConfig,
        "anthropic": AnthropicConfig,
        "opencode_zen": OpenCodeZenConfig,
        "deepseek": DeepSeekConfig,
        "langextract": LangExtractConfig,
        "google": GeminiEventConfig,
    }

    # Get config class for provider
    config_class = config_registry.get(provider_key)
    if not config_class:
        raise ValueError(
            f"Unknown provider '{provider_key}'. "
            f"Supported providers: {', '.join(config_registry.keys())}"
        )

    # Instantiate config with defaults from environment
    event_config = config_class()

    # Apply runtime model override if provided (per-request model selection)
    if runtime_model:
        event_config.model = runtime_model

    return docling_config, event_config, extractor_config
