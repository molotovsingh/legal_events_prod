"""
LangExtract Few-Shot Examples for Legal Events Extraction
Centralized example definitions to improve maintainability and configurability
"""

import logging
from typing import List, Optional

try:
    import langextract as lx
    LANGEXTRACT_AVAILABLE = True
except ImportError:
    LANGEXTRACT_AVAILABLE = False
    lx = None

logger = logging.getLogger(__name__)


def create_legal_events_examples() -> List:
    """
    Create standard legal events examples for LangExtract prompts

    Returns:
        List of LangExtract ExampleData instances, or empty list if LangExtract unavailable
    """
    if not LANGEXTRACT_AVAILABLE:
        logger.error("❌ LangExtract not available - returning empty examples list")
        return []

    try:
        examples = [
            lx.data.ExampleData(
                text="On January 15, 2024, the plaintiff filed a motion to dismiss pursuant to Rule 12(b)(6) of the Federal Rules of Civil Procedure.",
                extractions=[
                    lx.data.Extraction(
                        extraction_class="legal_filing",
                        extraction_text="Plaintiff filed motion to dismiss on January 15, 2024",
                        attributes={
                            "event_particulars": "On January 15, 2024, the plaintiff filed a motion to dismiss the complaint pursuant to Rule 12(b)(6) of the Federal Rules of Civil Procedure. This motion challenges the legal sufficiency of the complaint, arguing that the plaintiff has failed to state a claim upon which relief can be granted. The filing of this motion suspends the defendant's obligation to file an answer until the court rules on the motion. If granted, the motion would result in dismissal of some or all claims without the need for further discovery or trial proceedings.",
                            "citation": "Fed. R. Civ. P. 12(b)(6)",
                            "document_reference": "",
                            "date": "2024-01-15"
                        }
                    )
                ]
            ),
            lx.data.ExampleData(
                text="The contract executed on March 3, 2023, between ABC Corp and XYZ LLC, with an effective date of April 1, 2023, terminates on March 31, 2025.",
                extractions=[
                    lx.data.Extraction(
                        extraction_class="contract_execution",
                        extraction_text="Contract execution between ABC Corp and XYZ LLC on March 3, 2023",
                        attributes={
                            "event_particulars": "On March 3, 2023, ABC Corp and XYZ LLC executed a comprehensive business agreement that becomes effective on April 1, 2023. The contract establishes the terms and conditions for their ongoing business relationship and includes specific performance obligations for both parties. The agreement is structured with a definitive termination date of March 31, 2025, providing a two-year operational period. This execution represents the culmination of negotiations between the corporate entities and creates binding legal obligations under the agreed terms.",
                            "citation": "",
                            "document_reference": "",
                            "date": "2023-03-03"
                        }
                    )
                ]
            ),
            lx.data.ExampleData(
                text="Court hearing scheduled for discovery disputes on February 10, 2024 at 2:00 PM pursuant to Local Rule 37.1.",
                extractions=[
                    lx.data.Extraction(
                        extraction_class="court_hearing",
                        extraction_text="Court hearing scheduled for discovery disputes on February 10, 2024 at 2:00 PM",
                        attributes={
                            "event_particulars": "A court hearing has been scheduled for February 10, 2024 at 2:00 PM to address ongoing discovery disputes between the parties. This hearing is being convened pursuant to Local Rule 37.1, which governs discovery motion practice and requires judicial intervention when parties cannot resolve discovery disagreements through meet-and-confer efforts. The hearing will allow both parties to present their positions regarding the disputed discovery requests and will enable the court to issue binding rulings on the scope and timing of discovery obligations.",
                            "citation": "Local Rule 37.1",
                            "document_reference": "",
                            "date": "2024-02-10"
                        }
                    )
                ]
            )
        ]

        logger.info(f"✅ Created {len(examples)} legal events examples")
        return examples

    except Exception as e:
        logger.error(f"❌ Failed to create legal events examples: {e}")
        return []


def get_legal_events_examples() -> List:
    """
    Get legal events examples with error handling

    Returns:
        List of examples or empty list on failure
    """
    try:
        return create_legal_events_examples()
    except Exception as e:
        logger.error(f"❌ Error loading legal events examples: {e}")
        return []