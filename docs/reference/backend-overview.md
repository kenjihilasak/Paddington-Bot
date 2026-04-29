# Backend Overview

## Purpose

This document explains how the backend codebase is organized and which package owns each responsibility.

## Top-level structure

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
docs/
```

## Package responsibilities

### `app/main.py`

Application entrypoint. It creates the FastAPI app, registers routes, and manages shared resources through the lifespan hook.

### `app/api/`

HTTP-facing layer.

- `deps.py`: dependency injection wiring
- `routes/health.py`: health endpoint
- `routes/exchange_offers.py`: exchange offer API
- `routes/listings.py`: marketplace listing API
- `routes/events.py`: event API
- `routes/summary.py`: aggregated summary API
- `routes/webhook.py`: Meta webhook verification and processing

### `app/core/`

Cross-cutting runtime concerns.

- `config.py`: environment-based settings
- `logging.py`: logging configuration

### `app/db/`

Persistence setup and data access.

- `base.py`: declarative base
- `session.py`: async engine and session factory
- `models/`: ORM entities and enums
- `repositories/`: reusable query and persistence operations

### `app/llm/`

Optional LLM abstraction.

- `base.py`: provider contract
- `openai_provider.py`: OpenAI-compatible implementation
- `parser.py` and `prompts.py`: model-specific parsing and prompting helpers

### `app/schemas/`

Pydantic request and response schemas shared by HTTP routes and some internal flows.

### `app/services/`

Business logic and orchestration layer.

- `message_router.py`: conversational intent routing and extraction
- `webhook_service.py`: inbound webhook orchestration
- `whatsapp_service.py`: outbound Graph API calls
- `conversation_state_service.py`: Redis plus PostgreSQL state handling
- `exchange_service.py`, `listing_service.py`, `event_service.py`: domain operations
- `summary_service.py`: aggregated views for bot and API

### `app/workers/`

Currently a placeholder for future background jobs or asynchronous processors.

### `alembic/`

Database migration configuration and migration scripts.

### `tests/`

Pytest suite covering health checks, API flows, webhook behavior, and message router logic.

## Current architectural style

The project uses a lightweight layered architecture:

1. routes handle transport concerns
2. services handle business workflows
3. repositories handle database access
4. schemas validate IO boundaries

This is a practical structure for an MVP because it keeps responsibilities separated without introducing heavy domain abstractions too early.

## What is central today

The most important runtime path today is:

1. Meta sends a webhook payload
2. `WebhookService` extracts supported messages
3. inbound messages are persisted
4. `MessageRouter` decides the intent and next action
5. services create or query records
6. an outbound text response is sent and stored

## Where future growth will likely happen

- authentication and admin APIs
- stronger moderation and validation rules
- asynchronous retries and background processing
- richer WhatsApp response types
- better search and matching logic
