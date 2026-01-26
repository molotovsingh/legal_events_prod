# Document Processing & OCR Research

## Docling Linux Dependencies List

**Sources:**
- [Docling GitHub Installation Guide](https://docling-project.github.io/docling/installation/)
- [Docling PyPI Dependencies](https://pypi.org/project/docling/)
- [Docling Docker Images](https://github.com/aidotse/docling-inference)

**Core System Dependencies:**
Docling requires several system-level dependencies for full functionality, particularly for PDF processing and OCR:

### Required for PDF Processing:
- **poppler-utils** - PDF rendering and text extraction utilities
- **tesseract-ocr** - OCR engine for scanned PDFs and images

### Optional but Recommended:
- **libmagic-dev** - File type detection
- **libgl1** - OpenGL libraries for image processing

### Python Dependencies (via PyPI):
```bash
pip install docling
# Core dependencies include:
# - transformers
# - torch
# - pillow
# - pypdfium2
# - python-docx
# - python-pptx
# - xlrd
# - xlsxwriter
# - beautifulsoup4
# - lxml
# - huggingface-hub
```

### Docker Installation:
Official Docling Docker images include all system dependencies:
```dockerfile
FROM ghcr.io/aidotse/docling-inference:latest
# CUDA version
FROM ghcr.io/aidotse/docling-inference:cpu-latest
# CPU version
```

**Verification Commands:**
```bash
# Check poppler installation
pdfinfo --help

# Check tesseract installation
tesseract --version

# Check libmagic
python -c "import magic; print('libmagic available')"
```

## Tesseract Language Packs Docker Installation

**Sources:**
- [Tesseract Language Packs Installation](https://ocrmypdf.readthedocs.io/en/latest/languages.html)
- [Tesseract GitHub Tessdata](https://github.com/tesseract-ocr/tessdata)
- [Ubuntu Tesseract Language Packages](https://packages.ubuntu.com/search?keywords=tesseract-ocr-&searchon=names)

**Docker Installation Methods:**

### Method 1: Ubuntu/Debian Packages
```dockerfile
FROM ubuntu:22.04

# Install base tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Install additional languages
RUN apt-get update && apt-get install -y \
    tesseract-ocr-hin \
    tesseract-ocr-deu \
    tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/*
```

### Method 2: Manual Tessdata Download
```dockerfile
FROM ubuntu:22.04

# Install base tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Download specific language packs
RUN mkdir -p /usr/share/tesseract-ocr/tessdata && \
    cd /usr/share/tesseract-ocr/tessdata && \
    wget https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata && \
    wget https://github.com/tesseract-ocr/tessdata/raw/main/hin.traineddata && \
    wget https://github.com/tesseract-ocr/tessdata/raw/main/deu.traineddata

# Set TESSDATA_PREFIX if needed
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/tessdata
```

### Method 3: Using Multi-Language Base Image
```dockerfile
FROM python:3.11-slim

# Install tesseract with all languages
RUN apt-get update && apt-get install -y \
    tesseract-ocr-all \
    && rm -rf /var/lib/apt/lists/*
```

**Language Code Examples:**
- `eng` - English (default)
- `hin` - Hindi
- `deu` - German
- `fra` - French
- `spa` - Spanish
- `chi_sim` - Chinese Simplified
- `ara` - Arabic

**Usage in Python:**
```python
import pytesseract

# Single language
text = pytesseract.image_to_string(image, lang='eng')

# Multiple languages
text = pytesseract.image_to_string(image, lang='eng+hin+deu')

# Auto language detection
text = pytesseract.image_to_string(image, lang='osd')  # Script detection
```

**Docker Best Practices:**
```dockerfile
# Minimize image size
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Verify installation
RUN tesseract --list-langs
```

## Poppler-utils Performance in Docker Slim Images

**Sources:**
- [Poppler Official Documentation](https://poppler.freedesktop.org/)
- [Docker Slim Images Comparison](https://forums.docker.com/t/differences-between-standard-docker-images-and-alpine-slim-versions/134973)
- [Poppler Docker Images](https://hub.docker.com/search?q=poppler)

**Poppler Availability and Performance Tradeoffs:**

### Image Size Comparison:
```bash
# Full Ubuntu image with poppler
FROM ubuntu:22.04
RUN apt-get install -y poppler-utils
# Size: ~200MB+

# Slim image with poppler
FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*
# Size: ~50-100MB

# Alpine with poppler (limited)
FROM alpine:latest
RUN apk add --no-cache poppler-utils
# Size: ~20-30MB (but limited functionality)
```

### Performance Tradeoffs:

**Slim Images Advantages:**
- **Smaller size**: 70-80% reduction in image size
- **Faster deployments**: Quicker image pulls and builds
- **Better security**: Fewer packages = fewer vulnerabilities
- **Resource efficiency**: Lower memory footprint

**Slim Images Disadvantages:**
- **Limited package ecosystem**: Not all Ubuntu packages available
- **Missing dependencies**: Some poppler features may require additional libs
- **Build complexity**: Need to manually install all required dependencies
- **Debugging difficulty**: Fewer diagnostic tools available

### Poppler Performance Considerations:

**Memory Usage:**
```bash
# Check poppler memory usage
pdfinfo large_file.pdf &
ps aux | grep pdfinfo

# Typical memory usage: 50-200MB per large PDF
```

**Processing Speed:**
- **Slim images**: Same processing speed as full images
- **CPU usage**: Poppler is CPU-bound, not affected by image size
- **I/O performance**: Limited by disk I/O, not container resources

### Recommended Docker Setup:
```dockerfile
FROM python:3.11-slim-bookworm

# Install minimal poppler dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libpoppler-cpp0v5 \
    libpoppler118 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get autoclean -y

# Verify installation
RUN pdfinfo -v

# Your application
COPY . /app
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app.py"]
```

**Performance Optimization:**
```dockerfile
# Use multi-stage build to reduce final image size
FROM python:3.11-slim as builder
RUN apt-get update && apt-get install -y \
    poppler-utils \
    build-essential \
    && pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim as production
COPY --from=builder /usr/bin/pdfinfo /usr/bin/pdfinfo
COPY --from=builder /usr/lib/x86_64-linux-gnu/libpoppler* /usr/lib/x86_64-linux-gnu/
# Copy only necessary libraries
```

## Docling Memory Usage Configuration for Large PDFs

**Sources:**
- [Docling GitHub Issues - OOM](https://github.com/docling-project/docling/issues/2540)
- [Docling Advanced Options](https://docling-project.github.io/docling/usage/advanced_options/)
- [Docling Memory Issues](https://github.com/docling-project/docling/issues/2077)
- [Docling Page Range Usage](https://github.com/docling-project/docling/issues/2210)

**Memory Usage Patterns:**
Docling can consume significant memory (2-8GB+) when processing large or complex PDFs, especially those with:
- High page counts (>100 pages)
- Complex layouts with tables/images
- Embedded vector graphics
- Mathematical formulas
- Multiple languages

**Configuration Options for Large PDFs:**

### 1. Page Range Limiting
```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()

# Process in chunks to avoid OOM
page_ranges = [(1, 50), (51, 100), (101, 150)]

for start, end in page_ranges:
    result = converter.convert(
        "large_file.pdf",
        page_range=[start, end]
    )
    # Process each chunk separately
```

### 2. File Size and Page Limits
```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()

# Impose limits on document processing
result = converter.convert(
    "large_file.pdf",
    max_num_pages=100,      # Limit pages
    max_file_size=50*1024*1024  # 50MB limit
)
```

### 3. Pipeline Options Tuning
```python
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption

# Configure for memory efficiency
pipeline_options = PdfPipelineOptions(
    do_table_structure=False,    # Disable table detection
    do_ocr=False,                # Disable OCR for digital PDFs
    enable_remote_services=False # Avoid external API calls
)

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options
        )
    }
)
```

### 4. Resource Limits
```python
import os

# Limit CPU threads
os.environ["OMP_NUM_THREADS"] = "2"

# Limit memory usage (if available)
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:64"
```

### 5. Batch Processing Strategy
```python
from docling.document_converter import DocumentConverter
import os

def process_large_pdf(file_path, chunk_size=50):
    """Process large PDF in chunks to avoid OOM."""
    converter = DocumentConverter()
    
    # Get total pages (requires pdf parsing)
    import pypdf
    with open(file_path, "rb") as f:
        pdf = pypdf.PdfReader(f)
        total_pages = len(pdf.pages)
    
    results = []
    for start in range(1, total_pages + 1, chunk_size):
        end = min(start + chunk_size - 1, total_pages)
        
        result = converter.convert(
            file_path,
            page_range=[start, end]
        )
        results.append(result)
    
    return results
```

### 6. Docker Memory Limits
```dockerfile
# Set memory limits in Docker
FROM python:3.11-slim

# Limit container memory
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:64
ENV OMP_NUM_THREADS=2

# Run with memory limits
# docker run --memory=4g --memory-swap=4g your-image
```

### 7. Streaming and Iterative Processing
```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()

# Use streaming for large documents
with converter.iterate_pages("large_file.pdf") as page_iter:
    for page in page_iter:
        # Process one page at a time
        print(f"Processing page {page.page_no}")
        # Extract text, tables, etc.
        text = page.text
        # Process and save incrementally
```

### 8. Model Selection for Memory Efficiency
```python
from docling.datamodel.pipeline_options import PdfPipelineOptions

# Use CPU-only processing for large files
pipeline_options = PdfPipelineOptions(
    device="cpu",  # Force CPU processing
    model="heron", # Use newer Heron model (more efficient)
)

# Or disable heavy processing
pipeline_options = PdfPipelineOptions(
    do_table_structure=False,
    do_ocr=False,
    do_picture_classification=False,
)
```

### 9. Monitoring Memory Usage
```python
import psutil
import os

def monitor_memory():
    """Monitor memory usage during processing."""
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"Current memory usage: {memory_mb:.1f} MB")
    
    if memory_mb > 4000:  # 4GB threshold
        print("Warning: High memory usage detected")
        # Implement cleanup or chunking logic

# Use during processing
converter = DocumentConverter()
result = converter.convert("large_file.pdf")
monitor_memory()
```

### Best Practices Summary:

1. **Chunk processing**: Split large PDFs into smaller page ranges
2. **Disable unnecessary features**: Turn off OCR, table detection for digital PDFs
3. **Limit resources**: Set CPU thread limits and memory constraints
4. **Use streaming**: Process pages iteratively when possible
5. **Monitor usage**: Track memory consumption during processing
6. **Choose efficient models**: Heron model is more memory-efficient than previous versions
7. **Docker limits**: Set container memory limits appropriately

**Performance Benchmarks:**
- Typical memory usage: 500MB - 2GB for standard documents
- Large complex PDFs: 4GB+ (may require chunking)
- CPU threads: 2-4 recommended for memory efficiency
- Processing speed: 10-15 pages/second on consumer hardware
