# IBM Granite Models Integration Research

**Date:** November 10, 2025  
**Project:** legal-events-production  
**Status:** Feasibility Analysis

---

## Executive Summary

IBM Granite models (especially Granite-Docling and Granite Vision) can be integrated into this legal events extraction system, but they serve **different purposes** than current Docling usage:

1. **Granite-Docling-258M**: Drop-in replacement for Docling's document parsing layer
2. **Granite Vision models (2B-3.2B)**: Complementary vision-language models for image understanding and multimodal RAG

**Current State:** The project uses Docling 2.60.1 for document parsing. Granite-Docling can replace this with potential benefits in structure preservation and equation handling.

---

## Part 1: Granite-Docling-258M vs. Current Docling

### Granite-Docling Overview
- **Model Size:** 258M parameters (ultra-compact)
- **Architecture:** Vision-Language Model (VLM)
- **Built on:** Idefics3 + Granite 165M LLM + SigLIP2 vision encoder
- **Output Format:** DocTags (proprietary structured markup)
- **License:** Apache 2.0 (open-source)
- **Release:** September 17, 2025
- **Status:** Production-ready

### Key Capabilities
✅ **Better than current Docling:**
- Enhanced equation recognition (inline + floating math)
- Flexible inference modes (full-page, bbox-guided region)
- Improved stability (avoids infinite loops)
- Purpose-built for document conversion (not general image understanding)
- Preserves tables, code blocks, and document hierarchy
- DocTags format enables better downstream processing

⚠️ **Trade-offs:**
- Requires GPU or Apple Silicon (MLX) for inference (vs. Docling CPU-friendly)
- Smaller model = potentially lower accuracy on complex documents
- DocTags output requires different parsing than current Markdown-based pipeline
- Early multilingual support (Japanese, Chinese, Arabic) still experimental

### Integration Compatibility

#### Current Pipeline
```
PDF/Image → Docling DocumentConverter → Markdown → Event Extractors (LLM)
```

#### Proposed Granite Pipeline
```
PDF/Image → Granite-Docling VLM → DocTags + Markdown → Event Extractors (LLM)
```

**Effort Required:** Medium (1-2 sprints)

**Changes Needed:**
1. Add Granite-Docling-258M to requirements.txt
2. Create `core/granite_docling_adapter.py` (similar pattern to current `docling_adapter.py`)
3. Update `core/document_processor.py` to support VLM pipeline selection
4. Add GPU/MLX configuration for inference
5. Update metrics tracking (DocTags parsing time vs. Docling time)

---

## Part 2: Granite Vision Models Integration

### Granite Vision Model Options

| Model | Parameters | Pipeline Tag | Use Case |
|-------|-----------|--------------|----------|
| granite-vision-3.2-2b | 3.2B | image-to-text | Image captioning, OCR |
| granite-vision-3.1-2b-preview | 3.1B | image-to-text | Earlier version, preview |
| granite-vision-3.3-2b | 3.3B | image (general) | General vision tasks |
| granite-vision-3.3-2b-embedding | 3.3B | feature-extraction | Image embeddings, similarity |

### Positioning in Current Architecture

**NOT a document parser replacement**, but complementary for:

1. **Multimodal RAG Enhancement**
   - Extract visual features from document images
   - Build image-based retrieval for legal documents (charts, diagrams, signatures)
   - Enable visual similarity search across document collections

2. **Document Quality Assessment**
   - Detect document type/category via visual features
   - Assess image quality before OCR
   - Identify handwritten vs. printed content

3. **Event Extraction Enhancement**
   - Use image embeddings alongside text for event context
   - Detect visual indicators (seals, stamps, signatures) in legal docs

### Integration Complexity: **High** (requires architectural changes)

**Why?**
- Current pipeline is text-only (Docling → text → LLM classifier)
- Adding vision requires maintaining image references through pipeline
- New data contracts needed (images stored with documents)
- Additional storage requirements (images in MinIO)

**When to Consider:** Phase 3-4 (after core legal extraction stabilizes)

---

## Part 3: Current System Assessment

### What Works Today
✅ Docling 2.60.1 handles:
- PDFs (digital & scanned with OCR)
- DOCX, PPTX, HTML
- Images (PNG, JPEG) with OCR
- Email files (.eml, .msg)

✅ Extracted text → Event extraction via:
- OpenRouter (Claude, Mistral, etc.)
- Anthropic API
- OpenAI API
- DeepSeek API
- LangExtract (Gemini)

### Technical Debt Related to Document Processing
From CLAUDE.md, noted issues:
- Provider import failures (factory_callable paths breaking in worker)
- Only LangExtract provider fully working
- No provider validation at startup

**Note:** Not Docling-specific, but affects overall extraction quality

---

## Part 4: Integration Roadmap

### Option A: Minimal Change (Granite-Docling Only)
**Timeline:** 1-2 weeks  
**Effort:** Medium  
**Risk:** Low (drop-in replacement pattern)

```
1. Week 1:
   - Create granite_docling_adapter.py
   - Add VlmPipeline to document_processor.py
   - Add config options (GRANITE_DOCLING_ENABLED, INFERENCE_DEVICE)

2. Week 2:
   - Test on sample legal PDFs
   - Performance benchmarking vs current Docling
   - Update metrics/monitoring

3. Optional: A/B testing endpoint (compare both extractors)
```

**Configuration Example:**
```python
# .env
DOC_EXTRACTOR=granite_docling  # or "docling"
GRANITE_INFERENCE_DEVICE=cuda  # or "cpu", "mps" (Apple Silicon)
GRANITE_LOAD_IN_8BIT=true      # For memory constraints
```

### Option B: Full Vision Integration
**Timeline:** 2-3 months  
**Effort:** High  
**Risk:** Medium (architectural changes)

```
1. Phase 1: Implement Granite-Docling (Option A)
2. Phase 2: Add image pipeline to document processing
   - Store image references with documents
   - Compute Granite Vision embeddings
   - Index visual features in database

3. Phase 3: Multimodal event extraction
   - Hybrid text+vision classifiers
   - Visual indicator detection (signatures, stamps)

4. Phase 4: Multimodal RAG
   - Build visual search indices
   - Enable "find similar documents by appearance"
```

### Option C: Hybrid Approach (Recommended)
**Timeline:** 3-4 weeks  
**Effort:** Medium  
**Risk:** Low-Medium

```
1. Implement Granite-Docling as optional extractor (configurable)
2. Keep current Docling as default (backwards-compatible)
3. Add A/B testing framework to compare quality
4. Document decision criteria for when to use each
5. Plan Phase 2 vision integration after establishing baseline
```

---

## Part 5: Specific Integration Details

### Granite-Docling Installation

```bash
# Add to requirements.txt
docling==2.60.1                    # Current (keep for now)
granite-docling @ git+https://huggingface.co/ibm-granite/granite-docling-258M
torch>=2.0.0                        # Required for VLM
```

### Code Pattern (Following Current Design)

**File: `core/granite_docling_adapter.py`**
```python
class GraniteDoclingExtractor(DocumentExtractor):
    """Granite-Docling VLM extractor implementation"""
    
    def __init__(self, config: GraniteDoclingConfig):
        self.config = config
        self.model = load_model()  # Auto-download from HF
        self.processor = processor  # Image processor
        
    def extract(self, file_path: Path) -> ExtractedDocument:
        # Convert via VLM
        result = self.model.forward(...)
        doctags = result.get_doctags()
        markdown = convert_doctags_to_markdown(doctags)
        return ExtractedDocument(markdown, plain_text, metadata)
```

**File: `core/config.py` (extend existing)**
```python
@dataclass
class GraniteDoclingConfig:
    enabled: bool = field(default_factory=lambda: env_bool("GRANITE_DOCLING_ENABLED", False))
    inference_device: str = field(default_factory=lambda: env_str("GRANITE_INFERENCE_DEVICE", "cuda"))
    load_in_8bit: bool = field(default_factory=lambda: env_bool("GRANITE_LOAD_IN_8BIT", False))
    max_pages: int = field(default_factory=lambda: env_int("GRANITE_MAX_PAGES", 500))
```

### Deployment Considerations

**GPU Requirements:**
- Inference: ~4GB VRAM (standard NVIDIA)
- ~2GB VRAM (with 8-bit quantization)
- Apple Silicon: Automatic MLX acceleration (no explicit setup)

**Performance vs. Docling:**
- Docling: CPU-only, ~2-5s per page
- Granite-Docling: GPU, ~0.5-1s per page (10x faster with GPU)
- Trade-off: Requires GPU infrastructure

**Model Download:**
- First run auto-downloads ~800MB from HuggingFace
- Can be pre-cached in Docker image or mounted volume

---

## Part 6: Comparison Matrix

| Factor | Current Docling | Granite-Docling | Granite Vision |
|--------|-----------------|-----------------|-----------------|
| **Document Parsing** | ✅ Full support | ✅ Full support | ❌ Not supported |
| **Image OCR** | ✅ Yes (Tesseract) | ✅ Yes (native VLM) | ✅ Yes (native) |
| **Math/Equations** | ⚠️ Basic | ✅ Enhanced | ✅ Via text extraction |
| **Table Preservation** | ✅ Yes | ✅ Yes | ✅ Via text extraction |
| **GPU Required** | ❌ No | ✅ Yes (optional with MLX) | ✅ Yes |
| **Multimodal RAG** | ❌ No | ❌ No | ✅ Yes (embeddings) |
| **Inference Speed** | Slow (CPU) | Fast (GPU) | Fast (GPU) |
| **Output Format** | Markdown | DocTags + Markdown | Text + Embeddings |
| **Integration Effort** | N/A (already in) | Medium | High |
| **Data Contracts Change** | N/A | Minimal | Significant |

---

## Part 7: Questions for Clarification

1. **Performance vs. Quality Trade-off:**
   - Do faster extractions (Granite-Docling on GPU) outweigh setup complexity?
   - How important is multi-equation/complex table handling?

2. **Infrastructure:**
   - Is GPU capacity available in current deployment?
   - Can Docker Compose be extended with GPU support (nvidia-docker)?

3. **Event Extraction Quality:**
   - How much does text quality impact legal event detection (current step)?
   - Has this been tested with different document parsers?

4. **Multilingual Needs:**
   - Legal documents in languages beyond English?
   - Granite-Docling's experimental multilingual support adequate?

5. **Vision Integration Timeline:**
   - Is multimodal RAG for legal docs a future requirement?
   - Or focus purely on better document-to-text conversion?

---

## Part 8: Recommended Next Steps

### Immediate (1-2 weeks)
1. ✅ Review this research with team
2. Decide: Granite-Docling integration worth the effort?
3. If yes: Start with Option C (hybrid approach)

### Short-term (1 month)
1. Create Granite-Docling adapter module
2. Add configuration & Docker setup
3. Benchmark on sample legal documents vs. current Docling
4. Document decision criteria for when each extractor is used

### Medium-term (2-3 months)
1. If benchmarks are positive: Switch to Granite-Docling as primary
2. Keep current Docling as fallback
3. Deprecate in future release

### Optional (3+ months)
1. Evaluate Granite Vision for multimodal RAG
2. Plan vision feature integration if needed

---

## Resources

### Documentation
- **Granite-Docling HF:** https://huggingface.co/ibm-granite/granite-docling-258M
- **Granite-Docling Docs:** https://www.ibm.com/granite/docs/models/docling
- **Docling Library:** https://github.com/docling-project/docling
- **Granite Vision:** https://huggingface.co/collections/ibm-granite/granite-vision-models-67b3bd4ff90c915ba4cd2800

### Tutorial (Multimodal RAG with Granite)
- https://www.ibm.com/think/tutorials/build-multimodal-rag-langchain-with-docling-granite

### Related Blog Posts
- https://www.ibm.com/new/announcements/granite-docling-end-to-end-document-conversion
- https://www.infoq.com/news/2025/10/granite-docling-ibm/

---

## Implementation Feasibility Summary

| Integration Type | Feasibility | Complexity | Benefit | Timeline |
|------------------|-------------|-----------|---------|----------|
| **Granite-Docling** | ✅ High | Medium | Better equation/table handling, faster inference | 1-2 weeks |
| **Granite Vision (embeddings)** | ⚠️ Medium | High | Multimodal search, document similarity | 2-3 months |
| **Granite Vision (classification)** | ✅ High | Medium | Document type detection, quality assessment | 1 month |

**Recommendation:** Start with Granite-Docling as drop-in alternative to current Docling, with option to expand to vision models later.

