"""
Qwen3-VL Document Extractor Adapter
Budget vision-language model for document parsing (alternative to Gemini 2.5 / Docling)
"""

import logging
import time
import base64
from pathlib import Path
from typing import Optional

from .interfaces import DocumentExtractor, ExtractedDocument

logger = logging.getLogger(__name__)


class Qwen3VLDocumentExtractor:
    """
    Uses Qwen3-VL-8B via OpenRouter for budget vision-based PDF processing

    Advantages over Docling:
    - Vision model sees document structure (layout, tables, formatting)
    - Works on poor quality scans where OCR fails
    - No local GPU/OCR dependencies needed

    Advantages over Gemini 2.5:
    - 85% cheaper ($0.077 vs ~$0.50-1.25 per 15-page doc)
    - 256K context window (sufficient for most legal documents)
    - Still multimodal - understands visual document structure

    Trade-offs vs Docling (FREE):
    - Costs ~$0.077 per 15-page document vs $0 for Docling
    - Network latency for image upload
    - Requires OpenRouter API key

    Use Case: When Docling OCR fails on poor quality scans, handwritten docs, or complex layouts
    """

    # OpenRouter pricing (verified Oct 16, 2025)
    COST_PER_1M_INPUT_TOKENS = 0.05
    COST_PER_1M_OUTPUT_TOKENS = 0.20
    COST_PER_1K_IMAGES = 5.12  # $0.00512 per image

    def __init__(
        self,
        api_key: str,
        model: str = "qwen/qwen3-vl-8b-instruct",
        timeout: int = 120,
        prompt: Optional[str] = None
    ):
        """
        Initialize Qwen3-VL Document Extractor

        Args:
            api_key: OpenRouter API key
            model: Model identifier (default: qwen/qwen3-vl-8b-instruct)
            timeout: Request timeout in seconds
            prompt: Optional custom extraction prompt (defaults to legal document prompt from catalog)

        Raises:
            ValueError: If API key is missing
        """
        if not api_key or api_key.strip() == "":
            raise ValueError(
                "OpenRouter API key is required for Qwen3VLDocumentExtractor. "
                "Set OPENROUTER_API_KEY environment variable."
            )

        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = "https://openrouter.ai/api/v1"
        self.available = True

        # Store prompt (None means use default hardcoded prompt for backwards compatibility)
        self.prompt = prompt

        logger.info(f"✅ Qwen3VLDocumentExtractor initialized with model: {model}")

    def extract(self, file_path: Path) -> ExtractedDocument:
        """
        Extract text from document using Qwen3-VL vision model

        Args:
            file_path: Path to the document file (PDF, PNG, JPG supported)

        Returns:
            ExtractedDocument with markdown, plain_text and metadata

        Process:
            1. Validate file type and size
            2. Convert document to base64 images (for PDFs, extract pages as images)
            3. Send to Qwen3-VL via OpenRouter vision API
            4. Parse response into ExtractedDocument
        """
        if not self.available:
            logger.error("❌ Qwen3-VL document extractor not available")
            return self._create_fallback_document(
                file_path,
                "Qwen3-VL extractor not configured"
            )

        # Check file extension
        supported_extensions = ['.pdf', '.png', '.jpg', '.jpeg']
        if file_path.suffix.lower() not in supported_extensions:
            logger.warning(f"⚠️ Unsupported file type: {file_path.suffix}")
            return self._create_fallback_document(
                file_path,
                f"Unsupported file type: {file_path.suffix}"
            )

        try:
            start_time = time.time()

            # Get file size for metadata
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            logger.info(f"📄 Processing {file_path.name} with Qwen3-VL ({file_size_mb:.1f}MB)...")

            # Convert to base64 images
            image_data_list = self._convert_to_base64_images(file_path)
            num_images = len(image_data_list)
            conversion_time = time.time() - start_time
            logger.info(f"✅ Converted to {num_images} image(s) in {conversion_time:.1f}s")

            # Extract text using vision model
            extraction_start = time.time()
            content = self._extract_text_from_images(image_data_list, file_path.name)
            extraction_time = time.time() - extraction_start

            total_time = time.time() - start_time

            # Calculate costs
            estimated_cost = self._estimate_cost(num_images, len(content))

            logger.info(
                f"✅ Qwen3-VL extraction complete in {total_time:.1f}s "
                f"(conversion: {conversion_time:.1f}s, processing: {extraction_time:.1f}s) "
                f"Cost: ~${estimated_cost:.4f}"
            )

            return ExtractedDocument(
                markdown=content,
                plain_text=content,
                metadata={
                    "document_name": file_path.name,
                    "file_path": str(file_path),
                    "extractor": "qwen_vl",
                    "model": self.model,
                    "file_size_mb": round(file_size_mb, 2),
                    "num_images": num_images,
                    "conversion_time_seconds": round(conversion_time, 2),
                    "extraction_time_seconds": round(extraction_time, 2),
                    "total_time_seconds": round(total_time, 2),
                    "estimated_cost_usd": round(estimated_cost, 4),
                }
            )

        except Exception as e:
            logger.error(f"❌ Qwen3-VL extraction failed for {file_path.name}: {e}")
            return self._create_fallback_document(file_path, f"Qwen3-VL extraction error: {str(e)}")

    def _convert_to_base64_images(self, file_path: Path) -> list:
        """
        Convert document to base64-encoded images

        Args:
            file_path: Path to document

        Returns:
            List of base64 image data URIs
        """
        file_ext = file_path.suffix.lower()

        # For image files, just encode directly
        if file_ext in ['.png', '.jpg', '.jpeg']:
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
            mime_type = 'image/jpeg' if file_ext in ['.jpg', '.jpeg'] else 'image/png'
            base64_data = base64.b64encode(image_bytes).decode('utf-8')
            return [f"data:{mime_type};base64,{base64_data}"]

        # For PDFs, convert pages to images using pdf2image
        elif file_ext == '.pdf':
            try:
                from pdf2image import convert_from_path

                # Convert PDF pages to PIL images (150 DPI is good balance of quality/size)
                images = convert_from_path(file_path, dpi=150)

                base64_images = []
                for i, img in enumerate(images):
                    # Convert PIL image to bytes
                    import io
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=85)
                    image_bytes = buffer.getvalue()

                    # Encode to base64
                    base64_data = base64.b64encode(image_bytes).decode('utf-8')
                    base64_images.append(f"data:image/jpeg;base64,{base64_data}")

                return base64_images

            except ImportError:
                raise ImportError(
                    "pdf2image library is required for PDF processing. "
                    "Install with: pip install pdf2image"
                )

        raise ValueError(f"Unsupported file type: {file_ext}")

    def _extract_text_from_images(self, image_data_list: list, filename: str) -> str:
        """
        Send images to Qwen3-VL via OpenRouter for text extraction

        Args:
            image_data_list: List of base64 image data URIs
            filename: Original filename (for logging)

        Returns:
            Extracted text content
        """
        import requests

        # Use custom prompt if provided, otherwise use default legal document prompt
        if self.prompt:
            prompt = self.prompt
        else:
            # Default document transcription prompt optimized for legal documents
            prompt = """
Transcribe this document completely and accurately, preserving all content and structure.

Pay special attention to:
- All dates in their original format (critical for chronological analysis)
- Legal citations and case references
- Party names and their roles
- Numbered sections, clauses, and sub-clauses
- Tables and schedules (convert to markdown tables)
- Signature blocks and attestation clauses
- Temporal markers and sequences

Return the complete document text in clean markdown format.
If the document has multiple pages, transcribe them in order and maintain continuity.
""".strip()

        # Build messages with vision content
        # For multi-page documents, we include all images in a single message
        content_parts = [{"type": "text", "text": prompt}]

        for i, image_data in enumerate(image_data_list):
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": image_data}
            })

        messages = [{"role": "user", "content": content_parts}]

        # Call OpenRouter API
        logger.info(f"🤖 Sending {len(image_data_list)} image(s) to {self.model} for extraction...")

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
            },
            timeout=self.timeout
        )

        response.raise_for_status()
        result = response.json()

        if not result.get('choices') or len(result['choices']) == 0:
            raise ValueError("Qwen3-VL returned empty response")

        extracted_text = result['choices'][0]['message']['content']

        if not extracted_text or extracted_text.strip() == "":
            raise ValueError("Qwen3-VL returned no text content")

        return extracted_text.strip()

    def _estimate_cost(self, num_images: int, output_chars: int) -> float:
        """
        Estimate API cost for this extraction

        Args:
            num_images: Number of images processed
            output_chars: Number of characters in output (rough proxy for tokens)

        Returns:
            Estimated cost in USD
        """
        # Image cost
        image_cost = (num_images / 1000) * self.COST_PER_1K_IMAGES

        # Output token cost (rough estimate: 1 token ≈ 4 chars)
        output_tokens = output_chars / 4
        output_cost = (output_tokens / 1_000_000) * self.COST_PER_1M_OUTPUT_TOKENS

        # Input token cost is minimal (just the prompt)
        input_cost = (200 / 1_000_000) * self.COST_PER_1M_INPUT_TOKENS

        return image_cost + input_cost + output_cost

    def _create_fallback_document(self, file_path: Path, error_message: str) -> ExtractedDocument:
        """
        Create fallback ExtractedDocument when extraction fails

        Args:
            file_path: Path to the document
            error_message: Description of the failure

        Returns:
            ExtractedDocument with error information
        """
        fallback_text = f"[Qwen3-VL Document Extraction Failed: {error_message}]"

        return ExtractedDocument(
            markdown=fallback_text,
            plain_text=fallback_text,
            metadata={
                "document_name": file_path.name,
                "file_path": str(file_path),
                "extractor": "qwen_vl",
                "extraction_failed": True,
                "error_message": error_message,
            }
        )

    def get_supported_types(self):
        """Return list of supported file extensions"""
        return ['.pdf', '.png', '.jpg', '.jpeg']

    def is_available(self) -> bool:
        """Check if the extractor is available"""
        return self.available
