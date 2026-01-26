#!/usr/bin/env python3
"""
Test script to validate all LLM provider API keys with an actual PDF document.
Tests each provider's ability to extract legal events from a sample document.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from core.document_processor import DocumentProcessor
from core.config import load_config, load_provider_config
from core.langextract_adapter import LangExtractEventExtractor
from core.openrouter_adapter import OpenRouterEventExtractor
from core.anthropic_adapter import AnthropicEventExtractor
from core.openai_adapter import OpenAIEventExtractor
from core.deepseek_adapter import DeepSeekEventExtractor

# Test document
TEST_PDF = "test_documents/famas_transaction_fee.pdf"

# Providers to test
PROVIDERS = [
    ("langextract", "LangExtract (Gemini)", ["GEMINI_API_KEY", "GOOGLE_API_KEY"]),
    ("openrouter", "OpenRouter", ["OPENROUTER_API_KEY"]),
    ("anthropic", "Anthropic Claude", ["ANTHROPIC_API_KEY"]),
    ("openai", "OpenAI GPT", ["OPENAI_API_KEY"]),
    ("deepseek", "DeepSeek", ["DEEPSEEK_API_KEY"]),
]


def check_api_key(env_vars):
    """Check if any of the required environment variables is set"""
    for var in env_vars:
        if os.getenv(var):
            return True, var
    return False, None


def test_provider(provider_name, display_name, required_keys):
    """Test a single provider"""
    print(f"\n{'='*80}")
    print(f"Testing: {display_name} ({provider_name})")
    print(f"{'='*80}")
    
    # Check API key
    has_key, key_name = check_api_key(required_keys)
    if not has_key:
        print(f"❌ SKIP: No API key found (need one of: {', '.join(required_keys)})")
        return {"status": "skipped", "reason": "No API key"}
    
    print(f"✅ API key found: {key_name}")
    
    try:
        # Load config
        print(f"📝 Loading configuration...")
        docling_config, langextract_config, extractor_config = load_config()
        
        # Extract text from PDF
        print(f"📄 Extracting text from: {TEST_PDF}")
        processor = DocumentProcessor(docling_config)
        file_path = Path(TEST_PDF)
        text, extraction_method = processor.extract_text(file_path, "pdf")
        
        if not text:
            print(f"❌ FAIL: Text extraction failed (no text returned)")
            return {"status": "failed", "reason": "Text extraction failed"}
        
        if len(text.strip()) < 50:
            print(f"❌ FAIL: Insufficient text extracted ({len(text)} chars)")
            return {"status": "failed", "reason": "Insufficient text"}
        
        print(f"✅ Text extracted: {len(text):,} characters via {extraction_method}")
        
        # Get event extractor for this provider
        print(f"🔧 Initializing {display_name} extractor...")
        
        # Create appropriate extractor based on provider
        if provider_name == "langextract":
            extractor = LangExtractEventExtractor(langextract_config)
        elif provider_name == "openrouter":
            _, provider_config, _ = load_provider_config("openrouter")
            extractor = OpenRouterEventExtractor(provider_config)
        elif provider_name == "anthropic":
            _, provider_config, _ = load_provider_config("anthropic")
            extractor = AnthropicEventExtractor(provider_config)
        elif provider_name == "openai":
            _, provider_config, _ = load_provider_config("openai")
            extractor = OpenAIEventExtractor(provider_config)
        elif provider_name == "deepseek":
            _, provider_config, _ = load_provider_config("deepseek")
            extractor = DeepSeekEventExtractor(provider_config)
        else:
            print(f"❌ FAIL: Unknown provider: {provider_name}")
            return {"status": "failed", "reason": f"Unknown provider: {provider_name}"}
        
        if not extractor:
            print(f"❌ FAIL: Could not initialize extractor for {provider_name}")
            return {"status": "failed", "reason": "Extractor initialization failed"}
        
        # Test event extraction
        print(f"🚀 Extracting legal events...")
        metadata = {"file_path": str(file_path), "provider": provider_name}
        events = extractor.extract_events(text[:5000], metadata)  # Use first 5000 chars
        
        if not events:
            print(f"❌ FAIL: No events extracted")
            return {"status": "failed", "reason": "No events extracted"}
        
        # Check if it's a fallback record
        if len(events) == 1 and events[0].attributes.get("fallback"):
            reason = events[0].attributes.get("reason", "Unknown")
            print(f"❌ FAIL: Fallback record created - {reason}")
            return {"status": "failed", "reason": f"Fallback: {reason}"}
        
        # Success!
        print(f"✅ SUCCESS: Extracted {len(events)} legal event(s)")
        print(f"\n📊 Sample Event:")
        print(f"   Date: {events[0].date}")
        print(f"   Details: {events[0].event_particulars[:100]}...")
        print(f"   Citation: {events[0].citation}")
        
        return {
            "status": "success",
            "events_count": len(events),
            "first_event": {
                "date": events[0].date,
                "particulars": events[0].event_particulars[:100],
                "citation": events[0].citation
            }
        }
        
    except Exception as e:
        print(f"❌ FAIL: Exception occurred - {type(e).__name__}: {str(e)}")
        import traceback
        print(f"\n🔍 Traceback:")
        traceback.print_exc()
        return {"status": "failed", "reason": f"Exception: {str(e)}"}


def main():
    """Run tests for all providers"""
    print(f"╔{'='*78}╗")
    print(f"║{'LLM Provider API Key Validation Test':^78}║")
    print(f"╚{'='*78}╝")
    print(f"\n📅 Test Time: {datetime.utcnow().isoformat()}Z")
    print(f"📄 Test Document: {TEST_PDF}")
    
    # Check if test document exists
    if not Path(TEST_PDF).exists():
        print(f"\n❌ ERROR: Test document not found: {TEST_PDF}")
        return 1
    
    # Run tests
    results = {}
    for provider_name, display_name, required_keys in PROVIDERS:
        result = test_provider(provider_name, display_name, required_keys)
        results[provider_name] = result
    
    # Summary
    print(f"\n{'='*80}")
    print(f"TEST SUMMARY")
    print(f"{'='*80}\n")
    
    success_count = sum(1 for r in results.values() if r["status"] == "success")
    failed_count = sum(1 for r in results.values() if r["status"] == "failed")
    skipped_count = sum(1 for r in results.values() if r["status"] == "skipped")
    
    print(f"📊 Results:")
    print(f"   ✅ Success: {success_count}/{len(PROVIDERS)}")
    print(f"   ❌ Failed:  {failed_count}/{len(PROVIDERS)}")
    print(f"   ⏭️  Skipped: {skipped_count}/{len(PROVIDERS)}")
    
    print(f"\n📋 Detailed Results:\n")
    for provider_name, display_name, _ in PROVIDERS:
        result = results[provider_name]
        status_icon = {
            "success": "✅",
            "failed": "❌",
            "skipped": "⏭️"
        }.get(result["status"], "❓")
        
        print(f"   {status_icon} {display_name:25} - {result['status'].upper()}")
        if result["status"] == "failed":
            print(f"      └─ Reason: {result.get('reason', 'Unknown')}")
        elif result["status"] == "success":
            print(f"      └─ Extracted {result['events_count']} event(s)")
    
    print(f"\n{'='*80}\n")
    
    # Return exit code
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
