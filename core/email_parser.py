"""
Email Parser Module - Stdlib-Only .EML File Processing
Extracts clean text, headers, and attachment summaries from .eml files
"""

import logging
from pathlib import Path
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from typing import Dict, Tuple, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class HTMLTextExtractor(HTMLParser):
    """
    Extracts plain text from HTML email content
    Strips tags while preserving text content
    """

    def __init__(self):
        super().__init__()
        self.text_parts: List[str] = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        """Track script/style tags to skip their content"""
        if tag in ('script', 'style'):
            if tag == 'script':
                self.in_script = True
            else:
                self.in_style = True
        elif tag == 'br':
            self.text_parts.append('\n')
        elif tag == 'p':
            self.text_parts.append('\n\n')

    def handle_endtag(self, tag):
        """Reset script/style tracking"""
        if tag == 'script':
            self.in_script = False
        elif tag == 'style':
            self.in_style = False
        elif tag in ('p', 'div', 'li'):
            self.text_parts.append('\n')

    def handle_data(self, data):
        """Extract text content, skip script/style"""
        if not self.in_script and not self.in_style:
            text = data.strip()
            if text:
                self.text_parts.append(text + ' ')

    def get_text(self) -> str:
        """Return extracted plain text"""
        return ''.join(self.text_parts).strip()


@dataclass
class ParsedEmail:
    """
    Structured email data with clean text and metadata
    """
    subject: str
    from_addr: str
    to_addr: str
    cc_addr: str
    date: str
    message_id: str
    body_text: str
    body_format: str  # 'plain', 'html', or 'multipart'
    has_attachments: bool
    attachment_count: int
    attachment_summary: str


def extract_plain_text(message) -> Tuple[str, str]:
    """
    Extract plain text from email message part

    Args:
        message: email.message.Message object

    Returns:
        Tuple of (text_content, format_type)
    """
    # Try to get plain text part
    plain_part = message.get_body(preferencelist=('plain',))
    if plain_part:
        try:
            text = plain_part.get_content()
            return text, 'plain'
        except Exception as e:
            logger.warning(f"Failed to decode plain text part: {e}")

    # Fallback to HTML part
    html_part = message.get_body(preferencelist=('html',))
    if html_part:
        try:
            html_content = html_part.get_content()
            # Strip HTML tags
            parser = HTMLTextExtractor()
            parser.feed(html_content)
            text = parser.get_text()
            return text, 'html'
        except Exception as e:
            logger.warning(f"Failed to decode HTML part: {e}")
            return "", 'html'

    # No text or HTML part found
    return "", 'multipart'


def generate_attachment_summary(message) -> Tuple[bool, int, str]:
    """
    Generate human-readable attachment summary

    Args:
        message: email.message.Message object

    Returns:
        Tuple of (has_attachments, count, summary_text)
    """
    attachments = []

    for part in message.walk():
        # Check if part is an attachment
        if part.get_content_disposition() == 'attachment':
            filename = part.get_filename() or 'unnamed'

            # Get size
            try:
                payload = part.get_payload(decode=True)
                size_kb = len(payload) / 1024 if payload else 0
                attachments.append(f"[Attachment: {filename} ({size_kb:.1f}KB)]")
            except Exception:
                attachments.append(f"[Attachment: {filename}]")

    if attachments:
        summary = "\n\nAttachments:\n" + "\n".join(attachments)
        return True, len(attachments), summary
    else:
        return False, 0, ""


def parse_email_file(file_path: Path) -> ParsedEmail:
    """
    Parse .eml file and extract structured data

    Args:
        file_path: Path to .eml file

    Returns:
        ParsedEmail object with clean text and metadata

    Raises:
        Exception: If file cannot be parsed
    """
    try:
        # Read and parse email using BytesParser (handles all encodings)
        with open(file_path, 'rb') as f:
            message = BytesParser(policy=policy.default).parse(f)

        # Extract headers (with fallbacks for missing fields)
        subject = message.get('subject', '') or ''
        from_addr = message.get('from', '') or ''
        to_addr = message.get('to', '') or ''
        cc_addr = message.get('cc', '') or ''
        date = message.get('date', '') or ''
        message_id = message.get('message-id', '') or ''

        # Extract body text
        body_text, body_format = extract_plain_text(message)

        # Get attachment summary
        has_attachments, attachment_count, attachment_summary = generate_attachment_summary(message)

        # Combine body text with attachment summary
        full_body = body_text + attachment_summary if attachment_summary else body_text

        return ParsedEmail(
            subject=subject,
            from_addr=from_addr,
            to_addr=to_addr,
            cc_addr=cc_addr,
            date=date,
            message_id=message_id,
            body_text=full_body,
            body_format=body_format,
            has_attachments=has_attachments,
            attachment_count=attachment_count,
            attachment_summary=attachment_summary
        )

    except Exception as e:
        logger.error(f"Failed to parse email file {file_path.name}: {e}")
        raise


def format_email_as_text(parsed_email: ParsedEmail) -> str:
    """
    Format parsed email as clean text for event extraction

    Args:
        parsed_email: ParsedEmail object

    Returns:
        Formatted text string
    """
    lines = []

    # Email headers
    if parsed_email.subject:
        lines.append(f"Subject: {parsed_email.subject}")
    if parsed_email.from_addr:
        lines.append(f"From: {parsed_email.from_addr}")
    if parsed_email.to_addr:
        lines.append(f"To: {parsed_email.to_addr}")
    if parsed_email.cc_addr:
        lines.append(f"Cc: {parsed_email.cc_addr}")
    if parsed_email.date:
        lines.append(f"Date: {parsed_email.date}")

    # Separator
    lines.append("")

    # Body
    lines.append(parsed_email.body_text)

    return "\n".join(lines)


def get_email_metadata(parsed_email: ParsedEmail) -> Dict:
    """
    Extract email metadata for ExtractedDocument.metadata

    Args:
        parsed_email: ParsedEmail object

    Returns:
        Dictionary of email-specific metadata
    """
    return {
        "email_headers": {
            "subject": parsed_email.subject,
            "from": parsed_email.from_addr,
            "to": parsed_email.to_addr,
            "cc": parsed_email.cc_addr,
            "date": parsed_email.date,
            "message_id": parsed_email.message_id
        },
        "body_format": parsed_email.body_format,
        "has_attachments": parsed_email.has_attachments,
        "attachment_count": parsed_email.attachment_count
    }
