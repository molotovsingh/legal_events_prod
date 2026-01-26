# v0.12.0 Architecture Decisions

This document records key architecture and scope decisions made during v0.12.0 development.

---

## Decision 1: Make Transformers Dependency Optional ✅

**Date:** 2025-11-14
**Status:** APPROVED

### Context
The transformers package adds ~1.2GB to Docker image size, primarily for Llama model tokenization support. Many users only use GPT or Claude models and don't need this dependency.

### Decision
Make transformers + sentencepiece **OPTIONAL** dependencies.

**Approach:**
- tiktoken: REQUIRED (~5MB, needed for GPT models)
- transformers: OPTIONAL (~1.2GB, only needed for Llama models)
- sentencepiece: OPTIONAL (~50MB, required by transformers)

### Rationale
1. **Smaller Default Image:** Users who don't use Llama models save 1.2GB
2. **Graceful Degradation:** Code already raises clear `TokenizerUnavailable` error if transformers is missing
3. **Flexibility:** Power users can add transformers to custom builds as needed
4. **No Breaking Changes:** Existing GPT/Claude workflows unaffected

### Implementation
- Updated requirements.txt with clear comments documenting optional nature
- No code changes needed (token_counter.py already handles missing imports gracefully)
- Documentation clarifies which models require which tokenizers

### Impact
- Docker image size: Stays at ~13.6GB (was projected 14.8GB)
- Deployment: Faster for users not using Llama models
- User experience: Clear error message if Llama model selected without transformers

---

## Decision 2: Defer Non-OpenRouter Adapter Coverage to v0.12.1 ✅

**Date:** 2025-11-14
**Status:** APPROVED

### Context
Post-run token tracking requires extracting usage metadata from LLM provider responses. Currently only `core/openrouter_adapter.py` extracts usage tokens. Other adapters (Anthropic, OpenAI, LangExtract, DeepSeek) use fallback token counting.

### Decision
**DEFER** adapter coverage enhancements to v0.12.1.

**v0.12.0 Scope:**
- ✅ OpenRouter adapter: Full usage tracking (prompt + completion tokens)
- ✅ Other adapters: Fallback to prompt token counting (no completion tokens)
- ✅ Pre-run estimation: Works for all supported providers

**v0.12.1 Scope (Deferred):**
- [ ] Anthropic adapter: Extract usage from API response
- [ ] OpenAI adapter: Extract usage from API response
- [ ] LangExtract adapter: Extract usage from Gemini response
- [ ] DeepSeek adapter: Extract usage from API response

### Rationale
1. **Focus Testing Effort:** Core token counting logic needs comprehensive tests
2. **OpenRouter Sufficient:** Most users use OpenRouter as primary provider
3. **Graceful Fallback:** Other providers still work, just with approximate completion tokens
4. **Faster Release:** Reduces v0.12.0 scope by ~8 hours of work
5. **Lower Risk:** Smaller changeset = fewer potential bugs

### Implementation Status

**Current Adapter Coverage:**

| Adapter | Pre-Run Estimation | Post-Run Tracking | Completion Tokens |
|---------|-------------------|-------------------|-------------------|
| OpenRouter | ✅ | ✅ | ✅ (from API response) |
| Anthropic | ✅ | ⚠️ Fallback | ❌ (estimates available but not extracted) |
| OpenAI | ✅ | ⚠️ Fallback | ❌ (available but not extracted) |
| LangExtract | ✅ | ⚠️ Fallback | ❌ (Gemini provides usage) |
| DeepSeek | ✅ | ⚠️ Fallback | ❌ (likely available) |

**Fallback Behavior:**
- Counts prompt tokens from extracted document text
- Sets completion tokens to 0 (not estimated)
- Underestimates total cost by ~50% (input-only)

### Impact
- **User Experience:** OpenRouter users get full accuracy; others get input-only cost estimates
- **Timeline:** Saves 8-10 hours in v0.12.0 development
- **Risk:** Lower (smaller attack surface for bugs)
- **Documentation:** Must clearly state OpenRouter has full accuracy

### Follow-Up Actions for v0.12.1
1. Audit Anthropic API response structure for usage metadata
2. Audit OpenAI API response structure for usage metadata
3. Audit Gemini/LangExtract response structure for usage metadata
4. Update adapters to extract completion tokens
5. Add tests for each adapter's usage extraction
6. Update documentation to reflect 100% coverage

---

## Decision 3: Go/No-Go Criteria for v0.12.0 Release

**Date:** 2025-11-14
**Go/No-Go Decision Date:** 2025-11-22

### Must-Have Criteria (Release Blockers)

1. ✅ **Test Coverage ≥80%**
   - Unit tests for token_counter.py
   - Integration tests for /v1/estimate-tokens
   - Worker token tracking tests

2. ✅ **Zero Critical Bugs**
   - No P0 issues in testing
   - No data loss scenarios
   - No security vulnerabilities

3. ✅ **Performance Acceptable**
   - Token estimation < 5 seconds per document
   - No memory leaks in tokenizer loading
   - Docker image builds successfully

4. ✅ **Documentation Complete**
   - API docs updated
   - CLAUDE.md has v0.12.0 section
   - User guide for cost estimation

### Go Criteria (Ship v0.12.0)
- All Must-Have criteria met
- 0-2 minor (P2) bugs
- User testing feedback positive

### Caution Criteria (Ship as Beta)
- Must-Have criteria met
- 3-5 moderate (P1) bugs
- Known limitations documented
- Clear upgrade path to v0.12.1

### No-Go Criteria (Defer to v0.13.0)
- Test coverage < 80%
- Any critical (P0) bugs
- >5 moderate (P1) bugs
- Performance regressions
- Docker build failures

---

## Timeline Impact

### Original Estimate (v0.11.2 → v0.12.0)
- Effort: 15 hours
- Timeline: 2 weeks (Nov 14 - Nov 28)

### Revised Estimate (After Decisions)
- Effort: 18-22 hours (increased due to comprehensive testing)
- Timeline: 2 weeks (still achievable)
- Hours/day average: 1.5-2 hours

**Breakdown:**
- Testing: 13-15 hours (Week 1)
- Bug fixes: 2-3 hours
- Documentation: 2-3 hours
- Deployment: 1 hour

### Risk Assessment
- **Probability of Nov 28 Release:** 75% (high confidence)
- **Probability of Deferral:** 25% (if major bugs discovered)
- **Fallback Plan:** Ship v0.12.0-beta with known limitations

---

## References

- V0.12.0_EXECUTIVE_SUMMARY.md - High-level overview
- V0.12.0_RELEASE_ANALYSIS.md - Comprehensive technical analysis
- V0.12.0_POST_VALIDATION_SUMMARY.md - Validation findings
- V0.12.0_NEXT_48_HOURS.md - Immediate action plan
- CLAUDE.md - Project architecture and guardrails
