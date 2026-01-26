# Recommendation — Docling OCR Memory Mitigations

Date: 2025-11-06
Timestamp: 20251106T130949Z (UTC)

## Summary
Reduce OOM risk by defaulting OCR off for programmatic PDFs, preferring RapidOCR, chunking long docs, and explicit cleanup between batches; pin known good versions.

## Steps
- Detect scans; toggle OCR per run.
- Switch to RapidOCR in containers; expose env flag.
- Process in page batches; free intermediates.
- Pin docling/docling-parse versions with fixes.

## Validation
- Batch runs show stable RSS; long PDFs processed in chunks without OOM.
