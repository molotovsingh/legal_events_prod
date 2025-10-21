"""
3-Judge Panel System for Legal Event Extraction Evaluation

This module provides a robust evaluation system using three premium reasoning models:
- GPT-5 (OpenAI) with maximum thinking
- Claude Opus 4.1 (Anthropic) with extended thinking
- Gemini 2.5 Pro (Google) with built-in thinking

Each judge independently scores provider outputs on standardized criteria,
then consensus mechanism aggregates results with inter-judge agreement analysis.
"""

from .base_judge import BaseJudge, JudgeResult, ProviderScore

__all__ = ["BaseJudge", "JudgeResult", "ProviderScore"]
