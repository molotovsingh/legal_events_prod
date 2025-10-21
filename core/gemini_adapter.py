"""
Google Gemini Event Extractor Adapter
Direct Gemini API adapter for event extraction (alternative to LangExtract)

This adapter provides direct access to Google's Gemini API using google-generativeai SDK.
Unlike LangExtract (which uses structured few-shot extraction), this uses simple chat completion
with JSON mode, similar to OpenAI/Anthropic adapters.
"""

import json
import logging
import time
from typing import List, Dict, Any, Optional

from .interfaces import EventExtractor, EventRecord
from .config import GeminiEventConfig
from .constants import DEFAULT_NO_DATE, DEFAULT_NO_CITATION, LEGAL_EVENTS_PROMPT

logger = logging.getLogger(__name__)


class GeminiEventExtractor:
    """Adapter that wraps Google Gemini API to implement EventExtractor interface"""

    def __init__(self, config: GeminiEventConfig):
        """
        Initialize with Gemini configuration

        Args:
            config: GeminiEventConfig instance with all Gemini settings

        Raises:
            ExtractorConfigurationError: If required configuration is missing
        """
        from .extractor_factory import ExtractorConfigurationError

        self.config = config
        self._client = None
        self._model = None
        self._total_tokens = 0
        self._total_cost = 0.0

        # Validate API key at initialization
        if not config.api_key or config.api_key.strip() == "":
            raise ExtractorConfigurationError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable."
            )

        # Lazy import Gemini client
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.api_key)

            # Create model with JSON mode configuration
            self._model = genai.GenerativeModel(
                model_name=config.model_id,
                generation_config={
                    "temperature": config.temperature,
                    "max_output_tokens": config.max_output_tokens,
                    "response_mime_type": "application/json"  # Native JSON mode
                }
            )
            self.available = True
            logger.info(f"✅ GeminiEventExtractor initialized with model: {config.model_id}")
        except ImportError:
            logger.error("❌ google-generativeai library not available")
            self.available = False
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini client: {e}")
            self.available = False

    def extract_events(self, text: str, metadata: Dict[str, Any]) -> List[EventRecord]:
        """
        Extract legal events using Gemini API

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
            logger.warning("⚠️ Gemini adapter not available - creating fallback record")
            return [self._create_fallback_record(document_name, "Gemini client not available")]

        if not text or not text.strip():
            logger.warning(f"⚠️ No text provided for {document_name} - creating fallback record")
            return [self._create_fallback_record(document_name, "No text content to process")]

        try:
            # Call Gemini API with retry logic
            response_data = self._call_gemini_api_with_retry(text)

            if not response_data:
                logger.error(f"❌ Gemini API returned empty response for {document_name}")
                return [self._create_fallback_record(document_name, "Gemini API returned empty response")]

            # Parse the response and extract legal events
            events = self._parse_gemini_response(response_data, document_name)

            if not events:
                logger.warning(f"⚠️ No events extracted from Gemini response for {document_name}")
                return [self._create_fallback_record(document_name, "No legal events found in response")]

            logger.info(
                f"✅ Extracted {len(events)} legal events from {document_name} via Gemini "
                f"(model: {self.config.model_id})"
            )
            return events

        except Exception as e:
            logger.error(f"❌ GeminiEventExtractor failed for {document_name}: {e}")
            return [self._create_fallback_record(document_name, f"Gemini processing error: {str(e)}")]

    def _call_gemini_api_with_retry(
        self,
        text: str,
        max_retries: int = 3,
        initial_delay: float = 1.0
    ) -> Optional[str]:
        """
        Make API call to Gemini with exponential backoff retry logic

        Args:
            text: Document text to process
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds before first retry

        Returns:
            API response text (JSON string) or None on failure
        """
        delay = initial_delay

        for attempt in range(max_retries + 1):
            try:
                logger.info(f"🔍 Calling Gemini API (attempt {attempt + 1}/{max_retries + 1})")

                # Build prompt: Legal events prompt + document text
                prompt = f"{LEGAL_EVENTS_PROMPT}\n\nDocument text:\n{text}"

                # Generate content
                response = self._model.generate_content(prompt)

                if not response or not response.text:
                    logger.warning(f"⚠️ Empty response from Gemini (attempt {attempt + 1})")
                    if attempt < max_retries:
                        time.sleep(delay)
                        delay *= 2
                        continue
                    return None

                logger.info(f"✅ Gemini API call successful (response length: {len(response.text)} chars)")
                return response.text

            except Exception as e:
                error_msg = str(e).lower()

                # Check for rate limits
                if "quota" in error_msg or "rate" in error_msg:
                    if attempt < max_retries:
                        logger.warning(f"⚠️ Rate limit hit, retrying in {delay}s (attempt {attempt + 1})")
                        time.sleep(delay)
                        delay *= 2
                        continue
                    else:
                        logger.error(f"❌ Max retries exceeded due to rate limits")
                        return None

                # Other errors
                logger.error(f"❌ Gemini API error: {e}")
                if attempt < max_retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                return None

        logger.error(f"❌ All {max_retries + 1} API attempts failed")
        return None

    def _parse_gemini_response(self, response_text: str, document_name: str) -> List[EventRecord]:
        """
        Parse Gemini JSON response into EventRecord list

        Args:
            response_text: JSON string from Gemini API
            document_name: Source document filename

        Returns:
            List of EventRecord objects
        """
        try:
            # Parse JSON response
            response_json = json.loads(response_text)

            # Extract events array (handle both {"events": [...]} and direct [...] formats)
            if isinstance(response_json, dict) and "events" in response_json:
                events_data = response_json["events"]
            elif isinstance(response_json, list):
                events_data = response_json
            else:
                logger.error(f"❌ Unexpected JSON structure: {type(response_json)}")
                return []

            if not events_data:
                logger.warning(f"⚠️ Empty events array in Gemini response")
                return []

            # Convert to EventRecord list
            event_records = []
            for idx, event in enumerate(events_data, 1):
                try:
                    event_record = EventRecord(
                        number=idx,
                        date=event.get("date", DEFAULT_NO_DATE),
                        event_particulars=event.get("event_particulars", "Event details not available"),
                        citation=event.get("citation", DEFAULT_NO_CITATION),
                        document_reference=document_name,
                        attributes={
                            "model": self.config.model_id,
                            "temperature": self.config.temperature,
                            "source": "gemini_direct_api"
                        }
                    )
                    event_records.append(event_record)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to parse event {idx}: {e}")
                    continue

            return event_records

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON response from Gemini: {e}")
            logger.debug(f"Raw response: {response_text[:500]}...")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error parsing Gemini response: {e}")
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
            event_particulars=f"Failed to extract legal events from {document_name}: {reason}",
            citation="No citation available (extraction failed)",
            document_reference=document_name,
            attributes={"fallback": True, "reason": reason}
        )

    def is_available(self) -> bool:
        """
        Check if Gemini is properly configured and available

        Returns:
            True if extractor can be used, False otherwise
        """
        return self.available and self._model is not None
