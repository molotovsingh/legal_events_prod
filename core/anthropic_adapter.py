"""
Anthropic Event Extractor Adapter
Wraps Anthropic API to implement EventExtractor interface using tool calling for JSON output
"""

import json
import logging
import time
from typing import List, Dict, Any, Optional

from .interfaces import EventExtractor, EventRecord
from .config import AnthropicConfig
from .constants import DEFAULT_NO_DATE, DEFAULT_NO_CITATION, LEGAL_EVENTS_PROMPT

logger = logging.getLogger(__name__)


class AnthropicEventExtractor:
    """Adapter that wraps Anthropic API to implement EventExtractor interface"""

    def __init__(self, config: AnthropicConfig):
        """
        Initialize with Anthropic configuration

        Args:
            config: AnthropicConfig instance with all Anthropic settings

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
                "Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable."
            )

        # Lazy import Anthropic client
        try:
            from anthropic import Anthropic
            self._client = Anthropic(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout,
            )
            self.available = True
            logger.info(f"✅ AnthropicEventExtractor initialized with model: {config.model}")
        except ImportError:
            logger.warning("⚠️ anthropic library not available - Anthropic adapter will be disabled")
            self.available = False
        except Exception as e:
            logger.error(f"❌ Failed to initialize Anthropic client: {e}")
            self.available = False

    def extract_events(self, text: str, metadata: Dict[str, Any]) -> List[EventRecord]:
        """
        Extract legal events using Anthropic API with tool calling

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
            logger.warning("⚠️ Anthropic adapter not available - creating fallback record")
            return [self._create_fallback_record(document_name, "Anthropic client not available")]

        if not text or not text.strip():
            logger.warning(f"⚠️ No text provided for {document_name} - creating fallback record")
            return [self._create_fallback_record(document_name, "No text content to process")]

        try:
            # Call Anthropic API with retry logic
            response_data = self._call_anthropic_api_with_retry(text)

            if not response_data:
                logger.error(f"❌ Anthropic API returned empty response for {document_name}")
                return [self._create_fallback_record(document_name, "Anthropic API returned empty response")]

            # Parse the response and extract legal events
            events = self._parse_anthropic_response(response_data, document_name)

            if not events:
                logger.warning(f"⚠️ No events extracted from Anthropic response for {document_name}")
                return [self._create_fallback_record(document_name, "No legal events found in response")]

            logger.info(
                f"✅ Extracted {len(events)} legal events from {document_name} via Anthropic "
                f"(tokens: {self._total_tokens}, cost: ${self._total_cost:.4f})"
            )
            return events

        except Exception as e:
            logger.error(f"❌ AnthropicEventExtractor failed for {document_name}: {e}")
            return [self._create_fallback_record(document_name, f"Anthropic processing error: {str(e)}")]

    def _call_anthropic_api_with_retry(
        self,
        text: str,
        max_retries: int = 3,
        initial_delay: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Make API call to Anthropic with exponential backoff retry logic

        Args:
            text: Document text to process
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds before first retry

        Returns:
            API response data or None on failure
        """
        from anthropic import APIError, RateLimitError

        delay = initial_delay

        for attempt in range(max_retries + 1):
            try:
                return self._call_anthropic_api(text)

            except RateLimitError as e:
                if attempt < max_retries:
                    logger.warning(f"⚠️ Rate limit hit (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error(f"❌ Rate limit exceeded after {max_retries + 1} attempts: {e}")
                    return None

            except APIError as e:
                logger.error(f"❌ Anthropic API error: {e}")
                return None

            except Exception as e:
                logger.error(f"❌ Unexpected error calling Anthropic API: {e}")
                return None

        return None

    def _call_anthropic_api(self, text: str) -> Dict[str, Any]:
        """
        Make API call to Anthropic using tool calling for structured output

        Args:
            text: Document text to process

        Returns:
            API response data

        Raises:
            APIError: On API errors
        """
        # Define tool for legal events extraction
        # Anthropic uses tools to enforce JSON structure
        tools = [{
            "name": "extract_legal_events",
            "description": "Extract legal events from a document with dates, event details, and citations",
            "input_schema": {
                "type": "object",
                "properties": {
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "event_particulars": {
                                    "type": "string",
                                    "description": "Complete 2-8 sentence description with legal context"
                                },
                                "citation": {
                                    "type": "string",
                                    "description": "Legal reference or empty string (NO hallucinations)"
                                },
                                "document_reference": {
                                    "type": "string",
                                    "description": "Source filename (will be auto-populated)"
                                },
                                "date": {
                                    "type": "string",
                                    "description": "Specific date or empty string"
                                }
                            },
                            "required": ["event_particulars", "citation", "document_reference", "date"]
                        }
                    }
                },
                "required": ["events"]
            }
        }]

        # Construct messages with legal events extraction prompt
        messages = [
            {
                "role": "user",
                "content": f"{LEGAL_EVENTS_PROMPT}\n\nExtract legal events from this document:\n\n{text}"
            }
        ]

        # Call Anthropic API with tool choice to force tool use
        response = self._client.messages.create(
            model=self.config.model,
            max_tokens=4096,
            temperature=0.0,
            tools=tools,
            tool_choice={"type": "tool", "name": "extract_legal_events"},
            messages=messages
        )

        # Track token usage and costs
        if hasattr(response, "usage"):
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            self._total_tokens += (input_tokens + output_tokens)
            self._total_cost += self._calculate_cost(input_tokens, output_tokens)

        # Convert response to dict for consistency
        return {
            "content": response.content,
            "usage": {
                "input_tokens": response.usage.input_tokens if hasattr(response, "usage") else 0,
                "output_tokens": response.usage.output_tokens if hasattr(response, "usage") else 0,
            },
            "stop_reason": response.stop_reason,
        }

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost based on token usage

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        # Pricing per 1M tokens (as of 2025-01, Claude 4 series pricing from Anthropic)
        pricing = {
            # Claude 4 series (2025)
            "claude-sonnet-4-5": (3.00, 15.00),   # Claude Sonnet 4.5 (Sep 2025)
            "claude-opus-4": (15.00, 75.00),      # Claude Opus 4 (May 2025)
            # Claude 3 series (2024)
            "claude-3-5-sonnet": (3.00, 15.00),
            "claude-3-opus": (15.00, 75.00),
            "claude-3-sonnet": (3.00, 15.00),
            "claude-3-haiku": (0.25, 1.25),
        }

        # Find matching pricing
        model_lower = self.config.model.lower()
        input_price, output_price = (0.25, 1.25)  # Default to Haiku

        for model_key, prices in pricing.items():
            if model_key in model_lower:
                input_price, output_price = prices
                break

        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price

        return input_cost + output_cost

    def _parse_anthropic_response(self, response_data: Dict[str, Any], document_name: str) -> List[EventRecord]:
        """
        Parse Anthropic API response and convert to EventRecord list

        Args:
            response_data: API response data
            document_name: Source document name

        Returns:
            List of EventRecord instances
        """
        try:
            # Extract tool use from response content
            content = response_data.get("content", [])

            # Find tool use block
            tool_use_block = None
            for block in content:
                if hasattr(block, "type") and block.type == "tool_use":
                    tool_use_block = block
                    break

            if not tool_use_block:
                logger.error("❌ No tool_use block found in Anthropic response")
                return []

            # Extract events from tool input
            tool_input = tool_use_block.input
            events_data = tool_input.get("events", [])

            if not events_data:
                logger.warning("⚠️ No events in tool input")
                return []

            # Convert to EventRecord instances
            event_records = []
            for idx, event_data in enumerate(events_data, 1):
                event_record = EventRecord(
                    number=idx,
                    date=event_data.get("date", DEFAULT_NO_DATE) or DEFAULT_NO_DATE,
                    event_particulars=event_data.get("event_particulars", ""),
                    citation=event_data.get("citation", DEFAULT_NO_CITATION) or DEFAULT_NO_CITATION,
                    document_reference=document_name,
                    attributes={
                        "provider": "anthropic",
                        "model": self.config.model,
                        "raw_data": event_data
                    }
                )
                event_records.append(event_record)

            return event_records

        except Exception as e:
            logger.error(f"❌ Error parsing Anthropic response: {e}")
            return []

    def _create_fallback_record(self, document_name: str, reason: str) -> EventRecord:
        """
        Create a fallback EventRecord when extraction fails

        Args:
            document_name: Source document name
            reason: Reason for fallback

        Returns:
            EventRecord with fallback data
        """
        return EventRecord(
            number=1,
            date=DEFAULT_NO_DATE,
            event_particulars=f"❌ Extraction failed: {reason}",
            citation=DEFAULT_NO_CITATION,
            document_reference=document_name,
            attributes={
                "fallback": True,
                "reason": reason,
                "provider": "anthropic"
            }
        )

    def is_available(self) -> bool:
        """
        Check if the extractor is properly configured and available

        Returns:
            True if extractor can be used, False otherwise
        """
        return self.available
