# Decision Service

Decision Service that consumes ML inference results from Kafka, queries an LLM to determine the best network actions, and publishes decisions back to Kafka.

## How It Works

1. Consumes ML results from `network.ml.results` Kafka topic
2. Queries an Ollama-compatible LLM with available decisions and ML data
3. LLM selects decisions and extracts template arguments (e.g. `ban <<ip_src>>` → `{"ip_src": "1.2.3.4"}`)
4. Publishes compressed decision results to `network.decisions` Kafka topic

## Kafka Messages

**Input** (`network.ml.results`): ML inference results per cell

**Output** (`network.decisions`) — gzip compressed:
```json
// Compressed message envelope
{ "compression": "gzip", "data": "<base64-encoded gzip>" }

// After decompression
{
  "timestamp": "2026-03-20T21:06:33Z",
  "cell_id": 1,
  "decisions": [
    { "id": "ban <<ip_src>>", "description": "Ban IP 1.2.3.4", "args": {"ip_src": "1.2.3.4"}, "risk_level_id": 2 }
  ],
  "reasoning": "High anomaly score detected from IP 1.2.3.4...",
  "alternatives": [...],
  "llm_model": "qwen2.5:7b",
  "llm_provider_url": "https://...",
  "ml_result": {...}
}
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `KAFKA_HOST` | `kafka` | Kafka broker hostname |
| `KAFKA_PORT` | `9092` | Kafka broker port |
| `KAFKA_INPUT_TOPIC` | `network.ml.results` | Topic to consume ML results from |
| `KAFKA_OUTPUT_TOPIC` | `network.decisions` | Topic to publish decisions to |
| `KAFKA_DEBOUNCE_SECONDS` | `60` | Minimum time between decisions per cell |
| `LLM_URL` | — | Ollama API URL (e.g. `https://host/ollama/api/generate`) |
| `LLM_API_KEY` | — | API key for LLM service |
| `LLM_MODEL` | — | Model name (e.g. `qwen2.5:7b`) |
| `BLACKLIST_ENABLED` | `true` | Whether to filter blacklisted decisions |
| `DB_PATH` | `/app/data/decision.db` | SQLite database path |

## API

Base path: `/api/v1`

### Config
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/config/decisions` | List available decisions |
| `POST` | `/config/decisions` | Add a decision |
| `DELETE` | `/config/decisions/{name}` | Remove a decision |
| `GET` | `/config/blacklist` | List blacklisted decisions |
| `POST` | `/config/blacklist` | Add to blacklist |
| `DELETE` | `/config/blacklist/{name}` | Remove from blacklist |

### Risk Levels
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/risk-levels` | List risk levels |
| `POST` | `/risk-levels` | Create risk level |
| `DELETE` | `/risk-levels/{name}` | Delete risk level |

### Subscriptions
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/subscriptions` | List subscriptions |
| `GET` | `/subscriptions/{id}` | Get subscription |
| `POST` | `/subscriptions` | Create subscription |
| `DELETE` | `/subscriptions/{id}` | Delete subscription |

## Decision Templates

Decisions can use `<<parameter>>` placeholders. The LLM extracts the actual value from ML data and returns it in `args`:

```json
{ "id": "ban <<ip_src>>", "args": { "ip_src": "192.168.1.100" } }
```

The backend fills in the template before publishing to Kafka.

## Running

```bash
docker compose up --build decision
```

Data is persisted in a Docker volume (`decision_data`) mounted at `/app/data`.
