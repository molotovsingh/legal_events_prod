"""
DeepSeek Event Extractor Adapter
Wraps DeepSeek API to implement EventExtractor interface with native JSON mode support
Uses OpenAI-compatible SDK since DeepSeek API follows OpenAI specification
"""

import json
import logging
import time
from typing import List, Dict, Any, Optional

from .interfaces import EventExtractor, EventRecord
from .config import DeepSeekConfig
from .constants import DEFAULT_NO_DATE, DEFAULT_NO_CITATION, LEGAL_EVENTS_PROMPT

logger = logging.getLogger(__name__)


# DeepSeek models that support native JSON mode
JSON_MODE_COMPATIBLE_MODELS = [
    "deepseek-chat",
    "deepseek-coder",
]


class DeepSeekEventExtractor:
    """Adapter that wraps DeepSeek API to implement EventExtractor interface"""

    def __init__(self, config: DeepSeekConfig):
        """
        Initialize with DeepSeek configuration

        Args:
            config: DeepSeekConfig instance with all DeepSeek settings

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
                "DeepSeek API key is required. Set DEEPSEEK_API_KEY environment variable."
            )

        # Validate model supports JSON mode
        self._supports_json_mode = self._check_json_mode_support(config.model)
        if not self._supports_json_mode:
            logger.warning(
                f"⚠️ Model {config.model} may not support native JSON mode. "
                f"Compatible models: {', '.join(JSON_MODE_COMPATIBLE_MODELS)}"
            )

        # Lazy import OpenAI client (DeepSeek API is OpenAI-compatible)
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout,
            )
            self.available = True
            logger.info(f"✅ DeepSeekEventExtractor initialized with model: {config.model}")
        except ImportError:
            logger.warning("⚠️ openai library not available - DeepSeek adapter will be disabled")
            self.available = False
        except Exception as e:
            logger.error(f"❌ Failed to initialize DeepSeek client: {e}")
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

    def extract_events(self, text: str, metadata: Dict[str, Any]) -> List[EventRecord]:
        """
        Extract legal events using DeepSeek API

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
            logger.warning("⚠️ DeepSeek adapter not available - creating fallback record")
            return [self._create_fallback_record(document_name, "DeepSeek client not available")]

        if not text or not text.strip():
            logger.warning(f"⚠️ No text provided for {document_name} - creating fallback record")
            return [self._create_fallback_record(document_name, "No text content to process")]

        try:
            # Call DeepSeek API with retry logic
            response_data = self._call_deepseek_api_with_retry(text)

            if not response_data:
                logger.error(f"❌ DeepSeek API returned empty response for {document_name}")
                return [self._create_fallback_record(document_name, "DeepSeek API returned empty response")]

            # Parse the response and extract legal events
            events = self._parse_deepseek_response(response_data, document_name)

            if not events:
                logger.warning(f"⚠️ No events extracted from DeepSeek response for {document_name}")
                return [self._create_fallback_record(document_name, "No legal events found in response")]

            logger.info(
                f"✅ Extracted {len(events)} legal events from {document_name} via DeepSeek "
                f"(tokens: {self._total_tokens}, cost: ${self._total_cost:.4f})"
            )
            return events

        except Exception as e:
            logger.error(f"❌ DeepSeekEventExtractor failed for {document_name}: {e}")
            return [self._create_fallback_record(document_name, f"DeepSeek processing error: {str(e)}")]

    def _call_deepseek_api_with_retry(
        self,
        text: str,
        max_retries: int = 3,
        initial_delay: float = 2.0
    ) -> Optional[Dict[str, Any]]:
        """
        Make API call to DeepSeek with exponential backoff retry logic
        DeepSeek uses dynamic rate limiting - no fixed RPM, but slows down under load

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
                return self._call_deepseek_api(text)

            except RateLimitError as e:
                if attempt < max_retries:
                    logger.warning(
                        f"⚠️ DeepSeek dynamic rate limit hit (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error(f"❌ DeepSeek rate limit exceeded after {max_retries + 1} attempts: {e}")
                    return None

            except OpenAIError as e:
                logger.error(f"❌ DeepSeek API error: {e}")
                return None

            except Exception as e:
                logger.error(f"❌ Unexpected error calling DeepSeek API: {e}")
                return None

        return None

    def _call_deepseek_api(self, text: str) -> Dict[str, Any]:
        """
        Make API call to DeepSeek

        Args:
            text: Document text to process

        Returns:
            API response data

        Raises:
            OpenAIError: On API errors
        """
        # Construct messages with legal events extraction prompt
        # Note: DeepSeek requires "json" keyword in prompt when using JSON mode
        messages = [
            {
                "role": "system",
                "content": LEGAL_EVENTS_PROMPT + "\n\nReturn your response as valid JSON array containing the extracted events."
            },
            {
                "role": "user",
                "content": f"Extract legal events from this document and return as JSON:\n\n{text}"
            }
        ]

        # Call DeepSeek API with JSON mode if supported
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.0,
        }

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

        # Convert response to dict for consistency
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

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost based on token usage for DeepSeek models

        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        # Pricing per 1M tokens (as of 2025-01)
        # Source: https://platform.deepseek.com/api-docs/pricing/
        pricing = {
            "deepseek-chat": (0.27, 1.10),  # $0.27/M input, $1.10/M output
            "deepseek-coder": (0.27, 1.10),  # Same pricing as chat
        }

        # Find matching pricing
        model_lower = self.config.model.lower()
        input_price, output_price = (0.27, 1.10)  # Default to deepseek-chat

        for model_key, prices in pricing.items():
            if model_key in model_lower:
                input_price, output_price = prices
                break

        # Calculate cost
        input_cost = (prompt_tokens / 1_000_000) * input_price
        output_cost = (completion_tokens / 1_000_000) * output_price

        return input_cost + output_cost

    def _parse_deepseek_response(self, response_data: Dict[str, Any], document_name: str) -> List[EventRecord]:
        """
        Parse DeepSeek API response and convert to EventRecord instances

        Args:
            response_data: Response from DeepSeek API
            document_name: Source document name

        Returns:
            List of EventRecord instances
        """
        try:
            # Extract the content from response
            choices = response_data.get("choices", [])
            if not choices:
                logger.warning("⚠️ No choices in DeepSeek response")
                return []

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                logger.warning("⚠️ No content in DeepSeek response")
                return []

            # Parse JSON content
            try:
                events_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Failed to parse JSON from DeepSeek response: {e}")
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

                # Create EventRecord with DeepSeek-specific attributes
                attributes = {
                    "provider": "deepseek",
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
            logger.error(f"❌ Failed to parse DeepSeek response: {e}")
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
            event_particulars=f"Failed to extract legal events from {document_name} using DeepSeek: {reason}",
            citation="No citation available (extraction failed)",
            document_reference=document_name,
            attributes={
                "provider": "deepseek",
                "fallback": True,
                "reason": reason
            }
        )

    def is_available(self) -> bool:
        """
        Check if DeepSeek is properly configured and available

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
