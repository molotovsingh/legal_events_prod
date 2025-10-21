#!/usr/bin/env python3
"""
Gemini 2.5 Pro Judge Implementation with Built-in Thinking

Uses Google's Gemini 2.5 Pro model with automatic thinking capabilities
for deep reasoning about legal event extraction quality.
"""

import json
import logging
from typing import List, Dict, Any
from datetime import datetime

from .base_judge import BaseJudge, JudgeResult, ProviderScore

logger = logging.getLogger(__name__)


class GeminiProJudge(BaseJudge):
    """
    Gemini 2.5 Pro judge with built-in thinking capabilities.

    Thinking is automatic in Gemini 2.5 - no special configuration needed.
    Uses JSON response format for structured output.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-pro",
        temperature: float = 0.0
    ):
        """
        Initialize Gemini Pro judge

        Args:
            api_key: Google AI API key (GEMINI_API_KEY)
            model: Model name (default: "gemini-2.5-pro")
            temperature: Temperature (0.0 for consistency)
        """
        super().__init__(api_key=api_key, model=model, temperature=temperature)

        # Lazy import Google Generative AI
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.genai = genai
            self.model_obj = genai.GenerativeModel(self.model)
        except ImportError:
            logger.error("google-generativeai library not available - Gemini judge will be disabled")
            raise

        logger.info(f"Gemini Pro Judge initialized with model: {model}")

    def judge_providers(
        self,
        document_name: str,
        provider_outputs: Dict[str, List[Dict[str, Any]]]
    ) -> JudgeResult:
        """
        Evaluate all provider outputs using Gemini Pro with automatic thinking.

        Args:
            document_name: Name of the document being evaluated
            provider_outputs: Dict mapping provider names to list of events

        Returns:
            JudgeResult with Gemini's scores and reasoning
        """
        logger.info(f"Gemini Pro Judge evaluating document: {document_name}")
        logger.info(f"Providers to compare: {list(provider_outputs.keys())}")

        # Build standardized prompt
        prompt = self._build_judge_prompt(document_name, provider_outputs)

        # Call Gemini API
        response_text = self._call_api(prompt)

        # Parse response
        result = json.loads(response_text)

        # Build ProviderScore objects
        provider_scores = []
        for provider_data in result.get("providers", []):
            score = ProviderScore(
                provider=provider_data["provider"],
                document_name=document_name,
                completeness=float(provider_data["completeness"]),
                accuracy=float(provider_data["accuracy"]),
                hallucinations=float(provider_data["hallucinations"]),
                citation_quality=float(provider_data["citation_quality"]),
                overall_quality=float(provider_data["overall_quality"]),
                reasoning=provider_data["reasoning"],
                event_count=len(provider_outputs.get(provider_data["provider"], []))
            )
            provider_scores.append(score)

        # Calculate cost
        cost = getattr(self, '_last_cost', 0.0)

        # Create judge result
        judge_result = JudgeResult(
            judge_name="gemini-2.5-pro",
            model=self.model,
            document_name=document_name,
            provider_scores=provider_scores,
            winner=result.get("winner", "unknown"),
            timestamp=datetime.now().isoformat(),
            cost=cost,
            thinking_tokens=0  # Gemini doesn't expose thinking tokens separately
        )

        logger.info(f"Gemini Pro Judge winner for {document_name}: {judge_result.winner}")
        logger.info(f"Gemini cost: ${cost:.4f}")

        return judge_result

    def _call_api(self, prompt: str) -> str:
        """
        Make API call to Gemini 2.5 Pro with automatic thinking.

        Args:
            prompt: The judge evaluation prompt

        Returns:
            JSON string with provider scores
        """
        try:
            # Configure generation parameters for JSON output
            generation_config = {
                "temperature": self.temperature,
                "response_mime_type": "application/json"
            }

            # Generate content
            response = self.model_obj.generate_content(
                prompt,
                generation_config=generation_config
            )

            # Extract text response
            response_text = response.text

            # Calculate cost (Gemini 2.5 Pro pricing: ~$1.25/$5 per M tokens)
            # Note: usage_metadata might not be available in all versions
            if hasattr(response, 'usage_metadata'):
                input_tokens = response.usage_metadata.prompt_token_count
                output_tokens = response.usage_metadata.candidates_token_count

                input_cost = (input_tokens / 1_000_000) * 1.25
                output_cost = (output_tokens / 1_000_000) * 5.00
                self._last_cost = input_cost + output_cost

                logger.debug(f"Gemini API usage: {input_tokens} input, {output_tokens} output tokens")
                logger.debug(f"Gemini API cost: ${self._last_cost:.4f}")
            else:
                # Fallback - estimate based on response length
                estimated_tokens = len(prompt.split()) + len(response_text.split())
                self._last_cost = (estimated_tokens / 1_000_000) * 2.0
                logger.debug(f"Gemini API cost (estimated): ${self._last_cost:.4f}")

            return response_text

        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise

    def is_available(self) -> bool:
        """Check if Gemini Pro judge is properly configured"""
        return bool(self.api_key) and hasattr(self, 'model_obj')
