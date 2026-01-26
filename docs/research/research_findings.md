# Research Findings: API and Tool Compatibility Analysis

## OpenRouter Llama-3.3-70b-instruct Model Research

**Sources:**
- [OpenRouter Llama 3.3 70B Instruct Model Page](https://openrouter.ai/meta-llama/llama-3.3-70b-instruct)
- [Meta Llama 3.3 Model Card](https://github.com/meta-llama/llama-models/blob/main/models/llama3_3/MODEL_CARD.md)
- [OpenRouter Structured Outputs](https://openrouter.ai/docs/features/structured-outputs)

**Model ID:** `meta-llama/llama-3.3-70b-instruct`

**Context Window:** 131,072 tokens (128K)

**Pricing:**
- Input tokens: $0.13/M
- Output tokens: $0.38/M

**Availability:** Available on OpenRouter since December 6, 2024

**JSON Support:** OpenRouter supports structured outputs through `response_format: { type: "json_schema", json_schema: {...}, strict: true }`. This works with compatible models, though Llama models may have limitations compared to OpenAI models.

## OpenRouter API Headers

**Sources:**
- [OpenRouter App Attribution](https://openrouter.ai/docs/app-attribution)
- [OpenRouter API Reference - Headers](https://openrouter.ai/docs/api-reference/overview#headers)

**Required Headers for App Attribution:**
- `HTTP-Referer`: Identifies your app's URL on openrouter.ai
- `X-Title`: Sets/modifies your app's display name in rankings

**Purpose:** These optional headers help OpenRouter identify legitimate app usage, enable app rankings/analytics, and prevent request rejections/rate-limit issues. Apps using localhost URLs must include a title header to be tracked.

## Anthropic Claude 3 Haiku Compatibility

**Sources:**
- [Anthropic Claude API Documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
- [Claude 3 Model Card](https://docs.anthropic.com/en/docs/intro-to-claude)

**Latest SDK Usage:**
```python
import anthropic
client = anthropic.Anthropic()
response = client.beta.tools.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=1024,
    tools=[...],  # Tool definitions
    messages=[...]
)
```

**JSON/Tool Output Compatibility:**
- **Tool Calling:** Fully supported with `client.beta.tools.messages.create()`
- **JSON Mode:** Achieved through tool definitions with structured schemas
- **Latest Model:** `claude-3-5-haiku-20241022` (most recent)

**SDK Version:** Latest Anthropic Python SDK supports all Claude 3 Haiku features including tool use and structured outputs.

## OpenAI GPT-4o-mini Structured Outputs

**Sources:**
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [OpenAI GPT-4o-mini Model](https://platform.openai.com/docs/models/gpt-4o-mini)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference/chat/create)

**JSON Mode Parameters:**
```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "response_schema",
            "schema": {...},
            "strict": true
        }
    }
)
```

**Adapter Parameters:**
- `response_format.type`: `"json_schema"` for structured outputs
- `response_format.json_schema`: JSON schema definition
- `response_format.strict`: `true` for strict schema enforcement
- `model`: `"gpt-4o-mini"` (available from version 2024-07-18)

**Compatibility:** GPT-4o-mini supports structured outputs reliably, though community reports suggest slightly lower reliability than GPT-4o.

## MinIO Presigned PUT CORS Configuration

**Sources:**
- [MinIO CORS Configuration](https://docs.min.io/enterprise/aistor-object-store/administration/security/cors.html)
- [MinIO mc cors command](https://docs.min.io/enterprise/aistor-object-store/reference/cli/mc-cors/)
- [MinIO Presigned URLs](https://docs.min.io/enterprise/aistor-object-store/developers/python/minio-py.html#presigned-put-object)

**CORS Issue:** MinIO requires explicit CORS configuration for browser-based presigned uploads.

**Solution:**
```bash
# Configure CORS policy
mc admin config set <alias> api.cors.allow_origin="https://yourdomain.com"
mc admin config set <alias> api.cors.allow_methods="GET,POST,PUT"
mc admin config set <alias> api.cors.allow_headers="Authorization,Content-Type"
```

**Browser Uploads:** Presigned PUT URLs work for browser uploads when CORS is properly configured. Default MinIO policy allows GET operations via presigned URLs without special configuration.

## Python-MinIO Presigned PUT Timedelta Support

**Sources:**
- [MinIO Python SDK Documentation](https://docs.min.io/enterprise/aistor-object-store/developers/python/minio-py.html)
- [MinIO Python SDK GitHub](https://github.com/minio/minio-py)
- [Python timedelta documentation](https://docs.python.org/3/library/datetime.html#timedelta-objects)

**SDK Compatibility:** python-minio fully supports `timedelta` objects for the `expires` parameter.

**Usage:**
```python
from datetime import timedelta
from minio import Minio

client = Minio(...)
url = client.presigned_put_object(
    bucket_name="bucket",
    object_name="object",
    expires=timedelta(hours=2)  # timedelta accepted
)
```

**Version Support:** Compatible with minio v7.x and later versions.

## SSE-Starlette FastAPI Compatibility

**Sources:**
- [sse-starlette GitHub](https://github.com/sysid/sse-starlette)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Server-Sent Events MDN](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)

**Compatibility Status:** sse-starlette is fully compatible with FastAPI 0.115+

**Usage:**
```python
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

@app.get("/stream")
async def stream_endpoint(request: Request):
    async def generate():
        for i in range(10):
            yield {"data": f"Event {i}"}
            await asyncio.sleep(1)
    return EventSourceResponse(generate())
```

**Streaming:** SSE streaming works correctly with FastAPI 0.115 and uvicorn.

## RQ 1.15 Worker with Redis 7 Compatibility

**Sources:**
- [RQ Documentation - Workers](https://python-rq.org/docs/workers/)
- [RQ Documentation - Scheduling](https://python-rq.org/docs/scheduling/)
- [RQ GitHub Repository](https://github.com/rq/rq)

**Scheduler Flag:** Use `--with-scheduler` flag for RQ workers with scheduling capability.

**Best Practices:**
```bash
# Start worker with scheduler
rq worker --with-scheduler

# Programmatic usage
from rq import Worker, Queue
worker = Worker(queues=[queue], connection=redis)
worker.work(with_scheduler=True)
```

**Redis Compatibility:** RQ 1.15 supports Redis 7 (and Redis >= 5, Valkey >= 7.2).

**Multiple Workers:** Multiple workers can run with scheduler enabled for redundancy.

## Docling System Dependencies

**Sources:**
- [Docling GitHub Repository](https://github.com/docling-project/docling)
- [Docling Installation Guide](https://docling-project.github.io/docling/installation/)
- [Docling Docker Images](https://github.com/aidotse/docling-inference)

**Required System Dependencies:**
- **Tesseract OCR:** `tesseract-ocr` package for OCR functionality
- **Poppler:** `poppler-utils` package for PDF processing
- **Python Dependencies:** Listed in `pyproject.toml`

**Docker Images:** Official Docling Docker images include all necessary system dependencies:
- CUDA: `ghcr.io/aidotse/docling-inference:latest`
- CPU: `ghcr.io/aidotse/docling-inference:cpu-latest`

**API/Worker Images:** Pre-configured with tesseract, poppler, and all required OCR/PDF libraries.

## Pandas OpenPyXL Python 3.12 Compatibility Issues

**Sources:**
- [pandas GitHub - pyproject.toml](https://github.com/pandas-dev/pandas/blob/main/pyproject.toml)
- [openpyxl GitHub](https://github.com/theorchard/openpyxl)
- [pandas to_excel documentation](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_excel.html)

**Version Conflicts:**
- pandas 2.0.0+ requires openpyxl >= 3.0.7
- Python 3.12 compatibility issues in some environments

**Docker Solutions:**
- Use compatible versions: `pandas==2.1.4` with `openpyxl==3.0.10`
- Specify versions in requirements.txt:
  ```
  pandas==2.1.4
  openpyxl==3.0.10
  ```
- Use `pandas[excel]` for automatic dependency resolution

**Prevention:** Explicitly pin compatible versions to avoid Excel export failures.

## Alembic PostgreSQL ENUM Migration Best Practices

**Sources:**
- [Alembic Autogenerate Documentation](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [alembic-postgresql-enum GitHub](https://github.com/Pogchamp-company/alembic-postgresql-enum)
- [SQLAlchemy PostgreSQL ENUM](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#sqlalchemy.dialects.postgresql.ENUM)

**Autogenerate Limitations:** Alembic's autogenerate doesn't handle PostgreSQL ENUMs reliably.

**Best Practices:**
1. **Pre-create enums manually** in migrations rather than relying on autogenerate
2. **Use `postgresql.ENUM`** instead of SQLAlchemy `Enum` in migrations
3. **Reference existing enums** with `create_type=False`:
   ```python
   sa.Column('field', postgresql.ENUM(name='existing_enum', create_type=False))
   ```
4. **Use alembic-postgresql-enum** library for better autogenerate support

**Common Issues:**
- Type casting errors when altering enum columns
- Need for explicit USING clauses in ALTER TABLE statements

## MinIO Bucket Policy for Presigned URL Downloads

**Sources:**
- [MinIO Bucket Policies](https://docs.min.io/enterprise/aistor-object-store/administration/iam/access/)
- [MinIO mc share download](https://docs.min.io/enterprise/aistor-object-store/reference/cli/mc-share/mc-share-download/)
- [AWS S3 Presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html)

**Default Policy:** MinIO's default bucket policy allows GET operations via presigned URLs without additional configuration.

**Policy Structure:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"AWS": ["*"]},
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::bucket/*"]
    }
  ]
}
```

**Presigned URLs:** Work for downloads when users have appropriate bucket permissions.

## Google GenerativeAI Environment Variables

**Sources:**
- [Google AI Studio API Keys](https://aistudio.google.com/app/apikey)
- [Google GenAI SDK Documentation](https://googleapis.github.io/python-genai/)
- [Gemini API Authentication](https://ai.google.dev/gemini-api/docs/api-key)

**Accepted Variables:**
- `GEMINI_API_KEY` (recommended)
- `GOOGLE_API_KEY` (takes precedence if both set)

**SDK Behavior:**
```python
import google.genai as genai

# Automatically uses GEMINI_API_KEY or GOOGLE_API_KEY env var
client = genai.Client()

# Or explicit
client = genai.Client(api_key="your-key")
```

**Library Expectations:** SDK automatically detects and uses the correct API key from environment variables.

## LangExtract GitHub Repository Stability

**Sources:**
- [LangExtract GitHub Repository](https://github.com/google/langextract)
- [LangExtract Releases](https://github.com/google/langextract/releases)
- [LangExtract PyPI](https://pypi.org/project/langextract/)
- [LangExtract Official Site](https://langextract.com/)

**Repository:** `google/langextract`

**Pip Install URL:** `pip install git+https://github.com/google/langextract.git`

**Stability:**
- **Tags:** Stable releases available (v1.0.0 to v1.0.9)
- **Latest:** v1.0.9 (August 31, 2025)
- **Maintenance:** Actively maintained by Google
- **PyPI:** Available as `langextract` package

**Installation Examples:**
```bash
# From PyPI (recommended)
pip install langextract

# From specific tag
pip install git+https://github.com/google/langextract.git@v1.0.9

# From commit
pip install git+https://github.com/google/langextract.git@2446bbe2b8d1f948fc71f6bf57e2b4ca54329da8
```

## OpenRouter Rate Limits and Billing

**Sources:**
- [OpenRouter API Limits](https://openrouter.ai/docs/api-reference/limits)
- [OpenRouter Pricing](https://openrouter.ai/models)
- [OpenRouter FAQ](https://openrouter.ai/docs/faq)

**Trial Requirements:**
- Free tier available for testing
- Trial accounts have usage limits (50 free model requests/day after initial credits)
- Billing required for production usage

**Rate Limit Handling:**
- Implement proper error handling for 429 responses
- Use request batching and queuing
- Monitor usage through OpenRouter dashboard

**Billing Considerations:**
- Credits-based system
- Different pricing per model
- Automatic credit top-up available
