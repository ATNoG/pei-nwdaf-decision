# pei-nwdaf-decision

Consumes ML inference results from Kafka, queries an LLM to select network actions, and publishes decisions back to Kafka.

## How it works

1. Consumes ML results from `network.ml.results`
2. Matches results against active subscriptions by tag filters
3. Queries an Ollama-compatible LLM with available decisions and ML data
4. LLM selects decisions and fills template arguments (e.g. `ban <<ip_src>>` → `{"ip_src": "1.2.3.4"}`)
5. Publishes gzip-compressed decision records to `network.decisions`

## Running

```bash
docker compose up -d
```

Port: `8000` (configurable via `DECISION_PORT`)

## API

Base path: `/api/v1`

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/config/decisions` | List available decisions |
| `POST` | `/config/decisions` | Add a decision template |
| `DELETE` | `/config/decisions/{name}` | Remove a decision |
| `GET` | `/config/blacklist` | List blacklisted decisions |
| `POST` | `/config/blacklist` | Add to blacklist |
| `DELETE` | `/config/blacklist/{name}` | Remove from blacklist |
| `GET` | `/risk-levels` | List risk levels |
| `POST` | `/risk-levels` | Create risk level |
| `GET` | `/subscriptions` | List subscriptions |
| `POST` | `/subscriptions` | Create subscription |
| `DELETE` | `/subscriptions/{id}` | Delete subscription |

## Subscriptions

Subscriptions filter which ML results trigger a decision call. Each subscription specifies a `tags_filter` (partial match against incoming data tags) and a `callback_url`.

## Decision templates

Decisions support `<<parameter>>` placeholders filled by the LLM from ML data:

```json
{ "id": "ban <<ip_src>>", "args": { "ip_src": "192.168.1.100" } }
```

## Environment

| Variable | Default | Description |
|---|---|---|
| `KAFKA_HOST` | `kafka` | Kafka broker host |
| `KAFKA_PORT` | `9092` | Kafka broker port |
| `KAFKA_DEBOUNCE_SECONDS` | `60` | Min time between decisions per subscription |
| `LLM_URL` | — | Ollama API URL |
| `LLM_API_KEY` | — | API key |
| `LLM_MODEL` | — | Model name (e.g. `qwen2.5:14b`) |
| `LLM_TIMEOUT` | `40` | LLM request timeout in seconds |
| `BLACKLIST_ENABLED` | `true` | Filter blacklisted decisions |
| `DECISION_PORT` | `8000` | Service port |
