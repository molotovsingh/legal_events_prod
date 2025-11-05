# Research Summary: API Compatibility and Integration Guide

## Executive Summary

This document summarizes research findings on 15 API and tool compatibility queries, providing actionable recommendations for implementation.

## Key Findings by Category

### AI Model APIs
- **OpenRouter Llama-3.3-70b-instruct**: Available with 128K context, JSON support via structured outputs
- **Anthropic Claude 3 Haiku**: Full tool calling and JSON support with latest SDK
- **OpenAI GPT-4o-mini**: Structured outputs supported with `response_format.json_schema`
- **Google GenerativeAI**: Accepts `GEMINI_API_KEY` or `GOOGLE_API_KEY` env vars

### Infrastructure Tools
- **MinIO**: Requires CORS config for browser uploads; presigned URLs work with proper bucket policies
- **RQ**: Version 1.15 compatible with Redis 7; use `--with-scheduler` flag
- **SSE-Starlette**: Fully compatible with FastAPI 0.115+

### Data Processing
- **Docling**: Docker images include all system deps (tesseract, poppler)
- **Pandas/OpenPyXL**: Version conflicts in Python 3.12; pin `pandas==2.1.4, openpyxl==3.0.10`
- **Alembic**: Use `alembic-postgresql-enum` for reliable ENUM migrations

### Development Tools
- **LangExtract**: Stable PyPI package; VCS install from `google/langextract`

## Implementation Recommendations

### 1. API Headers & Authentication
```python
# OpenRouter headers for app attribution
headers = {
    "HTTP-Referer": "https://your-app.com",
    "X-Title": "Your App Name"
}

# Google GenAI env vars
os.environ["GEMINI_API_KEY"] = "your-key"
```

### 2. Structured Outputs
```python
# OpenAI GPT-4o-mini
response_format = {
    "type": "json_schema",
    "json_schema": {"name": "schema", "schema": {...}, "strict": True}
}

# Anthropic Claude
response = client.beta.tools.messages.create(
    model="claude-3-haiku-20240307",
    tools=[{"name": "tool", "input_schema": {...}}],
    messages=[...]
)
```

### 3. MinIO Configuration
```bash
# CORS for browser uploads
mc admin config set alias api.cors.allow_origin="https://yourdomain.com"

# Presigned URLs
url = client.presigned_put_object(bucket, object, expires=timedelta(hours=2))
```

### 4. RQ Worker Setup
```bash
# Start worker with scheduler
rq worker --with-scheduler queue_name

# Multiple workers for redundancy
rq worker-pool -n 3 high default low
```

### 5. Alembic ENUM Migrations
```python
# Use postgresql.ENUM with create_type=False for existing enums
sa.Column('field', postgresql.ENUM(name='enum_name', create_type=False))
```

## Risk Mitigation

### Version Conflicts
- Pin exact versions in requirements.txt
- Test upgrades in staging environments
- Use Docker images with pre-tested dependency combinations

### API Limits & Costs
- Implement proper error handling for rate limits (429 responses)
- Monitor usage through provider dashboards
- Use batching and queuing for high-volume operations

### CORS & Browser Compatibility
- Configure CORS policies before deployment
- Test presigned URL workflows end-to-end
- Handle preflight OPTIONS requests properly

## Next Steps

1. **Update Dependencies**: Pin compatible versions based on research findings
2. **Configure CORS**: Set up MinIO CORS policies for browser uploads
3. **Test Migrations**: Validate Alembic ENUM migration strategies
4. **Monitor Usage**: Implement usage tracking for API rate limits
5. **Document Configurations**: Create deployment checklists for each integration

## References & Further Reading

### Official Documentation Sources
- **OpenRouter**: [API Docs](https://openrouter.ai/docs), [Models](https://openrouter.ai/models), [App Attribution](https://openrouter.ai/docs/app-attribution)
- **Anthropic Claude**: [API Reference](https://docs.anthropic.com/), [Tool Use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- **OpenAI GPT**: [API Reference](https://platform.openai.com/docs/api-reference), [Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- **Google Gemini**: [API Docs](https://ai.google.dev/gemini-api/docs), [SDK](https://googleapis.github.io/python-genai/)

### Infrastructure Tools
- **MinIO**: [Documentation](https://docs.min.io/), [Python SDK](https://docs.min.io/enterprise/aistor-object-store/developers/python/minio-py.html)
- **RQ**: [Official Docs](https://python-rq.org/docs/), [GitHub](https://github.com/rq/rq)
- **SSE-Starlette**: [GitHub](https://github.com/sysid/sse-starlette), [FastAPI Integration](https://fastapi.tiangolo.com/)

### Data Processing Libraries
- **Docling**: [GitHub](https://github.com/docling-project/docling), [Docker Images](https://github.com/aidotse/docling-inference)
- **Pandas**: [Documentation](https://pandas.pydata.org/docs/), [GitHub](https://github.com/pandas-dev/pandas)
- **Alembic**: [Documentation](https://alembic.sqlalchemy.org/), [PostgreSQL ENUM](https://github.com/Pogchamp-company/alembic-postgresql-enum)
- **LangExtract**: [GitHub](https://github.com/google/langextract), [PyPI](https://pypi.org/project/langextract/)

### Research Methodology
All findings are based on official documentation, GitHub repositories, and API specifications current as of November 2025. Sources include:
- Official API documentation from providers
- GitHub repositories and release notes
- Community discussions and issue trackers
- SDK documentation and examples

**Note**: APIs and libraries evolve rapidly. Regular monitoring of these sources is recommended for the latest updates and breaking changes.
