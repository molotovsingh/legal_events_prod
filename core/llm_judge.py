#!/usr/bin/env python3
"""
LLM-as-Judge Evaluation System for Provider Comparison

Uses GPT-4o-mini to compare provider outputs and score on multiple criteria:
- Completeness: Are all legal events captured?
- Accuracy: Are dates, parties, facts correct?
- Hallucinations: Any invented facts?
- Citation Quality: Are citations accurate?
- Overall Quality: Overall usability for legal professionals

No ground truth needed - compares provider outputs directly.
"""

import os
import json
import logging
from typing import List, Dict, Any
from dataclasses import dataclass, asdict

from openai import OpenAI

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
class JudgeComparison:
    """Comparison of all providers for one document"""
    document_name: str
    provider_scores: List[ProviderScore]
    winner: str  # Provider with highest overall quality
    timestamp: str


class LLMJudge:
    """
    LLM-as-judge evaluator for legal event extraction quality

    Uses GPT-4o-mini to score provider outputs on multiple criteria
    without requiring ground truth annotations.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0
    ):
        """
        Initialize LLM judge

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use for judging (gpt-4o-mini recommended)
            temperature: Temperature for generation (0.0 for consistency)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required for LLM judge. Set OPENAI_API_KEY environment variable.")

        self.model = model
        self.temperature = temperature
        self.client = OpenAI(api_key=self.api_key)

        logger.info(f"LLM Judge initialized with model: {model}")

    def _build_judge_prompt(
        self,
        document_name: str,
        provider_outputs: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """
        Build comprehensive judge prompt comparing all provider outputs

        Args:
            document_name: Name of the document being evaluated
            provider_outputs: Dict mapping provider names to list of extracted events

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

    def judge_providers(
        self,
        document_name: str,
        provider_outputs: Dict[str, List[Dict[str, Any]]]
    ) -> JudgeComparison:
        """
        Compare provider outputs and score them

        Args:
            document_name: Name of document being evaluated
            provider_outputs: Dict mapping provider names to list of events

        Returns:
            JudgeComparison with scores for all providers
        """
        logger.info(f"Judging providers for document: {document_name}")
        logger.info(f"Providers to compare: {list(provider_outputs.keys())}")

        # Build prompt
        prompt = self._build_judge_prompt(document_name, provider_outputs)

        # Call OpenAI with JSON mode
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
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )

            # Parse response
            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            logger.info(f"Judge response received: {len(result.get('providers', []))} providers scored")

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

            # Create comparison
            comparison = JudgeComparison(
                document_name=document_name,
                provider_scores=provider_scores,
                winner=result.get("winner", "unknown"),
                timestamp=response.created.__str__()
            )

            logger.info(f"Winner for {document_name}: {comparison.winner}")

            return comparison

        except Exception as e:
            logger.error(f"Error during judging: {e}")
            raise

    def judge_multiple_documents(
        self,
        document_results: Dict[str, Dict[str, List[Dict[str, Any]]]]
    ) -> List[JudgeComparison]:
        """
        Judge provider outputs across multiple documents

        Args:
            document_results: Dict mapping document names to provider outputs
                Format: {
                    "doc1.pdf": {
                        "provider1": [event1, event2, ...],
                        "provider2": [event1, event2, ...],
                    },
                    "doc2.pdf": {...}
                }

        Returns:
            List of JudgeComparison objects, one per document
        """
        comparisons = []

        for doc_name, provider_outputs in document_results.items():
            logger.info(f"\n{'='*70}")
            logger.info(f"Judging document: {doc_name}")
            logger.info(f"{'='*70}")

            comparison = self.judge_providers(doc_name, provider_outputs)
            comparisons.append(comparison)

        return comparisons

    def aggregate_scores(
        self,
        comparisons: List[JudgeComparison]
    ) -> Dict[str, Dict[str, float]]:
        """
        Aggregate scores across all documents for each provider

        Args:
            comparisons: List of JudgeComparison objects from multiple documents

        Returns:
            Dict mapping provider names to average scores
            Format: {
                "provider1": {
                    "completeness": 8.5,
                    "accuracy": 9.0,
                    ...
                    "win_rate": 0.6  # Fraction of documents where this provider won
                }
            }
        """
        provider_scores = {}

        for comparison in comparisons:
            for score in comparison.provider_scores:
                if score.provider not in provider_scores:
                    provider_scores[score.provider] = {
                        "completeness": [],
                        "accuracy": [],
                        "hallucinations": [],
                        "citation_quality": [],
                        "overall_quality": [],
                        "wins": 0,
                        "total_docs": 0
                    }

                provider_scores[score.provider]["completeness"].append(score.completeness)
                provider_scores[score.provider]["accuracy"].append(score.accuracy)
                provider_scores[score.provider]["hallucinations"].append(score.hallucinations)
                provider_scores[score.provider]["citation_quality"].append(score.citation_quality)
                provider_scores[score.provider]["overall_quality"].append(score.overall_quality)
                provider_scores[score.provider]["total_docs"] += 1

                if score.provider == comparison.winner:
                    provider_scores[score.provider]["wins"] += 1

        # Calculate averages
        aggregated = {}
        for provider, scores in provider_scores.items():
            aggregated[provider] = {
                "completeness": sum(scores["completeness"]) / len(scores["completeness"]),
                "accuracy": sum(scores["accuracy"]) / len(scores["accuracy"]),
                "hallucinations": sum(scores["hallucinations"]) / len(scores["hallucinations"]),
                "citation_quality": sum(scores["citation_quality"]) / len(scores["citation_quality"]),
                "overall_quality": sum(scores["overall_quality"]) / len(scores["overall_quality"]),
                "win_rate": scores["wins"] / scores["total_docs"],
                "total_wins": scores["wins"],
                "total_docs": scores["total_docs"]
            }

        return aggregated

    def identify_champions(
        self,
        aggregated_scores: Dict[str, Dict[str, float]]
    ) -> Dict[str, str]:
        """
        Identify champion providers by category

        Args:
            aggregated_scores: Output from aggregate_scores()

        Returns:
            Dict mapping categories to champion provider names
        """
        champions = {}

        # Overall quality champion
        champions["overall_quality"] = max(
            aggregated_scores.items(),
            key=lambda x: x[1]["overall_quality"]
        )[0]

        # Completeness champion
        champions["completeness"] = max(
            aggregated_scores.items(),
            key=lambda x: x[1]["completeness"]
        )[0]

        # Accuracy champion
        champions["accuracy"] = max(
            aggregated_scores.items(),
            key=lambda x: x[1]["accuracy"]
        )[0]

        # No hallucinations champion
        champions["no_hallucinations"] = max(
            aggregated_scores.items(),
            key=lambda x: x[1]["hallucinations"]
        )[0]

        # Citation quality champion
        champions["citation_quality"] = max(
            aggregated_scores.items(),
            key=lambda x: x[1]["citation_quality"]
        )[0]

        # Win rate champion
        champions["win_rate"] = max(
            aggregated_scores.items(),
            key=lambda x: x[1]["win_rate"]
        )[0]

        return champions

    def export_results(
        self,
        comparisons: List[JudgeComparison],
        aggregated_scores: Dict[str, Dict[str, float]],
        champions: Dict[str, str],
        output_path: str
    ):
        """
        Export complete evaluation results to JSON

        Args:
            comparisons: List of per-document comparisons
            aggregated_scores: Aggregated scores across documents
            champions: Champion providers by category
            output_path: Path to save JSON file
        """
        export_data = {
            "per_document_comparisons": [
                {
                    "document": comp.document_name,
                    "winner": comp.winner,
                    "scores": [asdict(score) for score in comp.provider_scores]
                }
                for comp in comparisons
            ],
            "aggregated_scores": aggregated_scores,
            "champions": champions,
            "total_documents": len(comparisons)
        }

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Results exported to {output_path}")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example provider outputs
    sample_outputs = {
        "doc1.pdf": {
            "openai": [
                {
                    "date": "2024-01-15",
                    "event_particulars": "Contract signed between parties A and B",
                    "citation": "Contract § 1.1"
                }
            ],
            "langextract": [
                {
                    "date": "2024-01-15",
                    "event_particulars": "Contract execution",
                    "citation": ""
                },
                {
                    "date": "2024-01-20",
                    "event_particulars": "Payment due date",
                    "citation": ""
                }
            ]
        }
    }

    judge = LLMJudge()
    comparisons = judge.judge_multiple_documents(sample_outputs)
    aggregated = judge.aggregate_scores(comparisons)
    champions = judge.identify_champions(aggregated)

    print("\nChampions:")
    for category, provider in champions.items():
        print(f"  {category}: {provider}")
