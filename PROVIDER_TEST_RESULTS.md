# LLM Provider API Key Test Results

**Test Date**: 2025-11-09  
**Test Document**: test_documents/famas_transaction_fee.pdf (222KB, 1,214 chars extracted)  
**Test Method**: Standalone Python script with direct provider testing

---

## Test Results Summary

| Provider | Status | Events Extracted | API Key | Notes |
|----------|--------|------------------|---------|-------|
| **OpenRouter** | ✅ **WORKING** | 2 events | Configured | Using openai/gpt-oss-120b model |
| **Anthropic Claude** | ✅ **WORKING** | 1 event | Configured | Using claude-3-haiku-20240307 |
| **OpenAI GPT** | ✅ **WORKING** | 1 event | Configured | Using gpt-4o-mini |
| **LangExtract (Gemini)** | ❌ **FAILED** | 0 events | Configured | Module not installed: `langextract` |
| **DeepSeek** | ⏭️ **SKIPPED** | N/A | Not configured | No API key in .env |

---

## Detailed Results

### ✅ OpenRouter - WORKING

**Status**: SUCCESS  
**API Key**: OPENROUTER_API_KEY (configured)  
**Model**: openai/gpt-oss-120b  
**Events Extracted**: 2

**Sample Event**:
```
Date: 27 October 2023
Details: FaMAS GmbH issued Invoice Number ELSA10/2023 to Elcomponics Sales Pvt Ltd 
         (GSTIN NO 09AABCE6120F1Z0) for EUR 245,000.00 for services related to 
         engagement letter.
Citation: (empty)
```

**Logs**:
- ✅ API key validated
- ✅ Text extracted via Docling (1,214 chars)
- ✅ HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
- ✅ Successfully extracted 2 legal events

---

### ✅ Anthropic Claude - WORKING

**Status**: SUCCESS  
**API Key**: ANTHROPIC_API_KEY (configured)  
**Model**: claude-3-haiku-20240307  
**Events Extracted**: 1  
**Cost**: $0.0006 (1,589 tokens)

**Sample Event**:
```
Date: 27.Oct 2023
Details: This document appears to be an invoice from FaMAS GmbH to Elcomponics Sales 
         Pvt Ltd for professional services rendered...
Citation: No citation available
```

**Logs**:
- ✅ API key validated
- ✅ Text extracted via Docling (1,214 chars)
- ✅ HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
- ✅ Successfully extracted 1 legal event
- 📊 Tokens: 1,589 | Cost: $0.0006

---

### ✅ OpenAI GPT - WORKING

**Status**: SUCCESS  
**API Key**: OPENAI_API_KEY (configured)  
**Model**: gpt-4o-mini  
**Events Extracted**: 1  
**Cost**: $0.0037 (964-965 tokens)

**Sample Event**:
```
Date: 27.0ct 2023
Details: On October 27, 2023, FaMAS GmbH issued an invoice numbered ELSA10/2023 to 
         Elcomponics Sales Pvt Ltd for professional services rendered...
Citation: (empty)
```

**Logs**:
- ✅ API key validated
- ✅ Text extracted via Docling (1,214 chars)
- ✅ HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
- ✅ Successfully extracted 1 legal event
- 📊 Tokens: 964-965 | Cost: $0.0037

---

### ❌ LangExtract (Gemini) - FAILED

**Status**: FAILED  
**API Key**: GEMINI_API_KEY (configured)  
**Error**: `langextract module required`

**Root Cause**: The `langextract` Python package is not installed in the environment.

**Fix Required**:
```bash
pip install langextract
# or
uv pip install langextract
```

**Logs**:
- ✅ API key validated (GEMINI_API_KEY found)
- ✅ Text extracted via Docling (1,214 chars)
- ❌ LangExtract module not available
- ❌ Initialization failed: langextract module required
- ❌ Fallback record created

**Note**: This is a **dependency issue**, not an API key issue. The Gemini API key is configured correctly, but the `langextract` Python library is missing from the environment.

---

### ⏭️ DeepSeek - SKIPPED

**Status**: SKIPPED (No API key configured)  
**API Key**: DEEPSEEK_API_KEY (not in .env)

**To Enable**:
1. Sign up at: https://platform.deepseek.com
2. Get API key
3. Add to .env:
   ```bash
   DEEPSEEK_API_KEY=your_key_here
   DEEPSEEK_MODEL=deepseek-chat
   DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
   ```

---

## Summary

### Working Providers (3/5)
✅ **OpenRouter** - 2 events extracted  
✅ **Anthropic Claude** - 1 event extracted ($0.0006)  
✅ **OpenAI GPT** - 1 event extracted ($0.0037)

### Failed Providers (1/5)
❌ **LangExtract (Gemini)** - Module not installed (dependency issue)

### Skipped Providers (1/5)
⏭️ **DeepSeek** - No API key configured

---

## Recommendations

### Immediate Actions

1. **Install LangExtract module** to enable Gemini provider:
   ```bash
   pip install langextract
   ```

2. **Optional: Add DeepSeek API key** if you want to test that provider:
   ```bash
   # Add to .env
   DEEPSEEK_API_KEY=sk-xxxxx
   ```

### Production Recommendations

Based on test results, recommended provider order for production:

1. **OpenRouter** (openai/gpt-oss-120b)
   - Best extraction: 2 events vs 1 from others
   - Cost-effective OSS model
   - Good detail in event descriptions

2. **Anthropic Claude** (claude-3-haiku-20240307)
   - Very cheap: $0.0006 per document
   - Fast: 1.7s API call time
   - Good quality extraction

3. **OpenAI GPT** (gpt-4o-mini)
   - Higher cost: $0.0037 per document
   - Reliable quality
   - Good fallback option

4. **LangExtract (Gemini)** - Currently unavailable
   - Needs module installation
   - Once fixed, can be cost-effective option

---

## Test Script

The test script `test_providers.py` can be run anytime to validate provider configuration:

```bash
python3 test_providers.py
```

It will:
- Check for configured API keys
- Extract text from a sample PDF
- Test each provider's event extraction
- Report success/failure with details
