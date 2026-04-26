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

## Internal documentation

Technical notes for the backend live in [`docs/`](./docs/index.md).

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
- `INTENT_CLASSIFIER_ENABLED`: enable the optional embedding-based intent classifier
- `INTENT_CLASSIFIER_BASE_URL`: OpenAI-compatible embeddings base URL, for example a local TEI service
- `INTENT_CLASSIFIER_MODEL`: embedding model name, such as `intfloat/multilingual-e5-small`

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

Start PostgreSQL locally with Apptainer:

```bash
./scripts/start_local_postgres_apptainer.sh
```

In another terminal, create a virtual environment, install dependencies, and run the migration:

```bash
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
./scripts/migrate_local.sh
./scripts/start_backend_local.sh
```

Use these local development values in `.env`:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/luke_bot
USE_FAKE_REDIS=true
AUTO_CREATE_SCHEMA=false
```

With this setup, PostgreSQL runs locally and Redis stays in memory via `USE_FAKE_REDIS=true`.

## Run PostgreSQL locally with Apptainer

If Docker is unavailable but Apptainer works on your machine, you can run PostgreSQL locally from this repo:

```bash
./scripts/start_local_postgres_apptainer.sh
```

This starts PostgreSQL on `localhost:5432` with:

- database: `luke_bot`
- user: `postgres`
- password: `postgres`

In another terminal, verify the connection with:

```bash
./scripts/check_local_postgres_apptainer.sh
```

## Start the backend locally

After PostgreSQL is running and dependencies are installed:

```bash
./scripts/migrate_local.sh
./scripts/start_backend_local.sh
```

## Expose the local webhook with ngrok

Once the API is running on `http://localhost:8000`, create a public tunnel:

```bash
ngrok http 8000
```

Use the HTTPS forwarding URL from ngrok in your Meta webhook configuration:

- Verify URL: `https://<your-ngrok-domain>/webhook/meta`
- Verify token: the same value as `META_VERIFY_TOKEN`

Meta will send verification requests and incoming WhatsApp webhook events through that public URL to your local FastAPI server.

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

The routing stack works in layers:

- rule-based keywords and regex extraction first
- optional embedding-based intent classification second
- optional LLM classification and extraction as the final fallback

The LLM:

- never writes to the database
- only returns structured data or classifications
- is always followed by Pydantic validation before persistence
- is optional during local development because rule-based fallbacks cover the core MVP flows

## Running tests

```bash
pytest
```

## Import group members from CSV

After running migrations, you can import a WhatsApp group member export into `users`:

```powershell
.venv\Scripts\python.exe scripts\import_group_members.py --csv C:\path\members.csv
```

Optional photo arguments:

```powershell
.venv\Scripts\python.exe scripts\import_group_members.py `
  --csv C:\path\members.csv `
  --photos-dir C:\path\downloaded-photos `
  --copy-photos-to D:\Apps\Paddington-Bot\output\group-member-photos
```

Use `--dry-run` to preview the import without committing changes.

## Future improvements

- Interactive WhatsApp reply types
- Background processing or retry queues
- Admin authentication
- Smarter listing search and exchange matching
- Stronger confidence scoring and moderation rules
