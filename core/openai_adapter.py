"""
OpenAI Event Extractor Adapter
Wraps OpenAI API to implement EventExtractor interface with native JSON mode support
"""

import json
import logging
import time
from typing import List, Dict, Any, Optional

from .interfaces import EventExtractor, EventRecord
from .config import OpenAIConfig
from .constants import DEFAULT_NO_DATE, DEFAULT_NO_CITATION, LEGAL_EVENTS_PROMPT

logger = logging.getLogger(__name__)


# Models that support native JSON mode (response_format)
JSON_MODE_COMPATIBLE_MODELS = [
    "gpt-5",           # GPT-5 series (Aug 2025)
    "gpt-4o",          # GPT-4o series
    "gpt-4-turbo",
    "gpt-4-1106-preview",
    "gpt-4-0125-preview",
    "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo-0125",
]

# GPT-5 models use new API parameters (max_completion_tokens, temperature=1.0)
GPT5_MODELS = [
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5-pro",
    "gpt-5-2025-08-07",
    "gpt-5-mini-2025-08-07",
    "gpt-5-nano-2025-08-07",
    "gpt-5-pro-2025-10-06",
    "gpt-5-chat-latest",
    "gpt-5-codex",
]


class OpenAIEventExtractor:
    """Adapter that wraps OpenAI API to implement EventExtractor interface"""

    def __init__(self, config: OpenAIConfig):
        """
        Initialize with OpenAI configuration

        Args:
            config: OpenAIConfig instance with all OpenAI settings

        Raises:
            ExtractorConfigurationError: If required configuration is missing
        """
        from .extractor_factory import ExtractorConfigurationError

        self.config = config
        self._client = None
        self._total_tokens = 0
        self._total_cost = 0.0

        # Validate API key at initialization
        if not config.api_key or config.api_key.strip() == "":
            raise ExtractorConfigurationError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable."
            )

        # Validate model supports JSON mode
        self._supports_json_mode = self._check_json_mode_support(config.model)
        self._is_gpt5 = self._check_gpt5_model(config.model)
        self._uses_responses_api = self._supports_reasoning_api(config.model)

        if not self._supports_json_mode:
            logger.warning(
                f"⚠️ Model {config.model} may not support native JSON mode. "
                f"Compatible models: {', '.join(JSON_MODE_COMPATIBLE_MODELS[:3])}..."
            )

        if self._uses_responses_api:
            logger.info(
                f"🧠 Model {config.model} will use Responses API for advanced reasoning. "
                f"Outputs are non-deterministic (temperature=1.0)."
            )
        elif self._is_gpt5:
            logger.info(
                f"✅ GPT-5 model detected: {config.model}. "
                f"Using Chat Completions with max_completion_tokens and temperature=1.0"
            )

        # Lazy import OpenAI client
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout,
            )
            self.available = True
            logger.info(f"✅ OpenAIEventExtractor initialized with model: {config.model}")
        except ImportError:
            logger.warning("⚠️ openai library not available - OpenAI adapter will be disabled")
            self.available = False
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI client: {e}")
            self.available = False

    def _check_json_mode_support(self, model: str) -> bool:
        """
        Check if the model supports native JSON mode

        Args:
            model: Model identifier

        Returns:
            True if model supports response_format=json_object
        """
        model_lower = model.lower()
        return any(compatible in model_lower for compatible in JSON_MODE_COMPATIBLE_MODELS)

    def _check_gpt5_model(self, model: str) -> bool:
        """
        Check if the model is a GPT-5 variant

        Args:
            model: Model identifier

        Returns:
            True if model is GPT-5 (requires special API parameters)
        """
        model_lower = model.lower()
        return any(gpt5_model in model_lower for gpt5_model in GPT5_MODELS)

    def _supports_reasoning_api(self, model: str) -> bool:
        """
        Check if model should use Responses API for advanced reasoning

        OpenAI's GPT-5 models use the Responses API for complex agentic/reasoning
        tasks. This API provides better reasoning capabilities compared to Chat
        Completions for tasks like legal event extraction.

        Args:
            model: Model identifier

        Returns:
            True if model should use Responses API (GPT-5 variants)
        """
        # GPT-5 models benefit from Responses API for reasoning tasks
        return self._check_gpt5_model(model)

    def extract_events(self, text: str, metadata: Dict[str, Any]) -> List[EventRecord]:
        """
        Extract legal events using OpenAI API

        Args:
            text: Document text content
            metadata: Document metadata including source filename

        Returns:
            List of EventRecord instances (guaranteed at least one)
        """
        # Extract document name from metadata
        document_name = metadata.get("document_name", metadata.get("file_path", "Unknown document"))
        if isinstance(document_name, str) and "/" in document_name:
            document_name = document_name.split("/")[-1]  # Get filename only

        if not self.available:
            logger.warning("⚠️ OpenAI adapter not available - creating fallback record")
            return [self._create_fallback_record(document_name, "OpenAI client not available")]

        if not text or not text.strip():
            logger.warning(f"⚠️ No text provided for {document_name} - creating fallback record")
            return [self._create_fallback_record(document_name, "No text content to process")]

        try:
            # Call OpenAI API with retry logic
            response_data = self._call_openai_api_with_retry(text)

            if not response_data:
                logger.error(f"❌ OpenAI API returned empty response for {document_name}")
                return [self._create_fallback_record(document_name, "OpenAI API returned empty response")]

            # Parse the response and extract legal events
            events = self._parse_openai_response(response_data, document_name)

            if not events:
                logger.warning(f"⚠️ No events extracted from OpenAI response for {document_name}")
                return [self._create_fallback_record(document_name, "No legal events found in response")]

            logger.info(
                f"✅ Extracted {len(events)} legal events from {document_name} via OpenAI "
                f"(tokens: {self._total_tokens}, cost: ${self._total_cost:.4f})"
            )
            return events

        except Exception as e:
            logger.error(f"❌ OpenAIEventExtractor failed for {document_name}: {e}")
            return [self._create_fallback_record(document_name, f"OpenAI processing error: {str(e)}")]

    def _call_openai_api_with_retry(
        self,
        text: str,
        max_retries: int = 3,
        initial_delay: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Make API call to OpenAI with exponential backoff retry logic

        Routes to appropriate API based on model:
        - GPT-5: Responses API (for advanced reasoning)
        - Others: Chat Completions API

        Args:
            text: Document text to process
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds before first retry

        Returns:
            API response data or None on failure
        """
        from openai import OpenAIError, RateLimitError

        delay = initial_delay

        for attempt in range(max_retries + 1):
            try:
                # Route to appropriate API based on model type
                if self._uses_responses_api:
                    logger.info(f"🧠 Using Responses API for reasoning model: {self.config.model}")
                    return self._call_responses_api(text)
                else:
                    return self._call_openai_api(text)

            except RateLimitError as e:
                if attempt < max_retries:
                    logger.warning(f"⚠️ Rate limit hit (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error(f"❌ Rate limit exceeded after {max_retries + 1} attempts: {e}")
                    return None

            except OpenAIError as e:
                logger.error(f"❌ OpenAI API error: {e}")
                return None

            except Exception as e:
                logger.error(f"❌ Unexpected error calling OpenAI API: {e}")
                return None

        return None

    def _call_openai_api(self, text: str) -> Dict[str, Any]:
        """
        Make API call to OpenAI

        Args:
            text: Document text to process

        Returns:
            API response data

        Raises:
            OpenAIError: On API errors
        """
        # Construct messages with legal events extraction prompt
        messages = [
            {
                "role": "system",
                "content": LEGAL_EVENTS_PROMPT + "\n\nReturn your response as valid JSON array containing the extracted events."
            },
            {
                "role": "user",
                "content": f"Extract legal events from this document:\n\n{text}"
            }
        ]

        # Call OpenAI API with JSON mode if supported
        # GPT-5 requires different parameters than GPT-4
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 1.0 if self._is_gpt5 else 0.0,
        }

        # GPT-5 uses max_completion_tokens, GPT-4 uses max_tokens
        if self._is_gpt5:
            kwargs["max_completion_tokens"] = 4096  # GPT-5 default for legal extraction
        else:
            kwargs["max_tokens"] = 4096  # GPT-4 default for legal extraction

        if self._supports_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self._client.chat.completions.create(**kwargs)

        # Track token usage and costs
        if hasattr(response, "usage"):
            self._total_tokens += response.usage.total_tokens
            self._total_cost += self._calculate_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens
            )

        # Convert response to dict for consistency with OpenRouter adapter
        return {
            "choices": [
                {
                    "message": {
                        "content": response.choices[0].message.content
                    }
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if hasattr(response, "usage") else 0,
                "completion_tokens": response.usage.completion_tokens if hasattr(response, "usage") else 0,
                "total_tokens": response.usage.total_tokens if hasattr(response, "usage") else 0,
            }
        }

    def _call_responses_api(self, text: str) -> Dict[str, Any]:
        """
        Call OpenAI Responses API for GPT-5 reasoning models

        The Responses API is designed for advanced reasoning and agentic tasks,
        providing better performance for complex extractions like legal events.

        Args:
            text: Document text to process

        Returns:
            API response data in standardized format

        Raises:
            OpenAIError: On API errors

        Reference:
            https://platform.openai.com/docs/guides/reasoning
            https://platform.openai.com/docs/guides/latest-model
        """
        # Combine system prompt and user input into single input string
        # Responses API uses 'input' parameter instead of 'messages' array
        input_text = (
            f"{LEGAL_EVENTS_PROMPT}\n\n"
            f"Return your response as valid JSON array containing the extracted events.\n\n"
            f"Extract legal events from this document:\n\n{text}"
        )

        # Call OpenAI Responses API with reasoning parameters
        response = self._client.responses.create(
            model=self.config.model,
            input=input_text,
            reasoning={"effort": "medium"},  # low, medium, high, or ultra
            text={"verbosity": "medium"},     # low, medium, or high
        )

        # Track token usage and costs (Responses API has reasoning tokens)
        if hasattr(response, "usage"):
            reasoning_tokens = getattr(response.usage, "reasoning_tokens", 0)
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = reasoning_tokens + input_tokens + output_tokens

            self._total_tokens += total_tokens
            self._total_cost += self._calculate_cost_with_reasoning(
                input_tokens,
                output_tokens,
                reasoning_tokens
            )

            # Log reasoning token usage for cost transparency
            logger.info(
                f"📊 GPT-5 Responses API tokens: "
                f"reasoning={reasoning_tokens:,}, "
                f"input={input_tokens:,}, "
                f"output={output_tokens:,}, "
                f"total={total_tokens:,}"
            )

            if reasoning_tokens > 0:
                logger.info(
                    f"ℹ️  GPT-5 uses non-deterministic reasoning (temperature=1.0) - "
                    f"outputs will vary between runs"
                )

        # Convert Responses API format to standardized format
        # Responses API returns output_text directly (not in choices structure)
        return {
            "choices": [
                {
                    "message": {
                        "content": response.output_text
                    }
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.input_tokens if hasattr(response, "usage") else 0,
                "completion_tokens": response.usage.output_tokens if hasattr(response, "usage") else 0,
                "reasoning_tokens": getattr(response.usage, "reasoning_tokens", 0) if hasattr(response, "usage") else 0,
                "total_tokens": (
                    response.usage.input_tokens +
                    response.usage.output_tokens +
                    getattr(response.usage, "reasoning_tokens", 0)
                ) if hasattr(response, "usage") else 0,
            }
        }

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost based on token usage

        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        # Pricing per 1M tokens (as of 2025-01, GPT-5 pricing TBD - estimated based on GPT-4o)
        pricing = {
            "gpt-5": (3.00, 12.00),      # GPT-5 series (estimated, pending official pricing)
            "gpt-4o": (2.50, 10.00),
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-4-turbo": (10.00, 30.00),
            "gpt-3.5-turbo": (0.50, 1.50),
        }

        # Find matching pricing
        model_lower = self.config.model.lower()
        input_price, output_price = (0.15, 0.60)  # Default to gpt-4o-mini

        for model_key, prices in pricing.items():
            if model_key in model_lower:
                input_price, output_price = prices
                break

        # Calculate cost
        input_cost = (prompt_tokens / 1_000_000) * input_price
        output_cost = (completion_tokens / 1_000_000) * output_price

        return input_cost + output_cost

    def _calculate_cost_with_reasoning(
        self,
        input_tokens: int,
        output_tokens: int,
        reasoning_tokens: int
    ) -> float:
        """
        Calculate cost including reasoning tokens (for Responses API)

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            reasoning_tokens: Number of reasoning tokens

        Returns:
            Estimated cost in USD
        """
        # Pricing per 1M tokens (reasoning tokens typically cost same as input tokens)
        pricing = {
            "gpt-5": (3.00, 12.00),      # GPT-5 series (estimated)
            "gpt-4o": (2.50, 10.00),
            "gpt-4o-mini": (0.15, 0.60),
        }

        # Find matching pricing
        model_lower = self.config.model.lower()
        input_price, output_price = (0.15, 0.60)  # Default to gpt-4o-mini

        for model_key, prices in pricing.items():
            if model_key in model_lower:
                input_price, output_price = prices
                break

        # Calculate cost (reasoning tokens priced same as input tokens)
        input_cost = ((input_tokens + reasoning_tokens) / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price

        return input_cost + output_cost

    def _parse_openai_response(self, response_data: Dict[str, Any], document_name: str) -> List[EventRecord]:
        """
        Parse OpenAI API response and convert to EventRecord instances

        Args:
            response_data: Response from OpenAI API
            document_name: Source document name

        Returns:
            List of EventRecord instances
        """
        try:
            # Extract the content from response
            choices = response_data.get("choices", [])
            if not choices:
                logger.warning("⚠️ No choices in OpenAI response")
                return []

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                logger.warning("⚠️ No content in OpenAI response")
                return []

            # Parse JSON content
            try:
                events_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Failed to parse JSON from OpenAI response: {e}")
                # If JSON mode wasn't used, try to extract JSON from markdown code blocks
                if "```json" in content:
                    try:
                        json_start = content.find("```json") + 7
                        json_end = content.find("```", json_start)
                        json_str = content[json_start:json_end].strip()
                        events_data = json.loads(json_str)
                    except (json.JSONDecodeError, ValueError):
                        return []
                else:
                    return []

            # Handle both array and object responses
            if isinstance(events_data, dict):
                # If response is an object, look for events in common keys
                if "events" in events_data:
                    events_data = events_data["events"]
                elif "extractions" in events_data:
                    events_data = events_data["extractions"]
                else:
                    # Single event object
                    events_data = [events_data]

            if not isinstance(events_data, list):
                logger.warning("⚠️ Events data is not a list")
                return []

            # Convert to EventRecord instances
            event_records = []
            for i, event_data in enumerate(events_data, 1):
                if not isinstance(event_data, dict):
                    continue

                # Extract required fields with defaults
                event_particulars = event_data.get("event_particulars", "")
                if not event_particulars:
                    continue  # Skip events without particulars

                # Create EventRecord with OpenAI-specific attributes
                attributes = {
                    "provider": "openai",
                    "model": self.config.model,
                    "original_response": event_data,
                    "tokens": response_data.get("usage", {}).get("total_tokens", 0),
                    "cost": self._total_cost,
                }

                event_record = EventRecord(
                    number=i,
                    date=event_data.get("date", DEFAULT_NO_DATE),
                    event_particulars=event_particulars,
                    citation=event_data.get("citation", DEFAULT_NO_CITATION),
                    document_reference=document_name,
                    attributes=attributes
                )
                event_records.append(event_record)

            return event_records

        except Exception as e:
            logger.error(f"❌ Failed to parse OpenAI response: {e}")
            return []

    def _create_fallback_record(self, document_name: str, reason: str) -> EventRecord:
        """
        Create a fallback EventRecord when extraction fails

        Args:
            document_name: Source document name
            reason: Reason for fallback

        Returns:
            EventRecord with fallback content
        """
        return EventRecord(
            number=1,
            date=DEFAULT_NO_DATE,
            event_particulars=f"Failed to extract legal events from {document_name} using OpenAI: {reason}",
            citation="No citation available (extraction failed)",
            document_reference=document_name,
            attributes={
                "provider": "openai",
                "fallback": True,
                "reason": reason
            }
        )

    def is_available(self) -> bool:
        """
        Check if OpenAI is properly configured and available

        Returns:
            True if extractor can be used, False otherwise
        """
        return (
            self.available and
            self._client is not None and
            self.config.api_key and
            self.config.api_key.strip() != ""
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics

        Returns:
            Dictionary with total tokens and cost
        """
        return {
            "total_tokens": self._total_tokens,
            "total_cost": self._total_cost,
            "model": self.config.model,
            "supports_json_mode": self._supports_json_mode,
        }
