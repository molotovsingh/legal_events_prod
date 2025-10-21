#!/usr/bin/env python3
"""
GPT-5 Judge Implementation with Maximum Thinking

Uses OpenAI's GPT-5 model with reasoning_effort="high" for deep reasoning
about legal event extraction quality.
"""

import json
import logging
from typing import List, Dict, Any
from datetime import datetime

from openai import OpenAI

from .base_judge import BaseJudge, JudgeResult, ProviderScore

logger = logging.getLogger(__name__)


class GPT5Judge(BaseJudge):
    """
    GPT-5 judge with maximum thinking capabilities.

    Uses reasoning_effort="high" to maximize quality of evaluation.
    Tracks reasoning tokens separately for cost analysis.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5",
        reasoning_effort: str = "high",
        temperature: float = 1.0  # Required for GPT-5
    ):
        """
        Initialize GPT-5 judge

        Args:
            api_key: OpenAI API key
            model: Model name (default: "gpt-5")
            reasoning_effort: Thinking level - "minimal", "low", "medium", "high" (default: "high")
            temperature: Temperature (must be 1.0 for GPT-5)
        """
        super().__init__(api_key=api_key, model=model, temperature=temperature)

        self.reasoning_effort = reasoning_effort
        self.client = OpenAI(api_key=self.api_key)

        logger.info(f"GPT-5 Judge initialized with reasoning_effort={reasoning_effort}")

    def judge_providers(
        self,
        document_name: str,
        provider_outputs: Dict[str, List[Dict[str, Any]]]
    ) -> JudgeResult:
        """
        Evaluate all provider outputs using GPT-5 with deep reasoning.

        Args:
            document_name: Name of the document being evaluated
            provider_outputs: Dict mapping provider names to list of events

        Returns:
            JudgeResult with GPT-5's scores and reasoning
        """
        logger.info(f"GPT-5 Judge evaluating document: {document_name}")
        logger.info(f"Providers to compare: {list(provider_outputs.keys())}")

        # Build standardized prompt
        prompt = self._build_judge_prompt(document_name, provider_outputs)

        # Call GPT-5 API
        response_text = self._call_api(prompt)

        # Parse response
        result = json.loads(response_text)

        # Extract reasoning tokens from response metadata
        thinking_tokens = getattr(self, '_last_reasoning_tokens', 0)

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

        # Calculate cost (GPT-5 pricing: ~$2.50/$10 per M tokens)
        cost = getattr(self, '_last_cost', 0.0)

        # Create judge result
        judge_result = JudgeResult(
            judge_name="gpt-5",
            model=self.model,
            document_name=document_name,
            provider_scores=provider_scores,
            winner=result.get("winner", "unknown"),
            timestamp=datetime.now().isoformat(),
            cost=cost,
            thinking_tokens=thinking_tokens
        )

        logger.info(f"GPT-5 Judge winner for {document_name}: {judge_result.winner}")
        logger.info(f"GPT-5 reasoning tokens: {thinking_tokens}, cost: ${cost:.4f}")

        return judge_result

    def _call_api(self, prompt: str) -> str:
        """
        Make API call to GPT-5 with maximum thinking.

        Args:
            prompt: The judge evaluation prompt

        Returns:
            JSON string with provider scores
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert legal document analyst. You evaluate legal event extraction quality objectively and return results in JSON format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                reasoning_effort=self.reasoning_effort,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )

            # Extract reasoning tokens and calculate cost
            usage = response.usage
            total_tokens = usage.total_tokens

            # GPT-5 pricing (approximate):
            # Input: $2.50/M, Output: $10/M, Reasoning: $10/M (same as output)
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens

            # Check if reasoning tokens are available
            if hasattr(usage, 'completion_tokens_details'):
                reasoning_tokens = getattr(usage.completion_tokens_details, 'reasoning_tokens', 0)
                self._last_reasoning_tokens = reasoning_tokens
            else:
                reasoning_tokens = 0
                self._last_reasoning_tokens = 0

            # Calculate cost
            input_cost = (input_tokens / 1_000_000) * 2.50
            output_cost = (output_tokens / 1_000_000) * 10.00
            self._last_cost = input_cost + output_cost

            logger.debug(f"GPT-5 API usage: {input_tokens} input, {output_tokens} output, {reasoning_tokens} reasoning tokens")
            logger.debug(f"GPT-5 API cost: ${self._last_cost:.4f}")

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"GPT-5 API call failed: {e}")
            raise

    def is_available(self) -> bool:
        """Check if GPT-5 judge is properly configured"""
        return bool(self.api_key)
