#!/usr/bin/env python3
"""
Claude Opus 4.1 Judge Implementation with Extended Thinking

Uses Anthropic's Claude Opus 4.1 model with extended thinking mode
for deep reasoning about legal event extraction quality.
"""

import json
import logging
from typing import List, Dict, Any
from datetime import datetime

from .base_judge import BaseJudge, JudgeResult, ProviderScore

logger = logging.getLogger(__name__)


class ClaudeOpusJudge(BaseJudge):
    """
    Claude Opus 4.1 judge with extended thinking capabilities.

    Uses thinking mode with budget_tokens for deep reasoning.
    Thinking appears as separate content block in response.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-1",
        thinking_budget: int = 10000,
        temperature: float = 1.0  # MUST be 1.0 when thinking is enabled
    ):
        """
        Initialize Claude Opus judge

        Args:
            api_key: Anthropic API key
            model: Model name (default: "claude-opus-4-1")
            thinking_budget: Budget tokens for extended thinking (default: 10000)
            temperature: Temperature (must be 1.0 when thinking is enabled)
        """
        super().__init__(api_key=api_key, model=model, temperature=temperature)

        self.thinking_budget = thinking_budget

        # Lazy import Anthropic client
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
        except ImportError:
            logger.error("anthropic library not available - Claude Opus judge will be disabled")
            raise

        logger.info(f"Claude Opus Judge initialized with thinking_budget={thinking_budget}")

    def judge_providers(
        self,
        document_name: str,
        provider_outputs: Dict[str, List[Dict[str, Any]]]
    ) -> JudgeResult:
        """
        Evaluate all provider outputs using Claude Opus with extended thinking.

        Args:
            document_name: Name of the document being evaluated
            provider_outputs: Dict mapping provider names to list of events

        Returns:
            JudgeResult with Claude's scores and reasoning
        """
        logger.info(f"Claude Opus Judge evaluating document: {document_name}")
        logger.info(f"Providers to compare: {list(provider_outputs.keys())}")

        # Build standardized prompt
        prompt = self._build_judge_prompt(document_name, provider_outputs)

        # Call Anthropic API
        response_text = self._call_api(prompt)

        # Parse response
        result = json.loads(response_text)

        # Extract thinking tokens from last call
        thinking_tokens = getattr(self, '_last_thinking_tokens', 0)

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
            judge_name="claude-opus-4-1",
            model=self.model,
            document_name=document_name,
            provider_scores=provider_scores,
            winner=result.get("winner", "unknown"),
            timestamp=datetime.now().isoformat(),
            cost=cost,
            thinking_tokens=thinking_tokens
        )

        logger.info(f"Claude Opus Judge winner for {document_name}: {judge_result.winner}")
        logger.info(f"Claude thinking tokens: {thinking_tokens}, cost: ${cost:.4f}")

        return judge_result

    def _call_api(self, prompt: str) -> str:
        """
        Make API call to Claude Opus with extended thinking.

        Args:
            prompt: The judge evaluation prompt

        Returns:
            JSON string with provider scores
        """
        try:
            # Add JSON output instruction to system prompt
            system_prompt = """You are an expert legal document analyst. You evaluate legal event extraction quality objectively.

You must return your evaluation in valid JSON format only. No other text before or after the JSON.

Think deeply about your evaluation using the extended thinking budget provided."""

            # max_tokens must be > thinking.budget_tokens
            # Allocate thinking_budget + 4096 for actual response
            max_tokens = self.thinking_budget + 4096

            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                thinking={
                    "type": "enabled",
                    "budget_tokens": self.thinking_budget
                },
                temperature=self.temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extract content - Claude returns list of content blocks
            # Thinking appears as separate block with type="thinking"
            text_content = ""
            thinking_content = ""

            for block in response.content:
                if block.type == "text":
                    text_content += block.text
                elif block.type == "thinking":
                    thinking_content = block.thinking

            # Calculate thinking tokens and cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            # Claude Opus 4.1 pricing: $15/M input, $75/M output
            input_cost = (input_tokens / 1_000_000) * 15.00
            output_cost = (output_tokens / 1_000_000) * 75.00
            self._last_cost = input_cost + output_cost

            # Estimate thinking tokens (not directly provided by API)
            # Thinking tokens are included in output tokens
            self._last_thinking_tokens = len(thinking_content.split()) * 1.3 if thinking_content else 0

            logger.debug(f"Claude Opus API usage: {input_tokens} input, {output_tokens} output tokens")
            logger.debug(f"Claude Opus thinking: {len(thinking_content)} chars")
            logger.debug(f"Claude Opus API cost: ${self._last_cost:.4f}")

            return text_content

        except Exception as e:
            logger.error(f"Claude Opus API call failed: {e}")
            raise

    def is_available(self) -> bool:
        """Check if Claude Opus judge is properly configured"""
        return bool(self.api_key) and hasattr(self, 'client')
