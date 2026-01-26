# LLM Providers Research: API Headers, JSON Mode, and Structured Outputs

## OpenRouter Required Headers Research

### HTTP-Referer and X-Title Headers Usage

**Sources:**
- [OpenRouter App Attribution Guide](https://openrouter.ai/docs/app-attribution)
- [OpenRouter API Reference - Headers](https://openrouter.ai/docs/api-reference/overview#headers)
- [OpenRouter Quickstart](https://openrouter.ai/docs/quickstart)

**Purpose:** These optional headers help OpenRouter identify legitimate app usage, enable app rankings/analytics on their dashboard, and prevent request rejections/rate-limit issues. Apps using localhost URLs must include a title header to be tracked.

**Implementation Examples:**

**Python (OpenAI SDK):**
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="your-key",
    default_headers={
        "HTTP-Referer": "https://your-app.com",  # Your app's URL
        "X-Title": "Your App Name",              # Your app's display name
    }
)

response = client.chat.completions.create(
    model="meta-llama/llama-3.3-70b-instruct",
    messages=[{"role": "user", "content": "Hello"}]
)
```

**Python (Direct API):**
```python
import requests

headers = {
    "Authorization": "Bearer your-openrouter-key",
    "HTTP-Referer": "https://your-app.com",
    "X-Title": "Your App Name",
    "Content-Type": "application/json"
}

data = {
    "model": "meta-llama/llama-3.3-70b-instruct",
    "messages": [{"role": "user", "content": "Hello"}]
}

response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers=headers,
    json=data
)
```

**TypeScript/Fetch:**
```typescript
const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer your-openrouter-key',
    'HTTP-Referer': 'https://your-app.com',  // Optional. Site URL for rankings
    'X-Title': 'Your App Name',               // Optional. Site title for rankings
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    model: 'meta-llama/llama-3.3-70b-instruct',
    messages: [{ role: 'user', content: 'Hello' }],
  }),
});
```

**Benefits:**
- App appears in OpenRouter's public rankings
- Detailed analytics dashboard access
- Prevents rate limiting issues
- Professional visibility for your app

## OpenRouter Llama-3.3-70b-instruct JSON Mode

**Sources:**
- [OpenRouter Llama 3.3 70B Model Page](https://openrouter.ai/meta-llama/llama-3.3-70b-instruct)
- [OpenRouter Structured Outputs](https://openrouter.ai/docs/features/structured-outputs)
- [Meta Llama 3.3 Model Card](https://github.com/meta-llama/llama-models/blob/main/models/llama3_3/MODEL_CARD.md)

**Model Specifications:**
- **Model ID:** `meta-llama/llama-3.3-70b-instruct`
- **Context Window:** 131,072 tokens (128K)
- **Pricing:** $0.13/M input tokens, $0.38/M output tokens
- **Availability:** Since December 6, 2024

**JSON Mode Compatibility:**
OpenRouter supports structured outputs through `response_format: { type: "json_schema", json_schema: {...}, strict: true }`. This works with compatible models, though Llama models may have limitations compared to OpenAI models.

**Implementation:**
```python
import requests

headers = {
    "Authorization": "Bearer your-openrouter-key",
    "HTTP-Referer": "https://your-app.com",
    "X-Title": "Your App Name",
    "Content-Type": "application/json"
}

data = {
    "model": "meta-llama/llama-3.3-70b-instruct",
    "messages": [{"role": "user", "content": "Extract information in JSON format"}],
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "info_extraction",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"}
                },
                "required": ["name", "age"],
                "additionalProperties": False
            }
        }
    }
}

response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers=headers,
    json=data
)
```

**Limitations:**
- Llama models may not be as reliable as OpenAI models for strict JSON schema enforcement
- Some complex schemas might not work perfectly
- Consider using OpenAI models via OpenRouter for better JSON mode reliability

## Anthropic Python SDK Tool Use JSON Output

**Sources:**
- [Anthropic Python SDK Documentation](https://github.com/anthropics/anthropic-sdk-python)
- [Anthropic Tool Use Documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Anthropic Messages API](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)

**Correct SDK Usage for Structured Output:**
The Anthropic SDK provides tool-based approach for structured JSON outputs, using `client.beta.tools.messages.create()`.

**Implementation Examples:**

**Basic Tool Use:**
```python
import anthropic

client = anthropic.Anthropic(api_key="your-key")

response = client.beta.tools.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=1024,
    tools=[
        {
            "name": "extract_info",
            "description": "Extract structured information from text",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"}
                },
                "required": ["name", "age"]
            }
        }
    ],
    messages=[
        {"role": "user", "content": "John is 25 years old"}
    ]
)

# Access tool use result
if response.content[0].type == "tool_use":
    tool_result = response.content[0]
    print(f"Tool: {tool_result.name}")
    print(f"Input: {tool_result.input}")
```

**Advanced Tool Processing:**
```python
import anthropic
from typing import Any

client = anthropic.Anthropic()

def process_with_tools(user_input: str) -> dict[str, Any]:
    """Process user input using Claude tools for structured output."""
    
    tools = [
        {
            "name": "extract_person_info",
            "description": "Extract person information from text",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full name"},
                    "age": {"type": "integer", "description": "Age in years"},
                    "occupation": {"type": "string", "description": "Job or profession"}
                },
                "required": ["name"]
            }
        }
    ]
    
    response = client.beta.tools.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1024,
        tools=tools,
        messages=[{"role": "user", "content": user_input}]
    )
    
    # Process tool use
    for content in response.content:
        if content.type == "tool_use":
            return content.input
    
    return {}

# Usage
result = process_with_tools("John Smith is a 30-year-old software engineer")
print(result)  # {"name": "John Smith", "age": 30, "occupation": "software engineer"}
```

**Tool Runner Helper:**
```python
import json
from anthropic import Anthropic, beta_tool

client = Anthropic()

@beta_tool
def get_weather(location: str) -> str:
    """Get weather for a location."""
    # Mock weather API call
    return json.dumps({
        "location": location,
        "temperature": "72°F",
        "condition": "Sunny"
    })

# Automatic tool execution
runner = client.beta.messages.tool_runner(
    max_tokens=1024,
    model="claude-3-haiku-20240307",
    tools=[get_weather],
    messages=[{"role": "user", "content": "What's the weather in SF?"}]
)

for message in runner:
    print(message)
```

**Key Points:**
- Use `client.beta.tools.messages.create()` for tool-based structured outputs
- Define tools with `name`, `description`, and `input_schema`
- Access results via `response.content[0].input` for tool use blocks
- Tool schemas enforce JSON structure validation
- `client.beta.messages.tool_runner()` provides automatic tool execution

## OpenAI GPT-4o-mini Structured Output Schema Best Practices

**Sources:**
- [OpenAI Structured Outputs Guide](https://platform.openai.com/docs/guides/structured-outputs)
- [OpenAI GPT-4o-mini Documentation](https://platform.openai.com/docs/models/gpt-4o-mini)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference/chat/create)

**Model Specifications:**
- **Model ID:** `gpt-4o-mini` (or `gpt-4o-mini-2024-07-18`)
- **Context Window:** 128,000 tokens
- **Max Output Tokens:** 16,384
- **Structured Outputs:** Supported (version 2024-07-18 and later)

**Adapter Flags and Parameters:**

**Core Parameters:**
```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "response_schema",  # Required: unique identifier
            "schema": {...},            # Required: JSON schema object
            "strict": True              # Recommended: enforce exact schema
        }
    }
)
```

**Best Practices:**

**1. Schema Design:**
```python
# Good: Descriptive property names and descriptions
schema = {
    "type": "object",
    "properties": {
        "user_name": {
            "type": "string",
            "description": "The full name of the user"
        },
        "user_age": {
            "type": "integer",
            "description": "Age in years, must be positive",
            "minimum": 0,
            "maximum": 150
        }
    },
    "required": ["user_name", "user_age"],
    "additionalProperties": False  # Recommended: prevent extra fields
}
```

**2. SDK Helper Methods:**
```python
from openai import OpenAI
from pydantic import BaseModel

class UserInfo(BaseModel):
    name: str
    age: int
    email: str | None = None

client = OpenAI()

# Using parse() method with Pydantic models
completion = client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Extract user information"},
        {"role": "user", "content": "John Doe is 25 years old, email: john@example.com"}
    ],
    response_format=UserInfo
)

user_info = completion.choices[0].message.parsed
print(user_info.name)  # "John Doe"
print(user_info.age)   # 25
```

**3. Error Handling:**
```python
try:
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Extract info: invalid data"}],
        response_format=UserInfo
    )
    result = completion.choices[0].message.parsed
except Exception as e:
    # Handle parsing errors or invalid responses
    print(f"Structured output failed: {e}")
    # Fallback to regular completion
```

**Limits and Constraints:**

**Rate Limits (as of November 2025):**
- **Free Tier:** 3 RPM, 200 RPD, 40K TPM
- **Tier 1:** 500 RPM, 10K RPD, 200K TPM  
- **Tier 2:** 5K RPM, 2M TPM
- **Tier 3:** 5K RPM, 4M TPM
- **Tier 4:** 10K RPM, 10M TPM
- **Tier 5:** 30K RPM, 150M TPM

**Schema Limits:**
- Maximum schema complexity: ~100 properties
- Nested object depth: ~5 levels
- Array length limits: No hard limit, but performance degrades
- String length: No hard limit, but token limits apply

**Best Practices:**
1. **Always use `strict: True`** for guaranteed schema compliance
2. **Include detailed descriptions** in schema properties to guide the model
3. **Use `additionalProperties: False`** to prevent hallucinated fields
4. **Handle edge cases** where model might refuse or return incomplete responses
5. **Validate schema locally** before deployment
6. **Monitor token usage** - structured outputs can be more expensive
7. **Use appropriate model versions** - ensure 2024-07-18 or later for gpt-4o-mini

**Common Issues:**
- Model might return empty/invalid responses for edge cases
- Complex schemas can cause token limit issues
- Some prompt combinations work better than others
- Rate limits can be hit during high-volume structured output usage

**Performance Tips:**
- Use simpler schemas when possible
- Batch requests to stay within rate limits
- Consider caching for repeated schema validations
- Monitor actual token usage vs. estimates

## Summary

### OpenRouter Headers
- Use `HTTP-Referer` and `X-Title` headers for app attribution
- Prevents 403/rate-limit issues
- Enables dashboard analytics and rankings

### OpenRouter Llama JSON Mode
- Supports `response_format.json_schema` with `strict: true`
- Llama models less reliable than OpenAI for complex schemas
- Consider OpenAI models via OpenRouter for better JSON compliance

### Anthropic Tool Use
- Use `client.beta.tools.messages.create()` with tool definitions
- `input_schema` enforces JSON structure
- `client.beta.messages.tool_runner()` for automatic tool execution
- Tool-based approach ensures structured outputs

### OpenAI GPT-4o-mini Structured Outputs
- Use `response_format.json_schema` with `strict: True`
- SDK provides `client.beta.chat.completions.parse()` helper
- Always include descriptions and set `additionalProperties: False`
- Handle edge cases and rate limits appropriately
- Model version 2024-07-18+ required

All findings based on official documentation as of November 2025.
