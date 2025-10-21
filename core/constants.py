"""
Core Constants - Shared values across the legal events pipeline
"""

import os

# Five-column headers for legal events table - Date added as column 2
FIVE_COLUMN_HEADERS = ["No", "Date", "Event Particulars", "Citation", "Document Reference"]

# Internal field names used in processing (matching column order)
INTERNAL_FIELDS = ["number", "date", "event_particulars", "citation", "document_reference"]

# Default values for failed extractions
DEFAULT_NO_CITATION = "No citation available"
DEFAULT_NO_REFERENCE = "Unknown document"
DEFAULT_NO_PARTICULARS = "Event details not available"
DEFAULT_NO_DATE = "Date not available"

# ============================================================================
# LEGAL EVENTS PROMPT VERSIONS
# ============================================================================

# V1: Current production prompt (baseline)
LEGAL_EVENTS_PROMPT_V1 = """Extract legal events from this document. For each event, you must return exactly four JSON keys:

1. "event_particulars" - REQUIRED: Provide a complete description (2-8 sentences as appropriate) of what happened, including relevant context, parties involved, procedural background, implications, and any important details. Use verbatim or paraphrased text from the document. NEVER leave this field empty.
2. "citation" - Exact legal authority cited in the event (statute, rule, case, docket, etc.). Copy the verbatim reference from the document. Use empty string "" when no explicit legal citation appears.
3. "document_reference" - Leave as empty string "" (will be filled automatically with source filename)
4. "date" - Specific date mentioned (use empty string "" if no date is found)

CRITICAL REQUIREMENTS:
- "event_particulars" must ALWAYS contain meaningful, comprehensive text - provide a full description with sufficient context for legal analysis
- Use 2-8 sentences as appropriate to capture the complete legal significance and context of each event
- Include relevant background, procedural details, party information, and implications when available in the document
- Use empty strings ("") for missing values EXCEPT for "event_particulars" which must never be empty
- The "citation" field should only contain actual legal references mentioned in the text
- Always use empty string "" for "document_reference" - the system will populate it with the correct filename
- Return all four keys for every extraction

PROHIBITION: Never return an extraction with blank or empty "event_particulars" - every event must have a comprehensive, contextual description.

Extract all legally significant events, proceedings, filings, agreements, and deadlines."""

# V2: Enhanced prompt with improved granularity and recall (2025-10-11)
LEGAL_EVENTS_PROMPT_V2 = """Extract legal events from this document. For each event, you must return exactly four JSON keys:

1. "event_particulars" – REQUIRED: Provide a complete description (1–8 sentences as appropriate) of what happened, including context, parties, procedural posture, implications, and any relevant follow-up. Use verbatim or paraphrased text from the document. NEVER leave this field empty.
2. "citation" – Exact legal authority cited in the event (statute, rule, case, docket, etc.). Copy the verbatim reference from the document. Use the empty string "" when no explicit citation appears.
3. "document_reference" – Leave as the empty string "" (the pipeline fills the filename automatically).
4. "date" – Specific date or date range mentioned. Use the empty string "" only if no date is provided.

CRITICAL REQUIREMENTS:
- Create a SEPARATE event for every distinct dated action or milestone. Do not merge multiple dated actions even if they share a paragraph or storyline (e.g., meetings on July 5, July 10, and July 20 must produce three events if they represent distinct actions).
- Include interim milestones such as inspections, negotiation rounds, warnings, counter-offers, site visits, and status emails—not just formal filings or court orders.
- When the source states that only limited details are available (e.g., "response details not provided"), still create an event summarizing what is known and explicitly note the missing pieces.
- "event_particulars" must ALWAYS contain meaningful, contextual text; describe the action, participants, legal significance, and consequences.
- Use empty strings ("") for missing values EXCEPT for "event_particulars".
- The "citation" field should contain only actual legal references; use "" when none are present.
- Return all four keys for every event, in valid JSON form.

PROHIBITION: Never return an event with blank or superficial "event_particulars". Capture every legally significant development chronologically."""

# Active prompt selection (feature flag)
# Set USE_ENHANCED_PROMPT=true in .env to use V2, otherwise defaults to V1
LEGAL_EVENTS_PROMPT = (
    LEGAL_EVENTS_PROMPT_V2 if os.getenv("USE_ENHANCED_PROMPT", "false").lower() == "true"
    else LEGAL_EVENTS_PROMPT_V1
)

# ============================================================================
# DOCUMENT CLASSIFICATION PROMPT - Multi-Label Support
# ============================================================================

LEGAL_CLASSIFICATION_MULTILABEL_PROMPT = """You classify legal documents. Respond with strict JSON matching this schema:
{
  "classes": [<one or more labels>],
  "primary": "<single label>",
  "confidence": <0-1 float>,
  "rationale": "<short reason>"
}

Use only the labels provided. Return multiple labels in "classes" when appropriate. If uncertain, include "Other".

Available Labels:
- Agreement/Contract: Executed agreements, amendments, statements of work
- Correspondence: Emails, letters, notices exchanged between parties
- Pleading: Complaints, petitions, answers, motions filed with courts
- Motion/Application: Requests for court action or relief
- Court Order/Judgment: Judicial orders, opinions, decrees, bench rulings
- Evidence/Exhibit: Supporting materials (annexures, transcripts, expert reports, financial records)
- Case Summary/Chronology: Narrative timelines, case briefs, status reports
- Other: Documents that do not fit the categories above

Examples:

Example 1:
Document Title: "Request for Updated Discovery Responses"
Excerpt: "Dear Counsel, Please provide updated responses to our interrogatories by March 15."
Output: {"classes": ["Correspondence"], "primary": "Correspondence", "confidence": 0.82, "rationale": "Email between counsel requesting updated discovery responses."}

Example 2:
Document Title: "Delhi High Court Order - Interim Injunction"
Excerpt: "Ordered that the defendant is restrained from using the mark pending trial."
Output: {"classes": ["Court Order/Judgment"], "primary": "Court Order/Judgment", "confidence": 0.90, "rationale": "Issued by a court granting injunctive relief."}

Example 3:
Document Title: "Implementation Roadmap and Dispute Timeline"
Excerpt: "Summarises milestones, breach notices, and the current litigation status."
Output: {"classes": ["Case Summary/Chronology"], "primary": "Case Summary/Chronology", "confidence": 0.78, "rationale": "Narrative overview of events and procedural posture."}

Example 4 (Multi-label):
Document Title: "Email Forwarding Executed Amendment"
Excerpt: "Attached is the signed Amendment #2 to our Master Services Agreement dated January 5, 2024."
Output: {"classes": ["Correspondence", "Agreement/Contract", "Evidence/Exhibit"], "primary": "Agreement/Contract", "confidence": 0.85, "rationale": "Email (correspondence) containing executed agreement that serves as exhibit evidence."}

Review the document below and return valid JSON only."""

# V2: Optimized prompt with explicit single-label default (2025-10-14)
LEGAL_CLASSIFICATION_MULTILABEL_PROMPT_V2 = """You classify legal documents. Respond with strict JSON matching this schema:
{
  "classes": [<one or more labels>],
  "primary": "<single label>",
  "confidence": <0-1 float>,
  "rationale": "<short reason>"
}

Available Labels:
- Agreement/Contract: Executed agreements, amendments, statements of work
- Correspondence: Emails, letters, notices exchanged between parties
- Pleading: Complaints, petitions, answers, motions filed with courts
- Motion/Application: Requests for court action or relief
- Court Order/Judgment: Judicial orders, opinions, decrees, bench rulings
- Evidence/Exhibit: Supporting materials (annexures, transcripts, expert reports, financial records)
- Case Summary/Chronology: Narrative timelines, case briefs, status reports
- Other: Documents that do not fit the categories above

CRITICAL RULES:

1. DEFAULT TO SINGLE-LABEL
   - Most documents have ONE primary purpose
   - Use single-label unless multiple labels are clearly justified
   - Do NOT hedge by adding extra labels "just in case"

2. WHEN TO USE MULTIPLE LABELS (rare - requires explicit justification):
   - Email forwarding an executed contract → Correspondence + Agreement/Contract
   - Court order with embedded evidence → Court Order/Judgment + Evidence/Exhibit
   - Pleading that also serves as formal notice → Pleading + Correspondence
   - Document serves multiple distinct legal functions simultaneously

3. WHEN TO USE SINGLE LABEL (default):
   - Document has one clear primary purpose
   - Additional functions are incidental or future possibilities
   - You can reasonably describe it with one label
   - When uncertain between labels, pick the strongest one

4. PRIMARY SELECTION RULES:
   - The "primary" field MUST be the first label in "classes" array
   - Primary = the document's core legal function
   - Other labels (if any) are secondary attributes

5. "OTHER" LABEL RESTRICTIONS:
   - Use "Other" ONLY when document truly doesn't fit any valid label
   - NEVER combine "Other" with valid labels (e.g., ["Other", "Correspondence"] is forbidden)
   - If ANY valid label applies, use that label instead of "Other"

Examples:

Example 1 (Single-label - default case):
Document Title: "Request for Updated Discovery Responses"
Excerpt: "Dear Counsel, Please provide updated responses to our interrogatories by March 15."
Output: {"classes": ["Correspondence"], "primary": "Correspondence", "confidence": 0.82, "rationale": "Email between counsel requesting discovery responses. Single clear purpose."}

Example 2 (Single-label - court document):
Document Title: "Delhi High Court Order - Interim Injunction"
Excerpt: "Ordered that the defendant is restrained from using the mark pending trial."
Output: {"classes": ["Court Order/Judgment"], "primary": "Court Order/Judgment", "confidence": 0.90, "rationale": "Judicial order granting injunctive relief. Single primary function."}

Example 3 (Single-label - narrative summary):
Document Title: "Implementation Roadmap and Dispute Timeline"
Excerpt: "Summarises milestones, breach notices, and the current litigation status."
Output: {"classes": ["Case Summary/Chronology"], "primary": "Case Summary/Chronology", "confidence": 0.78, "rationale": "Narrative overview of case events. Single documentary purpose."}

Example 4 (Multi-label - RARE case with explicit justification):
Document Title: "Email Forwarding Executed Amendment"
Excerpt: "Attached is the signed Amendment #2 to our Master Services Agreement dated January 5, 2024."
Output: {"classes": ["Agreement/Contract", "Correspondence", "Evidence/Exhibit"], "primary": "Agreement/Contract", "confidence": 0.85, "rationale": "Multi-label justified: Contains executed contract (primary), transmitted via correspondence (secondary), serves as exhibit evidence (tertiary). All three functions are explicit and distinct."}

Example 5 (Counter-example - DO NOT use multi-label here):
Document Title: "Motion for Summary Judgment"
Excerpt: "Plaintiff moves for summary judgment. This motion will be filed with the court and served on opposing counsel."
Output: {"classes": ["Motion/Application"], "primary": "Motion/Application", "confidence": 0.88, "rationale": "Single-label correct. While document mentions filing and service, its PRIMARY purpose is the motion itself. Filing/service are procedural steps, not distinct legal functions."}

Review the document below and return valid JSON only."""

# API configuration
REQUIRED_ENV_VARS = ["GEMINI_API_KEY"]
DEFAULT_MODEL = "gemini-2.5-flash"  # Google's recommended model for LangExtract (GA since June 2025)

# ============================================================================
# MODEL IDENTIFIERS - Premium Models for Ground Truth Creation
# ============================================================================

# OpenAI Models
GPT_4O_MINI = "gpt-4o-mini"
GPT_4O = "gpt-4o"
GPT_5 = "gpt-5"
GPT_5_MINI = "gpt-5-mini"
GPT_5_NANO = "gpt-5-nano"

# Google Gemini Models
GEMINI_2_0_FLASH = "gemini-2.0-flash"
GEMINI_2_5_FLASH = "gemini-2.5-flash"
GEMINI_2_5_PRO = "gemini-2.5-pro"

# Anthropic Claude Models
CLAUDE_3_HAIKU = "claude-3-haiku-20240307"
CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20241022"
CLAUDE_SONNET_4_5 = "claude-sonnet-4-5"
CLAUDE_OPUS_4 = "claude-opus-4"
CLAUDE_OPUS_4_1 = "claude-opus-4-1"

# DeepSeek Models
DEEPSEEK_CHAT = "deepseek-chat"
DEEPSEEK_R1_DISTILL = "deepseek/deepseek-r1-distill-llama-70b"
