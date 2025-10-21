"""
Prompt builder utilities for small-model document classification.

The helper centralizes label taxonomy, few-shot exemplars, and output schema
instructions so API-backed classifiers (Claude, Gemini, GPT-4o-mini, etc.)
can reuse a consistent prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import List


LABEL_DEFINITIONS: List[str] = [
    "`Agreement/Contract`: Executed agreements, amendments, statements of work.",
    "`Correspondence`: Emails, letters, notices exchanged between parties.",
    "`Pleading`: Complaints, written statements, affidavits, responses to court filings.",
    "`Motion/Application`: Procedural requests such as extensions, dismissals, injunctions.",
    "`Court Order/Judgment`: Judicial orders, opinions, decrees, bench rulings.",
    "`Evidence/Exhibit`: Supporting materials (annexures, transcripts, expert reports).",
    "`Case Summary/Chronology`: Narrative timelines, case briefs, status reports.",
    "`Other`: Documents that do not fit the categories above.",
]


FEWSHOT_EXAMPLES = dedent(
    """
    Example 1:
    Document Title: "Email: Request for Updated Discovery Responses"
    Excerpt: "Counsel, per Rule 26 we require updated responses by 04/10/2024."
    Output: {"classes": ["Correspondence"], "primary": "Correspondence", "confidence": 0.82, "rationale": "Email between counsel requesting updated discovery responses."}

    Example 2:
    Document Title: "Delhi High Court Order - Interim Injunction"
    Excerpt: "Ordered that the defendant is restrained from using the mark pending trial."
    Output: {"classes": ["Court Order/Judgment"], "primary": "Court Order/Judgment", "confidence": 0.9, "rationale": "Issued by a court granting injunctive relief."}

    Example 3:
    Document Title: "Implementation Roadmap and Dispute Timeline"
    Excerpt: "Summarises milestones, breach notices, and the current litigation status."
    Output: {"classes": ["Case Summary/Chronology"], "primary": "Case Summary/Chronology", "confidence": 0.78, "rationale": "Narrative overview of events and procedural posture."}
    """
).strip()


@dataclass(frozen=True)
class PromptPayload:
    """Structured prompt output consumed by API callers."""

    system_message: str
    user_message: str
    prompt_version: str


def build_classification_prompt(document_title: str, document_excerpt: str, prompt_version: str = "v1") -> PromptPayload:
    """
    Assemble a consistent prompt for API-based document classification.

    Args:
        document_title: Human-readable title or file name.
        document_excerpt: Trimmed text that represents the document content.
        prompt_version: Semantic version string to track prompt changes.

    Returns:
        PromptPayload with system message, user message, and version metadata.
    """
    system_message = (
        "You classify legal documents. "
        "Respond with strict JSON matching this schema: "
        '{"classes": [<one or more labels>], "primary": "<single label>", "confidence": <0-1 float>, "rationale": "<short reason>"} '
        "Use only the labels provided. If uncertain, include 'Other'."
    )

    label_block = "\n".join(f"- {definition}" for definition in LABEL_DEFINITIONS)

    user_message = dedent(
        f"""
        Review the document below and return valid JSON only.

        Labels:
        {label_block}

        {FEWSHOT_EXAMPLES}

        Document Title: {document_title.strip()}
        Document Excerpt:
        {document_excerpt.strip()}
        """
    ).strip()

    return PromptPayload(
        system_message=system_message,
        user_message=user_message,
        prompt_version=prompt_version,
    )
