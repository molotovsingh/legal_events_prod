"""
OpenCode Zen Event Extractor Adapter
Wraps OpenCode Zen API to implement EventExtractor interface
"""

import json
import logging
from typing import List, Dict, Any, Optional

from .interfaces import EventExtractor, EventRecord
from .config import OpenCodeZenConfig
from .constants import DEFAULT_NO_DATE, DEFAULT_NO_CITATION, LEGAL_EVENTS_PROMPT

logger = logging.getLogger(__name__)


class OpenCodeZenEventExtractor:
    """Adapter that wraps OpenCode Zen API to implement EventExtractor interface"""

    def __init__(self, config: OpenCodeZenConfig):
        """
        Initialize with OpenCode Zen configuration

        Args:
            config: OpenCodeZenConfig instance with all OpenCode Zen settings

        Raises:
            ExtractorConfigurationError: If required configuration is missing
        """
        from .extractor_factory import ExtractorConfigurationError

        self.config = config
        self._http = None

        # Validate API key at initialization
        if not config.api_key or config.api_key.strip() == "":
            raise ExtractorConfigurationError(
                "OpenCode Zen API key is required. Set OPENCODEZEN_API_KEY environment variable."
            )

        # Lazy import HTTP client
        try:
            import requests
            self._http = requests
            self.available = True
            logger.info("✅ OpenCodeZenEventExtractor initialized successfully")
        except ImportError:
            logger.warning("⚠️ requests library not available - OpenCode Zen adapter will be disabled")
            self.available = False

    def extract_events(self, text: str, metadata: Dict[str, Any]) -> List[EventRecord]:
        """
        Extract legal events using OpenCode Zen API

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
            logger.warning("⚠️ OpenCode Zen adapter not available - creating fallback record")
            return [self._create_fallback_record(document_name, "OpenCode Zen HTTP client not available")]

        if not text or not text.strip():
            logger.warning(f"⚠️ No text provided for {document_name} - creating fallback record")
            return [self._create_fallback_record(document_name, "No text content to process")]

        try:
            # Call OpenCode Zen API
            response_data = self._call_opencode_zen_api(text)

            if not response_data:
                logger.error(f"❌ OpenCode Zen API returned empty response for {document_name}")
                return [self._create_fallback_record(document_name, "OpenCode Zen API returned empty response")]

            # Parse the response and extract legal events
            events = self._parse_opencode_zen_response(response_data, document_name)

            if not events:
                logger.warning(f"⚠️ No events extracted from OpenCode Zen response for {document_name}")
                return [self._create_fallback_record(document_name, "No legal events found in response")]

            logger.info(f"✅ Extracted {len(events)} legal events from {document_name} via OpenCode Zen")
            return events

        except Exception as e:
            logger.error(f"❌ OpenCodeZenEventExtractor failed for {document_name}: {e}")
            return [self._create_fallback_record(document_name, f"OpenCode Zen processing error: {str(e)}")]

    def _call_opencode_zen_api(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Make API call to OpenCode Zen using OpenAI-compatible format

        Args:
            text: Document text to process

        Returns:
            API response data or None on failure
        """
        import os

        # Use OpenAI-standard endpoint
        base_url = self.config.base_url.rstrip('/')
        url = f"{base_url}/chat/completions"

        # Construct OpenAI-compatible messages payload
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

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.0,
            "stream": False  # Explicitly disable streaming
        }

        # Check for debug mode
        debug_mode = os.getenv("OPENCODEZEN_DEBUG", "false").lower() in ("true", "1", "yes")

        # Try both auth header variants
        auth_variants = [
            {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"},
            {"X-API-Key": self.config.api_key, "Content-Type": "application/json"}
        ]

        last_error = None
        for attempt, headers in enumerate(auth_variants, 1):
            try:
                if debug_mode:
                    auth_type = "Bearer" if "Authorization" in headers else "X-API-Key"
                    logger.debug(f"🔍 OpenCode Zen attempt {attempt}/2 with {auth_type} auth")
                    logger.debug(f"🔍 URL: {url}")
                    logger.debug(f"🔍 Model: {self.config.model}")
                    logger.debug(f"🔍 Payload preview: {json.dumps(payload, indent=2)[:500]}...")

                response = self._http.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout
                )

                # Log response details for debugging
                if debug_mode:
                    logger.debug(f"🔍 Response status: {response.status_code}")
                    logger.debug(f"🔍 Response headers: {dict(response.headers)}")
                    logger.debug(f"🔍 Response preview: {response.text[:500]}...")

                # Map HTTP status codes to actionable errors
                if response.status_code == 401 or response.status_code == 403:
                    logger.error(f"❌ Authentication failed (HTTP {response.status_code})")
                    logger.error(f"   Check OPENCODEZEN_API_KEY validity")
                    if attempt < len(auth_variants):
                        continue  # Try next auth variant
                    return None
                elif response.status_code == 404:
                    logger.error(f"❌ Endpoint not found (HTTP 404)")
                    logger.error(f"   URL: {url}")
                    logger.error(f"   Check OPENCODEZEN_BASE_URL and model slug: {self.config.model}")
                    return None
                elif response.status_code == 429:
                    logger.error(f"❌ Rate limited (HTTP 429)")
                    logger.error(f"   Try again later or check rate limit settings")
                    return None
                elif response.status_code >= 500:
                    logger.error(f"❌ Provider outage (HTTP {response.status_code})")
                    logger.error(f"   Service unavailable, try again later")
                    return None

                response.raise_for_status()

                # Parse and return JSON
                response_json = response.json()

                if debug_mode:
                    logger.debug(f"✅ Successfully parsed JSON response")

                return response_json

            except self._http.exceptions.RequestException as e:
                last_error = e
                error_details = str(e)

                # Log comprehensive error information
                logger.error(f"❌ OpenCode Zen API request failed (attempt {attempt}/2): {error_details}")

                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"   Status code: {e.response.status_code}")
                    logger.error(f"   Response preview: {e.response.text[:500]}")
                    if 'x-request-id' in e.response.headers:
                        logger.error(f"   Request ID: {e.response.headers['x-request-id']}")

                # Try next auth variant if available
                if attempt < len(auth_variants):
                    continue

                return None

            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse OpenCode Zen API response: {e}")
                logger.error(f"   Raw response (first 500 chars): {response.text[:500]}")
                return None

        # All attempts failed
        if last_error:
            logger.error(f"❌ All authentication methods failed for OpenCode Zen")
            logger.error(f"   Last error: {last_error}")

        return None

    def _parse_opencode_zen_response(self, response_data: Dict[str, Any], document_name: str) -> List[EventRecord]:
        """
        Parse OpenCode Zen API response and convert to EventRecord instances

        Args:
            response_data: Response from OpenCode Zen API
            document_name: Source document name

        Returns:
            List of EventRecord instances
        """
        try:
            # Extract events from OpenCode Zen response format
            events_data = response_data.get("events", [])

            # Alternative response formats
            if not events_data:
                events_data = response_data.get("extractions", [])
            if not events_data:
                events_data = response_data.get("results", [])

            # If single event returned as object
            if not events_data and "event_particulars" in response_data:
                events_data = [response_data]

            if not isinstance(events_data, list):
                logger.warning("⚠️ Events data is not a list in OpenCode Zen response")
                return []

            # Convert to EventRecord instances
            event_records = []
            for i, event_data in enumerate(events_data, 1):
                if not isinstance(event_data, dict):
                    continue

                # Extract required fields with defaults
                event_particulars = event_data.get("event_particulars", "")
                if not event_particulars:
                    # Try alternative field names
                    event_particulars = event_data.get("description", "")
                    if not event_particulars:
                        event_particulars = event_data.get("summary", "")

                if not event_particulars:
                    continue  # Skip events without particulars

                # Extract other fields with fallbacks
                date = event_data.get("date", DEFAULT_NO_DATE)
                if not date:
                    date = event_data.get("event_date", DEFAULT_NO_DATE)

                citation = event_data.get("citation", DEFAULT_NO_CITATION)
                if not citation:
                    citation = event_data.get("reference", DEFAULT_NO_CITATION)

                # Create EventRecord with OpenCode Zen-specific attributes
                attributes = {
                    "provider": "opencode_zen",
                    "model": self.config.model,
                    "confidence": event_data.get("confidence", 0.0),
                    "original_response": event_data
                }

                # Include additional metadata if available
                if "char_start" in event_data:
                    attributes["char_start"] = event_data["char_start"]
                if "char_end" in event_data:
                    attributes["char_end"] = event_data["char_end"]

                event_record = EventRecord(
                    number=i,
                    date=date,
                    event_particulars=event_particulars,
                    citation=citation,
                    document_reference=document_name,
                    attributes=attributes
                )
                event_records.append(event_record)

            return event_records

        except Exception as e:
            logger.error(f"❌ Failed to parse OpenCode Zen response: {e}")
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
            event_particulars=f"Failed to extract legal events from {document_name} using OpenCode Zen: {reason}",
            citation="No citation available (extraction failed)",
            document_reference=document_name,
            attributes={
                "provider": "opencode_zen",
                "fallback": True,
                "reason": reason
            }
        )

    def is_available(self) -> bool:
        """
        Check if OpenCode Zen is properly configured and available

        Returns:
            True if extractor can be used, False otherwise
        """
        return (
            self.available and
            self._http is not None and
            self.config.api_key and
            self.config.api_key.strip() != ""
        )