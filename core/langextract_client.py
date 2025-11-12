"""
Centralized LangExtract Client - Single point for all LangExtract operations
Handles API key loading, shared prompts, and extraction calls
"""

import os
import logging
import time
from typing import Dict, List, Any, Optional

try:
    import langextract as lx
    LANGEXTRACT_AVAILABLE = True
except ImportError:
    LANGEXTRACT_AVAILABLE = False
    lx = None  # Set to None so references don't fail at import time

from .constants import REQUIRED_ENV_VARS, GEMINI_DEFAULT_MODEL, LEGAL_EVENTS_PROMPT
from .examples import get_legal_events_examples

logger = logging.getLogger(__name__)


class LangExtractClient:
    """
    Centralized client for all LangExtract operations
    Manages API keys, shared examples, and extraction calls
    """

    def __init__(self, model: str = None):
        """
        Initialize LangExtract client.

        Args:
            model: Optional model override. If not provided, reads from GEMINI_MODEL env var.
        """
        self.available = LANGEXTRACT_AVAILABLE
        self.api_key = None
        # Use provided model, or fall back to env var (standardized to GEMINI_MODEL in v0.11.0)
        self.model_id = model or os.getenv("GEMINI_MODEL", os.getenv("GEMINI_MODEL_ID", GEMINI_DEFAULT_MODEL))

        if not self.available:
            logger.error("🚨 LangExtract module not available")
            raise ImportError("langextract module required")

        # Load API key
        self._load_api_key()

        # Shared example data for all extractions
        self.shared_examples = self._create_shared_examples()

    def _load_api_key(self):
        """Load and validate GEMINI_API_KEY"""
        self.api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')

        if not self.api_key:
            logger.error("🚨 GEMINI_API_KEY or GOOGLE_API_KEY not found in environment")
            logger.error("💡 Solution: Set GEMINI_API_KEY in your .env file (see .env.example line 95-96)")
            logger.error("📝 Get your key at: https://makersuite.google.com/app/apikey")
            raise ValueError("GEMINI_API_KEY required for LangExtract operations - please configure in .env file")

        logger.info("✅ GEMINI_API_KEY loaded successfully")

    def _create_shared_examples(self) -> List[Any]:
        """
        Load shared example data from external module

        Returns:
            List of LangExtract examples or empty list on failure
        """
        try:
            examples = get_legal_events_examples()

            if not examples:
                logger.error("❌ No examples loaded from external module")
                return []

            logger.info(f"✅ Loaded {len(examples)} examples from external module")
            return examples

        except Exception as e:
            logger.error(f"❌ Failed to load examples from external module: {e}")
            return []

    def extract_with_prompt(self,
                           text: str,
                           prompt_description: str,
                           custom_examples: Optional[List[Any]] = None,
                           max_retries: int = 3) -> Optional[Any]:
        """
        Execute LangExtract with shared configuration and retry logic

        Args:
            text: Input text to process
            prompt_description: Description of what to extract
            custom_examples: Optional custom examples (uses shared if not provided)
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            LangExtract response or None if failed
        """
        if not text or not text.strip():
            logger.error("❌ No text provided for extraction")
            return None

        # Validate text length (warn if very large)
        text_length = len(text)
        if text_length > 500000:
            logger.warning(f"⚠️ Very large document ({text_length:,} chars) - may exceed API limits")
        
        examples = custom_examples if custom_examples else self.shared_examples

        logger.info(f"🔍 Starting LangExtract call: {prompt_description[:80]}...")
        logger.info(f"📝 Text length: {text_length:,} chars")
        logger.info(f"🎯 Examples: {len(examples)}")

        # Retry loop with exponential backoff
        for attempt in range(1, max_retries + 1):
            try:
                # Execute the real LangExtract API call
                response = lx.extract(
                    text_or_documents=text,
                    prompt_description=prompt_description,
                    examples=examples,
                    model_id=self.model_id,
                    api_key=self.api_key
                )

                if not response:
                    logger.error(f"❌ LangExtract returned empty response (attempt {attempt}/{max_retries})")
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)  # Exponential backoff: 2s, 4s, 8s
                        continue
                    return None

                logger.info(f"✅ LangExtract call successful (attempt {attempt})")
                return response

            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                logger.error(f"❌ LangExtract API call failed (attempt {attempt}/{max_retries}): {error_type}: {error_msg}")
                
                # Log additional context for debugging
                if "timeout" in error_msg.lower():
                    logger.error(f"⏱️ Timeout detected - document may be too large or API may be overloaded")
                elif "rate" in error_msg.lower() or "quota" in error_msg.lower():
                    logger.error(f"🚫 Rate limit or quota exceeded - consider waiting or upgrading API plan")
                elif "token" in error_msg.lower() or "context" in error_msg.lower():
                    logger.error(f"📏 Token/context limit exceeded - document size: {text_length:,} chars")
                
                # Retry with exponential backoff if not the last attempt
                if attempt < max_retries:
                    backoff_time = 2 ** attempt
                    logger.info(f"⏳ Retrying in {backoff_time}s...")
                    time.sleep(backoff_time)
                else:
                    logger.error(f"💥 All {max_retries} attempts failed - giving up")
                    return None

        return None

    def is_available(self) -> bool:
        """Check if LangExtract is properly configured"""
        return self.available and bool(self.api_key)

    def get_required_env_vars(self) -> List[str]:
        """Return list of required environment variables"""
        return REQUIRED_ENV_VARS.copy()

    def extract_legal_events(self, text: str, document_name: str) -> Dict[str, Any]:
        """
        Extract legal events using standardized prompt

        Args:
            text: Document text
            document_name: Source document filename

        Returns:
            Standardized result dictionary
        """
        # Verify examples are loaded before attempting extraction
        if not self.shared_examples:
            error_msg = "LangExtract example setup failed - cannot proceed with extraction"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        prompt = LEGAL_EVENTS_PROMPT

        response = self.extract_with_prompt(text, prompt)

        if not response:
            return {
                "success": False,
                "error": "LangExtract API call failed",
                "extractions": []
            }

        try:
            extractions = []
            dropped_count = 0

            if hasattr(response, 'extractions'):
                for extraction in response.extractions:
                    # Get attributes and ensure document_reference is set to our filename
                    attributes = getattr(extraction, 'attributes', {}).copy()
                    attributes['document_reference'] = document_name

                    # Capture character offsets if available (for GPT-5 integration and precise source attribution)
                    char_interval = getattr(extraction, 'char_interval', None)
                    start_char = getattr(extraction, 'start_char', None)
                    end_char = getattr(extraction, 'end_char', None)

                    if char_interval and hasattr(char_interval, 'start_pos') and hasattr(char_interval, 'end_pos'):
                        attributes['char_start'] = char_interval.start_pos
                        attributes['char_end'] = char_interval.end_pos
                        logger.debug(f"📍 Captured char_interval: {char_interval.start_pos}-{char_interval.end_pos}")
                    elif start_char is not None and end_char is not None:
                        attributes['char_start'] = start_char
                        attributes['char_end'] = end_char
                        logger.debug(f"📍 Captured start/end chars: {start_char}-{end_char}")
                    else:
                        logger.debug(f"📍 No character offsets available for extraction")

                    # Filter out extractions with empty or whitespace-only event_particulars
                    event_particulars = attributes.get('event_particulars', '').strip()
                    if not event_particulars:
                        dropped_count += 1
                        logger.warning(f"⚠️ Dropped extraction with empty event_particulars from {document_name}")
                        continue

                    extractions.append({
                        "extraction_text": getattr(extraction, 'extraction_text', ''),
                        "extraction_class": getattr(extraction, 'extraction_class', ''),
                        "attributes": attributes,
                        "document_reference": document_name
                    })

            if dropped_count > 0:
                logger.info(f"📋 Filtered out {dropped_count} empty extractions from {document_name}")

            return {
                "success": True,
                "extractions": extractions,
                "total_count": len(extractions)
            }

        except Exception as e:
            logger.error(f"❌ Failed to process LangExtract response: {e}")
            return {
                "success": False,
                "error": f"Response processing failed: {str(e)}",
                "extractions": []
            }

    def extract_dates(self, text: str) -> Dict[str, Any]:
        """
        Extract dates using standardized prompt

        Args:
            text: Document text

        Returns:
            Standardized result dictionary with dates
        """
        prompt = ("Extract all dates mentioned in this document. "
                 "Identify the date value, its context, and what type of legal event it refers to.")

        response = self.extract_with_prompt(text, prompt)

        if not response:
            return {
                "success": False,
                "error": "LangExtract API call failed",
                "dates": []
            }

        try:
            dates = []
            if hasattr(response, 'extractions'):
                for extraction in response.extractions:
                    dates.append({
                        "date_text": getattr(extraction, 'extraction_text', ''),
                        "date_class": getattr(extraction, 'extraction_class', ''),
                        "attributes": getattr(extraction, 'attributes', {})
                    })

            return {
                "success": True,
                "dates": dates,
                "total_count": len(dates)
            }

        except Exception as e:
            logger.error(f"❌ Failed to process date extraction response: {e}")
            return {
                "success": False,
                "error": f"Date processing failed: {str(e)}",
                "dates": []
            }