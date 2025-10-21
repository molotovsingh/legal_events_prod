#!/usr/bin/env python3
"""
Base Judge Abstract Class for 3-Judge Panel System

All judges must implement this interface to ensure consistent evaluation
across GPT-5, Claude Opus 4.1, and Gemini 2.5 Pro.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProviderScore:
    """Scores for a single provider on one document"""
    provider: str
    document_name: str
    completeness: float  # 0-10
    accuracy: float  # 0-10
    hallucinations: float  # 0-10 (10 = no hallucinations)
    citation_quality: float  # 0-10
    overall_quality: float  # 0-10
    reasoning: str  # Judge's explanation
    event_count: int


@dataclass
class JudgeResult:
    """Result from a single judge for one document"""
    judge_name: str  # "gpt-5", "claude-opus-4-1", "gemini-2-5-pro"
    model: str  # Actual model ID used
    document_name: str
    provider_scores: List[ProviderScore]
    winner: str  # Provider with highest overall quality
    timestamp: str
    cost: float  # Judging cost in USD
    thinking_tokens: int = 0  # Reasoning tokens used (for GPT-5, Claude)


class BaseJudge(ABC):
    """
    Abstract base class for all judges in the 3-judge panel.

    Each judge evaluates provider outputs on 5 standardized criteria:
    - Completeness (0-10)
    - Accuracy (0-10)
    - Hallucinations (0-10, where 10 = no hallucinations)
    - Citation Quality (0-10)
    - Overall Quality (0-10)
    """

    def __init__(self, api_key: str, model: str, temperature: float = 0.0):
        """
        Initialize judge with API credentials

        Args:
            api_key: API key for the model provider
            model: Model identifier (e.g., "gpt-5", "claude-opus-4-1")
            temperature: Temperature for generation (0.0 for consistency)
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

        if not self.api_key:
            raise ValueError(f"API key required for {self.__class__.__name__}")

        logger.info(f"{self.__class__.__name__} initialized with model: {model}")

    @abstractmethod
    def judge_providers(
        self,
        document_name: str,
        provider_outputs: Dict[str, List[Dict[str, Any]]]
    ) -> JudgeResult:
        """
        Evaluate all provider outputs for a single document.

        Args:
            document_name: Name of the document being evaluated
            provider_outputs: Dict mapping provider names to list of extracted events
                Example: {
                    "openai": [{"date": "...", "event_particulars": "...", "citation": "..."}],
                    "openrouter": [...]
                }

        Returns:
            JudgeResult with scores for all providers and winner selection
        """
        pass

    @abstractmethod
    def _call_api(self, prompt: str) -> str:
        """
        Make API call to the judge model.

        Args:
            prompt: The judge evaluation prompt

        Returns:
            JSON string with provider scores
        """
        pass

    def _build_judge_prompt(
        self,
        document_name: str,
        provider_outputs: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """
        Build standardized judge prompt (same across all judges).

        Args:
            document_name: Name of the document being evaluated
            provider_outputs: Dict mapping provider names to list of events

        Returns:
            Formatted prompt for the judge
        """
        prompt = f"""You are an expert legal document analyst evaluating the quality of automated legal event extraction systems. You will compare the outputs of multiple AI providers that extracted legal events from the same document.

**Document**: {document_name}

**Your Task**: Score each provider on 5 criteria (0-10 scale) and identify the best provider.

**Scoring Criteria** (calibrated for legal professional needs):

1. **Completeness** (0-10): Did the provider capture all meaningful legal events?
   - 10 = All events captured, no important events missed
   - 5 = About half the events captured
   - 0 = Very few or no events captured
   - NOTE: High completeness with missing citations should NOT score 10 overall

2. **Accuracy** (0-10): Are the dates, parties, facts, and details correct?
   - 10 = All facts accurate, no errors
   - 5 = Some errors but mostly correct
   - 0 = Many errors or completely wrong

3. **Hallucinations** (0-10): Are there invented facts NOT in the source?
   - 10 = No hallucinations, all facts from source
   - 5 = Minor invented details
   - 0 = Many fabricated facts

4. **Citation Quality** (0-10): Are legal citations accurate and properly formatted?
   - 10 = All citations accurate and well-formatted
   - 5 = Some citation errors or missing citations
   - 0 = No citations or completely wrong citations
   - **CRITICAL FOR LEGAL WORK**: Missing citations is a fatal flaw (max 5/10 overall)

5. **Overall Quality** (0-10): Overall usability for legal professionals
   - 10 = Production-ready, no corrections needed (requires proper citations)
   - 5 = Usable with moderate corrections
   - 0 = Not usable, requires complete rewrite
   - **Consider**: Legal professionals need QUALITY over QUANTITY
   - **Prefer**: 1 well-cited event over 5 events without citations
   - **Fatal flaws**: Missing citations, hallucinations, poor accuracy

**Provider Outputs**:

"""

        # Add each provider's output
        for provider, events in provider_outputs.items():
            prompt += f"\n**{provider.upper()}** ({len(events)} events):\n"
            if not events:
                prompt += "  (No events extracted)\n"
            else:
                for i, event in enumerate(events, 1):
                    prompt += f"  {i}. Date: {event.get('date', 'N/A')}\n"
                    prompt += f"     Event: {event.get('event_particulars', 'N/A')[:200]}...\n"
                    prompt += f"     Citation: {event.get('citation', 'N/A')}\n\n"

        prompt += """
**Output Format**: Return ONLY valid JSON with this exact structure:

{
  "providers": [
    {
      "provider": "provider_name",
      "completeness": 8.5,
      "accuracy": 9.0,
      "hallucinations": 10.0,
      "citation_quality": 7.5,
      "overall_quality": 8.5,
      "reasoning": "Brief explanation of scores (2-3 sentences)"
    }
  ],
  "winner": "provider_name"
}

**Important Judging Guidelines**:
- Score ALL providers objectively
- Use decimal scores (e.g., 8.5) for precision
- Winner = highest overall_quality score
- **Citation quality is CRITICAL**: Providers with missing/poor citations cannot score >7/10 overall
- **Quality over quantity**: 1 well-cited event beats 5 events without citations
- **Legal professional context**: Prioritize usability for lawyers (citations, accuracy, no hallucinations)
- Reasoning should explain key strengths/weaknesses (2-3 sentences)
- Return ONLY the JSON, no other text
"""

        return prompt

    def is_available(self) -> bool:
        """Check if judge is properly configured and available"""
        return bool(self.api_key)
