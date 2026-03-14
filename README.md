# Paddington Bot Backend

MVP backend for a WhatsApp community assistant bot powered by the official Meta WhatsApp Cloud API. The service is designed for a Leeds community marketplace and utility assistant, with support for currency exchange offers, local sale listings, community events, summaries, and simple conversational state.

## Tech stack

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy 2.0
- Alembic
- Redis
- httpx
- Pydantic
- Docker / Docker Compose
- Pytest

## Features

- Meta webhook verification and inbound message handling
- Outbound WhatsApp text messaging through the Meta Graph API
- Rule-based command handling for `help`, `menu`, `summary`, `sell`, `exchange`, and `event`
- Provider-agnostic LLM abstraction with an initial OpenAI-compatible implementation
- PostgreSQL persistence for users, messages, conversation state snapshots, exchange offers, listings, and events
- Redis-backed active conversation state
- REST API endpoints for future frontend and admin integration
- Basic tests for API, router, and webhook flows

## Project structure

```text
app/
  api/
  core/
  db/
  llm/
  schemas/
  services/
  workers/
alembic/
tests/
Dockerfile
docker-compose.yml
requirements.txt
```

## Environment variables

Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
```

Important variables:

- `DATABASE_URL`: async SQLAlchemy database URL
- `REDIS_URL`: Redis connection string
- `META_VERIFY_TOKEN`: token used by Meta webhook verification
- `META_ACCESS_TOKEN`: WhatsApp Cloud API access token
- `META_PHONE_NUMBER_ID`: WhatsApp business phone number ID
- `LLM_API_KEY`: API key for the OpenAI-compatible provider
- `LLM_BASE_URL`: provider base URL, defaults to OpenAI-compatible `/v1`
- `LLM_MODEL`: model name used for intent classification and extraction

## Run locally with Docker

```bash
docker compose up --build
```

In another terminal:

```bash
docker compose exec app alembic upgrade head
```

The API will be available at `http://localhost:8000`.

## Run locally without Docker

Create a virtual environment, install dependencies, and run the migration:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## API endpoints

- `GET /health`
- `GET /api/exchange-offers`
- `POST /api/exchange-offers`
- `GET /api/listings`
- `POST /api/listings`
- `GET /api/events`
- `POST /api/events`
- `GET /api/summary`
- `GET /webhook/meta`
- `POST /webhook/meta`

## Meta webhook setup

### Verification

Configure your Meta app to use:

- Verify URL: `https://<your-public-domain>/webhook/meta`
- Verify token: the same value as `META_VERIFY_TOKEN`

Meta will call:

```text
GET /webhook/meta?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
```

The service validates the token and returns the challenge string.

### Inbound message test

You can test the webhook locally with a request like:

```bash
curl -X POST http://localhost:8000/webhook/meta \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "contacts": [{"profile": {"name": "Kenji"}}],
          "messages": [{
            "from": "447700900123",
            "id": "wamid.test",
            "timestamp": "1741975200",
            "type": "text",
            "text": {"body": "I want to exchange 300 soles for pounds in Leeds city centre"}
          }]
        }
      }]
    }]
  }'
```

If Meta credentials are configured, the service will attempt to send a reply using the Graph API. If they are not configured yet, the outbound reply is still recorded in the database with a warning response payload so local development remains easy.

## LLM provider notes

The backend exposes a provider abstraction:

- `classify_intent(message, context)`
- `extract_structured_data(message, context)`

The initial implementation uses an OpenAI-compatible `chat/completions` endpoint over `httpx`, but the rest of the code depends only on the abstract interface.

The LLM:

- never writes to the database
- only returns structured data or classifications
- is always followed by Pydantic validation before persistence
- is optional during local development because rule-based fallbacks cover the core MVP flows

## Running tests

```bash
pytest
```

## Future improvements

- Interactive WhatsApp reply types
- Background processing or retry queues
- Admin authentication
- Smarter listing search and exchange matching
- Stronger confidence scoring and moderation rules
