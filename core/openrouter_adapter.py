"""
OpenRouter Event Extractor Adapter
Wraps OpenRouter API to implement EventExtractor interface
"""

import json
import logging
from typing import List, Dict, Any, Optional

from openai import OpenAI

from .interfaces import EventExtractor, EventRecord
from .config import OpenRouterConfig
from .constants import DEFAULT_NO_DATE, DEFAULT_NO_CITATION, LEGAL_EVENTS_PROMPT

logger = logging.getLogger(__name__)


# Models that support native JSON mode (response_format parameter)
# Based on OpenRouter provider support and Oct 2025 testing
JSON_MODE_COMPATIBLE_MODELS = [
    "openai/gpt-4o",
    "openai/gpt-4",
    "openai/gpt-3.5-turbo",
    "anthropic/claude-3",
    "anthropic/claude-4",
    "deepseek/deepseek-chat",
    "deepseek/deepseek-r1",
    "meta-llama/llama-3.3-70b-instruct",
    "meta-llama/llama-3.1-405b-instruct",
    "mistralai/mistral-large",
    "mistralai/mistral-small",
]


class OpenRouterEventExtractor:
    """Adapter that wraps OpenRouter API to implement EventExtractor interface"""

    def __init__(self, config: OpenRouterConfig):
        """
        Initialize with OpenRouter configuration

        Args:
            config: OpenRouterConfig instance with all OpenRouter settings

        Raises:
            ExtractorConfigurationError: If required configuration is missing
        """
        from .extractor_factory import ExtractorConfigurationError

        self.config = config
        self._client = None

        # Validate API key at initialization
        if not config.api_key or config.api_key.strip() == "":
            raise ExtractorConfigurationError(
                "OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable."
            )

        # Check if model supports native JSON mode
        self._supports_json_mode = self._check_json_mode_support(config.active_model)
        if not self._supports_json_mode:
            logger.info(
                f"ℹ️  Model {config.active_model} will use prompt-based JSON (no native response_format support). "
                f"This is normal for many OSS models."
            )

        # Initialize OpenAI SDK client (pointed at OpenRouter base_url)
        try:
            self._client = OpenAI(
                base_url=config.base_url,
                api_key=config.api_key,
                timeout=config.timeout
            )
            self.available = True

            # Log which model is being used (runtime override or env default)
            active_model = config.active_model
            if config.runtime_model:
                logger.info(f"✅ OpenRouterEventExtractor initialized with runtime model: {active_model} (overriding env default: {config.model})")
            else:
                logger.info(f"✅ OpenRouterEventExtractor initialized with model: {active_model}")
        except Exception as e:
            logger.warning(f"⚠️ OpenAI SDK not available - OpenRouter adapter will be disabled: {e}")
            self.available = False

    def _check_json_mode_support(self, model: str) -> bool:
        """
        Check if the model supports native JSON mode (response_format parameter)

        Args:
            model: Model identifier (e.g., "openai/gpt-4o-mini")

        Returns:
            True if model supports response_format=json_object via OpenRouter
        """
        model_lower = model.lower()
        return any(compatible in model_lower for compatible in JSON_MODE_COMPATIBLE_MODELS)

    def extract_events(self, text: str, metadata: Dict[str, Any]) -> List[EventRecord]:
        """
        Extract legal events using OpenRouter API

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
            logger.warning("⚠️ OpenRouter adapter not available - creating fallback record")
            return [self._create_fallback_record(document_name, "OpenRouter HTTP client not available")]

        if not text or not text.strip():
            logger.warning(f"⚠️ No text provided for {document_name} - creating fallback record")
            return [self._create_fallback_record(document_name, "No text content to process")]

        try:
            # Call OpenRouter Chat Completions API
            response_data = self._call_openrouter_api(text)

            if not response_data:
                logger.error(f"❌ OpenRouter API returned empty response for {document_name}")
                return [self._create_fallback_record(document_name, "OpenRouter API returned empty response")]

            # Parse the response and extract legal events
            events = self._parse_openrouter_response(response_data, document_name)

            if not events:
                logger.warning(f"⚠️ No events extracted from OpenRouter response for {document_name}")
                return [self._create_fallback_record(document_name, "No legal events found in response")]

            logger.info(f"✅ Extracted {len(events)} legal events from {document_name} via OpenRouter")
            return events

        except Exception as e:
            logger.error(f"❌ OpenRouterEventExtractor failed for {document_name}: {e}")
            return [self._create_fallback_record(document_name, f"OpenRouter processing error: {str(e)}")]

    def _call_openrouter_api(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Make API call to OpenRouter using OpenAI SDK

        Args:
            text: Document text to process

        Returns:
            API response data or None on failure
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

        try:
            # Build request parameters
            params = {
                "model": self.config.active_model,  # Use active_model (runtime override or env default)
                "messages": messages,
                "temperature": 0.0,
            }

            # Only add response_format if model supports it (otherwise rely on prompt-based JSON)
            if self._supports_json_mode:
                params["response_format"] = {"type": "json_object"}

            # OpenAI SDK handles retries, connection pooling, error handling
            response = self._client.chat.completions.create(**params)

            # Convert SDK response to dict format (same structure as before for compatibility)
            return {
                "choices": [
                    {
                        "message": {
                            "content": response.choices[0].message.content
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }

        except Exception as e:
            logger.error(f"❌ OpenRouter API request failed: {e}")
            return None

    def _parse_openrouter_response(self, response_data: Dict[str, Any], document_name: str) -> List[EventRecord]:
        """
        Parse OpenRouter API response and convert to EventRecord instances

        Args:
            response_data: Response from OpenRouter API
            document_name: Source document name

        Returns:
            List of EventRecord instances
        """
        try:
            # Extract the content from OpenAI-format response
            choices = response_data.get("choices", [])
            if not choices:
                logger.warning("⚠️ No choices in OpenRouter response")
                return []

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                logger.warning("⚠️ No content in OpenRouter response")
                return []

            # Log first 500 chars of raw response for debugging
            logger.info(f"📝 OpenRouter raw response preview: {content[:500]}...")

            # Strip markdown code block wrappers if present (common in prompt-based JSON)
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            elif content.startswith("```"):
                content = content[3:]  # Remove ```
            if content.endswith("```"):
                content = content[:-3]  # Remove closing ```
            content = content.strip()

            # Parse JSON content
            try:
                events_data = json.loads(content)
            except json.JSONDecodeError as json_err:
                logger.warning(f"⚠️ Failed to parse JSON from OpenRouter response: {json_err}")
                logger.info(f"📝 Unparseable content (first 300 chars): {content[:300]}")

                # Try fallback parsing before giving up
                fallback_events = self._fallback_event_parser(content, document_name)
                if fallback_events:
                    return fallback_events

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
                    logger.info(f"ℹ️  Skipping event #{i} - missing event_particulars. Keys present: {list(event_data.keys())}")
                    continue  # Skip events without particulars

                # Create EventRecord with OpenRouter-specific attributes
                attributes = {
                    "provider": "openrouter",
                    "model": self.config.active_model,  # Use active_model (runtime override or env default)
                    "original_response": event_data
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
            logger.error(f"❌ Failed to parse OpenRouter response: {e}")
            return []

    def _fallback_event_parser(self, content: str, document_name: str) -> List[EventRecord]:
        """
        Attempt alternative parsing strategies when primary JSON parsing fails

        Handles:
        - Non-JSON responses (plain text descriptions)
        - Markdown-formatted responses
        - Partial JSON responses buried in text

        Args:
            content: Raw response content from OpenRouter
            document_name: Source document name

        Returns:
            List of EventRecord instances (may be empty if all strategies fail)
        """
        import re

        logger.info("🔄 Attempting fallback parsing strategies...")

        # Strategy 1: Look for JSON anywhere in the response (even if wrapped in text)
        json_match = re.search(r'\{.*\}|\[.*\]', content, re.DOTALL)
        if json_match:
            try:
                events_data = json.loads(json_match.group(0))
                logger.info("✅ Fallback: Found JSON via regex extraction")

                # Reuse existing logic for handling dict/list responses
                if isinstance(events_data, dict):
                    if "events" in events_data:
                        events_data = events_data["events"]
                    elif "extractions" in events_data:
                        events_data = events_data["extractions"]
                    else:
                        events_data = [events_data]

                if isinstance(events_data, list):
                    # Try to convert to EventRecords
                    event_records = []
                    for i, event_data in enumerate(events_data, 1):
                        if isinstance(event_data, dict) and event_data.get("event_particulars"):
                            attributes = {
                                "provider": "openrouter",
                                "model": self.config.active_model,
                                "parsing_strategy": "fallback_regex_json",
                                "original_response": event_data
                            }
                            event_record = EventRecord(
                                number=i,
                                date=event_data.get("date", DEFAULT_NO_DATE),
                                event_particulars=event_data.get("event_particulars"),
                                citation=event_data.get("citation", DEFAULT_NO_CITATION),
                                document_reference=document_name,
                                attributes=attributes
                            )
                            event_records.append(event_record)

                    if event_records:
                        logger.info(f"✅ Fallback extracted {len(event_records)} events via regex JSON")
                        return event_records
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.info(f"ℹ️  Regex JSON strategy failed: {e}")

        # Strategy 2: Parse as plain text and create single event from response
        logger.warning("⚠️ All parsing strategies failed - creating single event from response text")
        truncated_content = content[:500] if len(content) > 500 else content

        return [EventRecord(
            number=1,
            date=DEFAULT_NO_DATE,
            event_particulars=f"OpenRouter response (non-standard format): {truncated_content}",
            citation=DEFAULT_NO_CITATION,
            document_reference=document_name,
            attributes={
                "provider": "openrouter",
                "model": self.config.active_model,
                "parsing_strategy": "fallback_text_extraction",
                "original_content_length": len(content)
            }
        )]

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
            event_particulars=f"Failed to extract legal events from {document_name} using OpenRouter: {reason}",
            citation="No citation available (extraction failed)",
            document_reference=document_name,
            attributes={
                "provider": "openrouter",
                "fallback": True,
                "reason": reason
            }
        )

    def is_available(self) -> bool:
        """
        Check if OpenRouter is properly configured and available

        Returns:
            True if extractor can be used, False otherwise
        """
        return (
            self.available and
            self._client is not None and
            self.config.api_key and
            self.config.api_key.strip() != ""
        )