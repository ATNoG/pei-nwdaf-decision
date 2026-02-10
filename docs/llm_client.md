# LLM Client

Author: Thiago Vicente

## Overview

Client for sending decision requests to an LLM API.

> This was designed thinking about a ollama instance :)

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `LLM_URL` | API endpoint | Yes |
| `LLM_MODEL` | Model name | Yes |
| `LLM_API_KEY` | Token for auth | Yes |

## Files

- `llm/system.txt` - System prompt
- `llm/prompt.txt` - Prompt template with placeholders

### Placeholders
   
- data
- decisions

**Usage**: place {<placeholder>} on prompt.txt
 
## Usage

```python
from src.schemas import DecisionRequest
from src.services.llm_client import LLMClient

# Load env or setup using os.environ
from dotenv import load_dotenv
load_dotenv()

request = DecisionRequest( 
    ...
)

client = LLMClient()
response = await client.query(request)
```

## Request Format (Ollama)

```json
{
  "model": "llama3",
  "system": ["xpto"](../llm/system.txt),
  "prompt": ["xpto"](../llm/prompt.txt),
  "stream": false,
  "format": {
    "type": "object",
    "properties": {
      "decision": {"type": "string"},
      "reasoning": {"type": "string"},
      "alternatives": {"type": "array"}
    }
  }
}
```

## Methods

| Method | Description |
|--------|-------------|
| `query(request)` | Send request to LLM, returns response dict |
| `info()` | Returns client config (url, model, masked api key, call count) |
