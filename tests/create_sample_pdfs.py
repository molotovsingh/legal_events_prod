"""
Generate sample PDF files from text fixtures for testing.

This script converts the text fixtures (sample_1page.txt, sample_5page.txt)
into PDF files using PyMuPDF (fitz) for testing the token estimation endpoint.
"""

import fitz  # PyMuPDF
from pathlib import Path


def text_to_pdf(text_content: str, output_path: str):
    """
    Convert text content to a PDF file.

    Args:
        text_content: Text to write to PDF
        output_path: Path to save the PDF file
    """
    # Create a new PDF
    doc = fitz.open()

    # Add a page (A4 size: 595 x 842 points)
    page = doc.new_page(width=595, height=842)

    # Define text area (with margins)
    margin = 72  # 1 inch margins
    text_rect = fitz.Rect(margin, margin, 595 - margin, 842 - margin)

    # Insert text with automatic text flow
    # fontsize=11, fontname="helv" (Helvetica)
    page.insert_textbox(
        text_rect,
        text_content,
        fontsize=11,
        fontname="helv",
        align=0  # Left-aligned
    )

    # Save the PDF
    doc.save(output_path)
    doc.close()
    print(f"✅ Created PDF: {output_path}")


def main():
    """Generate sample PDFs from text fixtures."""
    fixtures_dir = Path(__file__).parent / "fixtures"

    # Convert sample_1page.txt to PDF
    sample_1page_txt = fixtures_dir / "sample_1page.txt"
    sample_1page_pdf = fixtures_dir / "sample_1page.pdf"

    if sample_1page_txt.exists():
        with open(sample_1page_txt, 'r') as f:
            text_content = f.read()
        text_to_pdf(text_content, str(sample_1page_pdf))
        print(f"   Size: {sample_1page_pdf.stat().st_size} bytes")

    # Convert sample_5page.txt to PDF
    sample_5page_txt = fixtures_dir / "sample_5page.txt"
    sample_5page_pdf = fixtures_dir / "sample_5page.pdf"

    if sample_5page_txt.exists():
        with open(sample_5page_txt, 'r') as f:
            text_content = f.read()
        text_to_pdf(text_content, str(sample_5page_pdf))
        print(f"   Size: {sample_5page_pdf.stat().st_size} bytes")

    print("\n📄 Sample PDFs created successfully!")
    print("These PDFs are used for integration testing of the /v1/estimate-tokens endpoint.")


if __name__ == "__main__":
    main()
