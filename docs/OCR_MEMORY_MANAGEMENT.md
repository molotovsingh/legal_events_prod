# Docling OCR Memory Management

## Overview

Docling uses OCR engines (Tesseract, EasyOCR, RapidOCR, OCRmac) for processing scanned PDFs and images. OCR operations are memory-intensive and can cause OOM (Out of Memory) errors in containerized environments, especially when processing large batches or high-resolution scans.

## Current Configuration

### OCR Engine Selection

From `core/config.py`:

```python
ocr_engine: Literal["tesseract", "easyocr", "ocrmac", "rapidocr"]
# Default: "tesseract"
# Environment: DOCLING_OCR_ENGINE
```

**Available Engines:**

1. **Tesseract** (Default)
   - Memory: Moderate (~500MB-1GB per document)
   - Speed: Moderate
   - Accuracy: Good for English, decent for other languages
   - Pros: Mature, widely tested, good memory management
   - Cons: Slower than deep learning models

2. **EasyOCR**
   - Memory: High (~2-4GB due to deep learning models)
   - Speed: Moderate-Fast (with GPU), Slow (CPU-only)
   - Accuracy: Excellent for multilingual documents
   - Pros: High accuracy, many languages
   - Cons: **Memory-intensive, prone to memory leaks in some versions**

3. **RapidOCR**
   - Memory: Low-Moderate (~200-800MB per document)
   - Speed: Fast (optimized for production)
   - Accuracy: Good (uses ONNX models)
   - Pros: **Recommended for containers**, low memory footprint, fast
   - Cons: Newer, less widely adopted

4. **OCRmac** (macOS only)
   - Memory: Low (uses Apple's Vision framework)
   - Speed: Very Fast (hardware-accelerated)
   - Accuracy: Excellent
   - Pros: Native macOS performance
   - Cons: macOS only, not available in Docker Linux containers

### OCR Control Flags

```python
do_ocr: bool = True  # Enable/disable OCR globally
auto_ocr_detection: bool = True  # Auto-detect scanned PDFs
```

**Auto-Detection Logic** (from `core/docling_adapter.py:is_scanned_pdf`):
- Samples first N pages of PDF
- Checks if text extraction yields < 100 characters
- If scanned, automatically enables OCR even if `do_ocr=False`

## Known Issues

### EasyOCR Memory Regression

**Upstream Reports:**
- Docling GitHub issues mention memory regressions with EasyOCR backend
- EasyOCR models (~2-4GB) loaded into memory are not always released
- Multi-document processing can accumulate memory until OOM

**Symptoms:**
- Gradual RSS growth during batch processing
- OOM kills in Docker worker containers
- Slower processing over time (memory pressure)

**Current Status:**
- Default engine is `tesseract` (not affected)
- Users who explicitly set `DOCLING_OCR_ENGINE=easyocr` may experience issues

## Mitigation Strategies

### 1. Use RapidOCR for Containers (Recommended)

RapidOCR is optimized for production containerized environments:

```bash
# In .env or environment
DOCLING_OCR_ENGINE=rapidocr
```

**Pros:**
- Low memory footprint (~200-800MB per document)
- Fast inference (ONNX-based)
- Stable memory behavior (no known leaks)
- Good accuracy for common use cases

**Cons:**
- Newer than Tesseract, less field-tested
- Slightly lower accuracy than EasyOCR for complex multilingual documents

### 2. Disable OCR for Programmatic PDFs

Most legal documents are programmatic (not scanned). Only enable OCR when needed:

```bash
# Default to OCR off
DOCLING_DO_OCR=false

# Enable auto-detection (will OCR only scanned PDFs)
DOCLING_AUTO_OCR_DETECTION=true
```

This reduces memory usage by ~500MB-2GB per document for programmatic PDFs.

### 3. Chunk Large Documents

For very long PDFs (>100 pages) with OCR, process in chunks to limit memory:

**Implementation in `core/docling_adapter.py`:**

```python
def extract_with_chunking(self, file_path: Path, chunk_size: int = 20) -> ExtractedDocument:
    """
    Extract large documents in page chunks to limit memory usage

    Args:
        file_path: Path to PDF
        chunk_size: Number of pages to process at once

    Returns:
        Merged ExtractedDocument with all pages
    """
    import fitz

    doc = fitz.open(file_path)
    total_pages = len(doc)

    if total_pages <= chunk_size:
        # Small doc, process normally
        return self.extract(file_path)

    # Split into chunks
    all_text = []
    all_metadata = []

    for start_page in range(0, total_pages, chunk_size):
        end_page = min(start_page + chunk_size, total_pages)

        # Extract chunk to temporary PDF
        chunk_doc = fitz.open()
        chunk_doc.insert_pdf(doc, from_page=start_page, to_page=end_page - 1)
        chunk_path = file_path.parent / f"{file_path.stem}_chunk_{start_page}.pdf"
        chunk_doc.save(chunk_path)
        chunk_doc.close()

        # Process chunk
        try:
            result = self.extract(chunk_path)
            all_text.append(result.plain_text)
            all_metadata.append(result.metadata)
        finally:
            chunk_path.unlink(missing_ok=True)  # Clean up temp file

    doc.close()

    # Merge results
    return ExtractedDocument(
        markdown="\n\n".join(all_text),
        plain_text="\n\n".join(all_text),
        metadata={
            "file_path": str(file_path),
            "total_pages": total_pages,
            "chunk_size": chunk_size,
            "chunks_processed": len(all_metadata),
            "extraction_method": "chunked",
            "chunks_metadata": all_metadata
        }
    )
```

**Usage:**

```python
# In worker tasks, detect large documents
if needs_ocr and page_count > 100:
    result = docling_extractor.extract_with_chunking(file_path, chunk_size=20)
else:
    result = docling_extractor.extract(file_path)
```

### 4. Limit Concurrent OCR Jobs

In `worker/main.py` or queue configuration:

```python
# Limit worker concurrency for OCR jobs
RQ_CONCURRENCY = int(os.getenv("RQ_CONCURRENCY", "2"))  # Default: 2 workers

# Or use separate queues
OCR_QUEUE = "ocr"  # Dedicated queue for OCR jobs with lower concurrency
DEFAULT_QUEUE = "default"  # Normal jobs
```

**Docker Compose:**

```yaml
services:
  worker:
    environment:
      RQ_CONCURRENCY: "2"  # Limit to 2 concurrent OCR jobs
    deploy:
      resources:
        limits:
          memory: 4G  # Set memory limit
        reservations:
          memory: 2G
```

### 5. Explicitly Release Memory

After processing each document:

```python
import gc

def process_document(doc_path):
    result = extractor.extract(doc_path)
    # ... use result ...

    # Explicitly trigger garbage collection
    gc.collect()

    return result
```

### 6. Monitor Memory Usage

Add memory monitoring to worker:

```python
import psutil
import logging

logger = logging.getLogger(__name__)

def log_memory_usage(stage: str):
    """Log current memory usage for debugging"""
    process = psutil.Process()
    mem_info = process.memory_info()
    mem_mb = mem_info.rss / (1024 * 1024)
    logger.info(f"Memory usage at {stage}: {mem_mb:.1f} MB")

# In worker task
log_memory_usage("start")
result = extractor.extract(doc_path)
log_memory_usage("after_extraction")
```

### 7. Pin Docling Version

Ensure consistent behavior by pinning Docling and OCR dependencies:

```txt
# requirements.txt
docling==2.60.1
rapidocr-onnxruntime>=1.3.0  # If using RapidOCR
pytesseract>=0.3.10  # If using Tesseract
# Avoid: easyocr>=1.7.0  (known memory issues)
```

## Testing Memory Behavior

### Local Testing

```bash
# 1. Start worker with memory monitoring
docker compose up worker

# 2. Watch memory usage
docker stats legal_events_worker

# 3. Process test batch
curl -X POST http://localhost:8000/v1/runs/{run_id}/start \
  -H "Content-Type: application/json" \
  -d '{"files": [...]}'

# 4. Observe RSS growth over multiple documents
```

### Load Testing

```bash
# Process 20 documents and monitor memory
for i in {1..20}; do
  echo "Processing document $i"
  docker exec legal_events_worker python -c "
    import psutil
    mem = psutil.Process().memory_info().rss / (1024**2)
    print(f'Memory: {mem:.1f} MB')
  "

  # Trigger processing
  curl -X POST http://localhost:8000/v1/runs/{run_id}/start ...

  sleep 5
done
```

### Expected Memory Profile

**Tesseract (Default):**
- Baseline: ~200-300MB (worker idle)
- Per Document: +500MB-1GB spike
- After GC: Returns to baseline
- 10 docs: Stable at ~300-400MB

**RapidOCR (Recommended for Containers):**
- Baseline: ~150-250MB
- Per Document: +200-600MB spike
- After GC: Returns to baseline
- 10 docs: Stable at ~250-350MB

**EasyOCR (High Memory):**
- Baseline: ~800MB-1.5GB (models loaded)
- Per Document: +1-2GB spike
- After GC: May not fully release (leak)
- 10 docs: Gradual growth to 3-4GB+ ⚠️

## Recommended Configuration

### Development (Local)

```bash
# .env
DOCLING_DO_OCR=false  # Off by default
DOCLING_AUTO_OCR_DETECTION=true  # Auto-enable for scans
DOCLING_OCR_ENGINE=tesseract  # Stable default
```

### Production (Docker)

```bash
# .env
DOCLING_DO_OCR=false  # Off by default
DOCLING_AUTO_OCR_DETECTION=true  # Auto-enable for scans
DOCLING_OCR_ENGINE=rapidocr  # Low memory, fast
RQ_CONCURRENCY=2  # Limit concurrent jobs
```

### High-Volume Production

```bash
# .env
DOCLING_DO_OCR=false
DOCLING_AUTO_OCR_DETECTION=true
DOCLING_OCR_ENGINE=rapidocr
RQ_CONCURRENCY=1  # Single worker for OCR
DOCLING_TABLE_MODE=FAST  # Reduce table processing overhead
```

**Docker Compose:**

```yaml
services:
  worker:
    environment:
      DOCLING_OCR_ENGINE: rapidocr
      RQ_CONCURRENCY: "1"
    deploy:
      resources:
        limits:
          memory: 3G
        reservations:
          memory: 1G
    restart: always  # Auto-restart if OOM
```

## Troubleshooting

### Issue: Worker OOM Killed

**Symptoms:**
```
docker logs legal_events_worker
# ... (killed)
dmesg | grep -i oom
# Out of memory: Killed process 1234 (python)
```

**Solutions:**
1. Switch to RapidOCR: `DOCLING_OCR_ENGINE=rapidocr`
2. Disable OCR for programmatic PDFs: `DOCLING_DO_OCR=false`
3. Reduce concurrency: `RQ_CONCURRENCY=1`
4. Increase container memory: `docker compose` memory limits
5. Implement chunking for large documents (see Strategy 3)

### Issue: Gradual Memory Growth

**Symptoms:**
- Memory grows from 500MB → 2GB over 50 documents
- Processing slows down over time

**Solutions:**
1. Check OCR engine: If using EasyOCR, switch to RapidOCR
2. Add explicit `gc.collect()` after each document
3. Restart workers periodically (e.g., after 100 documents)
4. Pin Docling version to avoid regressions

### Issue: "CUDA out of memory" with GPU

**Solutions:**
1. Use CPU for OCR: `DOCLING_ACCELERATOR_DEVICE=cpu`
2. Reduce batch size if GPU OCR is batching internally
3. Set `PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512`

## Future Improvements

1. **Implement Chunking Strategy**: Add `extract_with_chunking` to `docling_adapter.py`
2. **Memory Monitoring**: Add prometheus metrics for worker memory usage
3. **Adaptive Concurrency**: Dynamically adjust worker concurrency based on memory pressure
4. **OCR Queue Separation**: Use dedicated low-concurrency queue for OCR jobs
5. **Upgrade Docling**: Monitor upstream for memory fixes, test newer versions

## References

- [Docling GitHub Issues - Memory](https://github.com/DS4SD/docling/issues?q=memory)
- [RapidOCR Documentation](https://github.com/RapidAI/RapidOCR)
- [EasyOCR Memory Issues](https://github.com/JaidedAI/EasyOCR/issues?q=memory)
- [Docker Memory Management](https://docs.docker.com/config/containers/resource_constraints/)
- [psutil for Python Memory Monitoring](https://psutil.readthedocs.io/)
