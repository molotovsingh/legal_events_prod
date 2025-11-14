# Test Fixtures for v0.12.0 Token Counting

This directory contains test fixtures for validating the token counting and cost estimation feature.

## Required Fixtures

### 1. Sample PDF Documents

**Purpose:** Test document extraction and token counting accuracy

**Files Needed:**
- `sample_1page.pdf` - Simple 1-page PDF (~500 words)
- `sample_5page.pdf` - Medium 5-page PDF (~2500 words)
- `sample_complex.pdf` - Complex PDF with tables, images, formatting
- `sample_unicode.pdf` - PDF with Unicode characters (Chinese, Arabic, emoji)

**How to Generate:**
```python
# Use scripts/generate_test_pdfs.py (TODO: create this script)
python scripts/generate_test_pdfs.py --output tests/fixtures/
```

### 2. Ground Truth Token Counts

**Purpose:** Validate tokenizer accuracy against known values

**File:** `ground_truth_tokens.json`

**Format:**
```json
{
  "sample_1page.pdf": {
    "text": "Full extracted text content...",
    "gpt4_tokens": 142,
    "llama_tokens": 156,
    "claude_tokens": 138,
    "providers": {
      "openrouter/gpt-4": 142,
      "openrouter/meta-llama/llama-3.3-70b-instruct": 156,
      "anthropic/claude-3-sonnet": 138
    }
  },
  "sample_5page.pdf": {
    "text": "...",
    "gpt4_tokens": 712,
    "llama_tokens": 745,
    "claude_tokens": 698
  }
}
```

**How to Generate:**
```bash
# Manually count tokens using online tokenizers
# GPT: https://platform.openai.com/tokenizer
# Claude: https://docs.anthropic.com/claude/reference/token-counting
# Llama: Use transformers.AutoTokenizer locally
```

### 3. Test Pricing Data

**Purpose:** Validate cost calculations

**File:** `test_pricing.json`

**Format:**
```json
{
  "openai/gpt-4": {
    "cost_input_per_1m": 30.0,
    "cost_output_per_1m": 60.0,
    "last_updated": "2025-11-14"
  },
  "meta-llama/llama-3.3-70b-instruct": {
    "cost_input_per_1m": 0.88,
    "cost_output_per_1m": 0.88,
    "last_updated": "2025-11-14"
  }
}
```

### 4. MinIO Storage Keys

**Purpose:** Test estimation endpoint with real uploads

**File:** `minio_test_keys.json`

**Format:**
```json
{
  "sample_1page.pdf": {
    "storage_key": "documents/test_abc123.pdf",
    "filename": "sample_1page.pdf",
    "upload_date": "2025-11-14T00:00:00Z"
  }
}
```

**How to Generate:**
```python
# Upload test PDFs to MinIO and record storage keys
# Use scripts/upload_test_fixtures.py (TODO: create this script)
```

## Test Coverage Goals

### Unit Tests (test_token_counter.py)
- ✅ GPT encoding resolution (cl100k_base vs o200k_base)
- ✅ Tokenizer resolution for different providers
- ⏳ Token counting accuracy (needs ground truth fixtures)
- ⏳ Message array token counting
- ⏳ Error handling for missing tokenizers

### Integration Tests (test_token_estimation.py)
- ✅ Endpoint registration
- ✅ Classifiers endpoint functionality
- ⏳ Token estimation with real files (needs MinIO fixtures)
- ⏳ Cost calculation accuracy (needs pricing fixtures)
- ⏳ Classification token estimation
- ⏳ Error handling and edge cases

## Creating Test Fixtures

### Quick Start
```bash
# 1. Create sample PDFs
cd tests/fixtures/
# Manually create simple PDFs or use pandoc:
echo "# Test Document\nThis is a test." | pandoc -o sample_1page.pdf

# 2. Generate ground truth token counts
python scripts/count_tokens_manually.py sample_1page.pdf > ground_truth_tokens.json

# 3. Upload to MinIO for integration tests
python scripts/upload_test_fixtures.py
```

### Validation Checklist
- [ ] Sample PDFs created and committed
- [ ] Ground truth token counts verified manually
- [ ] Test pricing data matches production catalog
- [ ] MinIO test keys generated for CI/CD
- [ ] All fixtures documented in this README

## Usage in Tests

```python
import pytest
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def sample_pdf():
    return FIXTURES_DIR / "sample_1page.pdf"

@pytest.fixture
def ground_truth():
    with open(FIXTURES_DIR / "ground_truth_tokens.json") as f:
        return json.load(f)

def test_token_count_accuracy(sample_pdf, ground_truth):
    # Extract text from sample_pdf
    # Count tokens
    # Compare to ground_truth["sample_1page.pdf"]["gpt4_tokens"]
    pass
```

## Notes

- **Security:** Do NOT commit real client documents as test fixtures
- **Performance:** Keep test PDFs small (<1MB each) for fast CI/CD
- **Updates:** Regenerate ground truth when tokenizer versions change
- **Versioning:** Tag fixtures with v0.12.0 to track changes across releases
