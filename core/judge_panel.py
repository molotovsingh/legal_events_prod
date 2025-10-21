#!/usr/bin/env python3
"""
3-Judge Panel Orchestrator for Robust Legal Event Extraction Evaluation

Coordinates GPT-5, Claude Opus 4.1, and Gemini 2.5 Pro judges to provide
consensus evaluation with inter-judge agreement analysis.
"""

import os
import logging
import statistics
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json

from .judges.gpt5_judge import GPT5Judge
from .judges.claude_opus_judge import ClaudeOpusJudge
from .judges.gemini_pro_judge import GeminiProJudge
from .judges.base_judge import JudgeResult, ProviderScore

logger = logging.getLogger(__name__)


@dataclass
class ConsensusScore:
    """Consensus scores for a single provider"""
    provider: str
    completeness: float  # median of 3 judges
    accuracy: float
    hallucinations: float
    citation_quality: float
    overall_quality: float
    score_variance: Dict[str, float]  # std dev per criterion


@dataclass
class InterJudgeAgreement:
    """Metrics for inter-judge agreement"""
    pearson_correlation: Dict[str, float]  # Pairwise correlations
    average_correlation: float
    score_std_dev_per_provider: Dict[str, Dict[str, float]]
    winner_consensus_percentage: float
    confidence_level: str  # "HIGH", "MEDIUM", "LOW"


@dataclass
class PanelResult:
    """Complete 3-judge panel evaluation result"""
    document_name: str
    timestamp: str
    judges_used: List[str]

    # Individual judge results
    individual_results: Dict[str, JudgeResult]

    # Consensus
    consensus_method: str
    consensus_scores: Dict[str, ConsensusScore]
    consensus_winner: str
    winner_votes: Dict[str, int]

    # Agreement analysis
    agreement: InterJudgeAgreement

    # Cost tracking
    total_cost: float
    total_thinking_tokens: int


class JudgePanel:
    """
    3-Judge Panel Orchestrator

    Coordinates multiple premium reasoning models for robust evaluation:
    - GPT-5 (OpenAI) with maximum thinking
    - Claude Opus 4.1 (Anthropic) with extended thinking
    - Gemini 2.5 Pro (Google) with built-in thinking

    Provides consensus scores and inter-judge agreement analysis.
    """

    def __init__(
        self,
        gpt5_api_key: str | None = None,
        claude_api_key: str | None = None,
        gemini_api_key: str | None = None
    ):
        """
        Initialize 3-judge panel

        Args:
            gpt5_api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            claude_api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            gemini_api_key: Google AI API key (defaults to GEMINI_API_KEY env var)
        """
        self.gpt5_api_key = gpt5_api_key or os.getenv("OPENAI_API_KEY")
        self.claude_api_key = claude_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")

        # Initialize judges
        self.judges: List[BaseJudge] = []

        if self.gpt5_api_key:
            try:
                judge = GPT5Judge(api_key=self.gpt5_api_key, reasoning_effort="high")
                self.judges.append(judge)
                logger.info("✅ GPT-5 judge initialized")
            except Exception as e:
                logger.warning(f"⚠️ GPT-5 judge failed to initialize: {e}")

        if self.claude_api_key:
            try:
                judge = ClaudeOpusJudge(api_key=self.claude_api_key, thinking_budget=10000, temperature=1.0)
                self.judges.append(judge)
                logger.info("✅ Claude Opus judge initialized")
            except Exception as e:
                logger.warning(f"⚠️ Claude Opus judge failed to initialize: {e}")

        if self.gemini_api_key:
            try:
                judge = GeminiProJudge(api_key=self.gemini_api_key)
                self.judges.append(judge)
                logger.info("✅ Gemini Pro judge initialized")
            except Exception as e:
                logger.warning(f"⚠️ Gemini Pro judge failed to initialize: {e}")

        if len(self.judges) < 2:
            raise ValueError(
                f"At least 2 judges required for panel (only {len(self.judges)} available). "
                "Check API keys: OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY"
            )

        logger.info(f"🎯 Judge Panel initialized with {len(self.judges)} judges")

    def judge_document(
        self,
        document_name: str,
        provider_outputs: Dict[str, List[Dict[str, Any]]]
    ) -> PanelResult:
        """
        Evaluate provider outputs using all 3 judges in parallel, then compute consensus.

        Args:
            document_name: Name of the document being evaluated
            provider_outputs: Dict mapping provider names to list of events

        Returns:
            PanelResult with individual results, consensus, and agreement analysis
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 3-JUDGE PANEL EVALUATION: {document_name}")
        logger.info(f"{'='*70}")
        logger.info(f"Judges: {[j.__class__.__name__ for j in self.judges]}")
        logger.info(f"Providers to evaluate: {list(provider_outputs.keys())}")

        # Run judges in parallel
        individual_results = self._run_judges_parallel(document_name, provider_outputs)

        # Calculate consensus scores
        consensus_scores = self._calculate_consensus_scores(individual_results, provider_outputs)

        # Determine winner by majority vote
        consensus_winner, winner_votes = self._determine_consensus_winner(individual_results)

        # Calculate inter-judge agreement
        agreement = self._calculate_agreement(individual_results, consensus_scores)

        # Calculate total cost and thinking tokens
        total_cost = sum(r.cost for r in individual_results.values())
        total_thinking_tokens = sum(r.thinking_tokens for r in individual_results.values())

        # Create panel result
        panel_result = PanelResult(
            document_name=document_name,
            timestamp=datetime.now().isoformat(),
            judges_used=[r.judge_name for r in individual_results.values()],
            individual_results=individual_results,
            consensus_method="median_scores_majority_winner",
            consensus_scores=consensus_scores,
            consensus_winner=consensus_winner,
            winner_votes=winner_votes,
            agreement=agreement,
            total_cost=total_cost,
            total_thinking_tokens=total_thinking_tokens
        )

        self._log_panel_summary(panel_result)

        return panel_result

    def _run_judges_parallel(
        self,
        document_name: str,
        provider_outputs: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, JudgeResult]:
        """Run all judges in parallel using ThreadPoolExecutor"""
        results = {}

        with ThreadPoolExecutor(max_workers=len(self.judges)) as executor:
            futures = {
                executor.submit(judge.judge_providers, document_name, provider_outputs): judge
                for judge in self.judges
            }

            for future in as_completed(futures):
                judge = futures[future]
                try:
                    result = future.result()
                    results[result.judge_name] = result
                    logger.info(f"✅ {result.judge_name} completed - winner: {result.winner}")
                except Exception as e:
                    logger.error(f"❌ {judge.__class__.__name__} failed: {e}")

        return results

    def _calculate_consensus_scores(
        self,
        individual_results: Dict[str, JudgeResult],
        provider_outputs: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, ConsensusScore]:
        """Calculate consensus scores using median aggregation"""
        consensus_scores = {}

        for provider in provider_outputs.keys():
            # Collect scores from all judges for this provider
            completeness_scores = []
            accuracy_scores = []
            hallucination_scores = []
            citation_scores = []
            overall_scores = []

            for judge_result in individual_results.values():
                for score in judge_result.provider_scores:
                    if score.provider == provider:
                        completeness_scores.append(score.completeness)
                        accuracy_scores.append(score.accuracy)
                        hallucination_scores.append(score.hallucinations)
                        citation_scores.append(score.citation_quality)
                        overall_scores.append(score.overall_quality)

            # Calculate median (robust to outliers)
            if completeness_scores:
                consensus_scores[provider] = ConsensusScore(
                    provider=provider,
                    completeness=statistics.median(completeness_scores),
                    accuracy=statistics.median(accuracy_scores),
                    hallucinations=statistics.median(hallucination_scores),
                    citation_quality=statistics.median(citation_scores),
                    overall_quality=statistics.median(overall_scores),
                    score_variance={
                        "completeness": statistics.stdev(completeness_scores) if len(completeness_scores) > 1 else 0.0,
                        "accuracy": statistics.stdev(accuracy_scores) if len(accuracy_scores) > 1 else 0.0,
                        "hallucinations": statistics.stdev(hallucination_scores) if len(hallucination_scores) > 1 else 0.0,
                        "citation_quality": statistics.stdev(citation_scores) if len(citation_scores) > 1 else 0.0,
                        "overall_quality": statistics.stdev(overall_scores) if len(overall_scores) > 1 else 0.0,
                    }
                )

        return consensus_scores

    def _determine_consensus_winner(
        self,
        individual_results: Dict[str, JudgeResult]
    ) -> Tuple[str, Dict[str, int]]:
        """Determine winner by majority vote (2/3 required)"""
        winner_votes = {}

        for judge_result in individual_results.values():
            winner = judge_result.winner
            winner_votes[winner] = winner_votes.get(winner, 0) + 1

        # Find winner with most votes
        consensus_winner = max(winner_votes.items(), key=lambda x: x[1])[0]

        return consensus_winner, winner_votes

    def _calculate_agreement(
        self,
        individual_results: Dict[str, JudgeResult],
        consensus_scores: Dict[str, ConsensusScore]
    ) -> InterJudgeAgreement:
        """Calculate inter-judge agreement metrics"""

        # Calculate pairwise Pearson correlations
        judge_names = list(individual_results.keys())
        correlations = {}

        for i in range(len(judge_names)):
            for j in range(i + 1, len(judge_names)):
                judge1 = judge_names[i]
                judge2 = judge_names[j]

                # Collect overall_quality scores for correlation
                scores1 = [s.overall_quality for s in individual_results[judge1].provider_scores]
                scores2 = [s.overall_quality for s in individual_results[judge2].provider_scores]

                if len(scores1) == len(scores2) and len(scores1) > 1:
                    corr = self._pearson_correlation(scores1, scores2)
                    correlations[f"{judge1}_vs_{judge2}"] = corr

        average_correlation = statistics.mean(correlations.values()) if correlations else 0.0

        # Score standard deviation per provider (from ConsensusScore.score_variance)
        score_std_dev = {
            provider: score.score_variance
            for provider, score in consensus_scores.items()
        }

        # Winner consensus percentage
        total_judges = len(individual_results)
        max_votes = max(len(individual_results), 1)
        winner_votes_count = 0
        for result in individual_results.values():
            if result.winner == list(individual_results.values())[0].winner:
                winner_votes_count += 1

        winner_consensus_pct = (winner_votes_count / total_judges) * 100 if total_judges > 0 else 0.0

        # Determine confidence level
        if average_correlation >= 0.8 and winner_consensus_pct == 100:
            confidence = "HIGH"
        elif average_correlation >= 0.6 and winner_consensus_pct >= 67:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return InterJudgeAgreement(
            pearson_correlation=correlations,
            average_correlation=average_correlation,
            score_std_dev_per_provider=score_std_dev,
            winner_consensus_percentage=winner_consensus_pct,
            confidence_level=confidence
        )

    @staticmethod
    def _pearson_correlation(x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        mean_x = statistics.mean(x)
        mean_y = statistics.mean(y)

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator_x = sum((x[i] - mean_x) ** 2 for i in range(n))
        denominator_y = sum((y[i] - mean_y) ** 2 for i in range(n))

        if denominator_x == 0 or denominator_y == 0:
            return 0.0

        return numerator / (denominator_x * denominator_y) ** 0.5

    def _log_panel_summary(self, result: PanelResult):
        """Log comprehensive panel evaluation summary"""
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 PANEL EVALUATION SUMMARY: {result.document_name}")
        logger.info(f"{'='*70}")

        logger.info(f"\n🏆 CONSENSUS WINNER: {result.consensus_winner}")
        logger.info(f"   Vote Distribution: {result.winner_votes}")
        logger.info(f"   Winner Consensus: {result.agreement.winner_consensus_percentage:.1f}%")

        logger.info(f"\n📈 INTER-JUDGE AGREEMENT:")
        logger.info(f"   Average Correlation: {result.agreement.average_correlation:.3f}")
        for pair, corr in result.agreement.pearson_correlation.items():
            logger.info(f"   {pair}: {corr:.3f}")
        logger.info(f"   Confidence Level: {result.agreement.confidence_level}")

        logger.info(f"\n💰 COST ANALYSIS:")
        logger.info(f"   Total Cost: ${result.total_cost:.4f}")
        logger.info(f"   Total Thinking Tokens: {result.total_thinking_tokens:,}")

        for judge_name, judge_result in result.individual_results.items():
            logger.info(f"   {judge_name}: ${judge_result.cost:.4f} ({judge_result.thinking_tokens:,} thinking tokens)")

        logger.info(f"\n{'='*70}\n")

    def save_results(self, result: PanelResult, output_path: str):
        """Save panel results to JSON file"""
        # Convert dataclasses to dicts
        output_data = {
            "document_name": result.document_name,
            "timestamp": result.timestamp,
            "judges_used": result.judges_used,
            "individual_results": {
                judge_name: {
                    "judge_name": jr.judge_name,
                    "model": jr.model,
                    "winner": jr.winner,
                    "cost": jr.cost,
                    "thinking_tokens": jr.thinking_tokens,
                    "scores": [asdict(score) for score in jr.provider_scores]
                }
                for judge_name, jr in result.individual_results.items()
            },
            "consensus": {
                "method": result.consensus_method,
                "winner": result.consensus_winner,
                "winner_votes": result.winner_votes,
                "scores": {
                    provider: asdict(score)
                    for provider, score in result.consensus_scores.items()
                }
            },
            "agreement": asdict(result.agreement),
            "total_cost": result.total_cost,
            "total_thinking_tokens": result.total_thinking_tokens
        }

        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"✅ Panel results saved to: {output_path}")
