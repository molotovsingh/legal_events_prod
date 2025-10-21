"""
OpenRouter Classification Adapter

Handles document classification via OpenRouter API.
Supports all OpenRouter-compatible models (Claude, Llama, GPT, etc.)

Based on scripts/classify_documents.py implementation.
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional
import requests

from core.prompt_registry import PromptVariant

logger = logging.getLogger(__name__)


class OpenRouterClassifier:
    """
    Classification adapter for OpenRouter API.

    Handles:
    - API authentication
    - Prompt construction
    - JSON response parsing
    - Error handling and retries
    """

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_TEMPERATURE = 0.0
    DEFAULT_TIMEOUT = 60.0

    def __init__(
        self,
        model_id: str,
        prompt_variant: PromptVariant,
        cost_per_1m: float,
        max_chars: int = 2000
    ):
        """
        Initialize OpenRouter classifier.

        Args:
            model_id: Full model identifier (e.g., "anthropic/claude-3-haiku")
            prompt_variant: PromptVariant object from prompt_registry
            cost_per_1m: Cost per 1M tokens (for logging/tracking)
            max_chars: Maximum characters to send for classification (default: 2000)
        """
        self.model_id = model_id
        self.prompt_variant = prompt_variant
        self.cost_per_1m = cost_per_1m
        self.max_chars = max_chars

        # Validate API key
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY not set. "
                "Add it to your .env file to use OpenRouter classification. "
                "Get API key: https://openrouter.ai/keys"
            )

        logger.info(
            f"Initialized OpenRouterClassifier: model={model_id}, "
            f"prompt={prompt_variant.name}, cost=${cost_per_1m}/M"
        )

    def classify(
        self,
        text: str,
        document_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Classify a document using OpenRouter API.

        Args:
            text: Document text (from Docling extraction)
            document_title: Optional document title/filename

        Returns:
            dict: {
                "primary": str,  # Primary classification label
                "classes": List[str],  # All relevant labels
                "confidence": float,  # Confidence score (0-1)
                "rationale": str,  # Explanation
                "latency_seconds": float,  # API call time
                "model": str,  # Model used
                "prompt_version": str  # Prompt version
            }

        Raises:
            RuntimeError: If API call fails or response is invalid
        """
        # Trim text to max_chars
        excerpt = text[:self.max_chars].strip()

        # Build messages using prompt variant
        system_message, user_message = self._build_prompt(
            document_title or "Untitled Document",
            excerpt
        )

        # Make API call
        start_time = time.time()
        try:
            response_data, raw_response = self._call_api(
                system_message=system_message,
                user_message=user_message
            )
            latency = time.time() - start_time
        except Exception as e:
            logger.error(f"Classification failed for model {self.model_id}: {e}")
            raise RuntimeError(f"Classification API call failed: {e}") from e

        # Parse and validate response
        try:
            parsed = self._parse_response(raw_response)
        except Exception as e:
            logger.error(f"Failed to parse classification response: {e}")
            logger.error(f"Raw response: {raw_response}")
            raise RuntimeError(f"Invalid classification response: {e}") from e

        # Add metadata
        parsed["latency_seconds"] = latency
        parsed["model"] = self.model_id
        parsed["prompt_version"] = self.prompt_variant.version

        logger.info(
            f"Classification complete: {parsed['primary']} "
            f"(confidence={parsed['confidence']:.2f}, latency={latency:.2f}s)"
        )

        return parsed

    def _build_prompt(
        self,
        document_title: str,
        document_excerpt: str
    ) -> tuple[str, str]:
        """
        Build system and user messages from prompt variant.

        Uses the prompt_variant's prompt_text and splits it appropriately.

        Args:
            document_title: Document title/filename
            document_excerpt: Text excerpt (already trimmed)

        Returns:
            tuple: (system_message, user_message)
        """
        prompt_text = self.prompt_variant.prompt_text

        # Split prompt into system and user parts
        # The prompt format expects document excerpt at the end
        system_message = prompt_text.split("Review the document below")[0].strip()

        # Build user message with excerpt
        user_message = (
            f"Review the document below and return valid JSON only.\n\n"
            f"Document Title: {document_title}\n\n"
            f"Document Excerpt:\n{document_excerpt}"
        )

        return system_message, user_message

    def _call_api(
        self,
        system_message: str,
        user_message: str
    ) -> tuple[Dict[str, Any], str]:
        """
        Make API call to OpenRouter.

        Args:
            system_message: System prompt
            user_message: User prompt with document text

        Returns:
            tuple: (response_data dict, raw_content string)

        Raises:
            requests.HTTPError: If API returns error status
            RuntimeError: If response format is invalid
        """
        payload = {
            "model": self.model_id,
            "temperature": self.DEFAULT_TEMPERATURE,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": [{"type": "text", "text": user_message}]},
            ],
        }

        response = requests.post(
            self.OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.DEFAULT_TIMEOUT,
        )

        response.raise_for_status()
        data = response.json()

        if "choices" not in data or len(data["choices"]) == 0:
            raise RuntimeError(f"Invalid API response format: {data}")

        raw_content = data["choices"][0]["message"]["content"]

        return data, raw_content

    def _parse_response(self, raw_content: str) -> Dict[str, Any]:
        """
        Parse model response into structured classification result.

        Handles:
        - Markdown code fences (```json ... ```)
        - "JSON:" prefix
        - Whitespace cleanup

        Args:
            raw_content: Raw response from API

        Returns:
            dict: Parsed classification with primary, classes, confidence, rationale

        Raises:
            json.JSONDecodeError: If response is not valid JSON
        """
        cleaned = raw_content.strip()

        # Remove markdown code fences
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            # Drop leading ```json or ``` fence
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            # Drop trailing ``` fence
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        # Remove "JSON:" prefix
        if cleaned.lower().startswith("json:"):
            cleaned = cleaned[5:].strip()

        # Attempt direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: Extract JSON from between first { and last }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = cleaned[start : end + 1]
                return json.loads(snippet)
            raise

    def is_available(self) -> bool:
        """
        Check if classifier is available (API key configured).

        Returns:
            bool: True if API key is set
        """
        return bool(self.api_key)
