# Technical Decisions

## Why FastAPI

FastAPI provides:

- fast iteration for an MVP
- native async support
- built-in request validation through Pydantic
- simple dependency injection for wiring services
- automatic OpenAPI generation when needed later

## Why SQLAlchemy async plus PostgreSQL

This stack gives the project:

- reliable relational storage
- explicit schema evolution through Alembic
- support for more complex filtering and admin use cases
- a clean migration path from MVP to a more feature-rich system

## Why Redis for conversation state

Conversation state is read and updated frequently during multi-step bot flows. Redis is a good fit because it offers:

- cheap short-lived state storage
- TTL support
- simple key-based access per user

PostgreSQL still stores a mirrored snapshot so the system can recover draft context and support inspection.

## Why keep the LLM optional

The current implementation deliberately keeps the bot functional without an LLM.

Benefits:

- easier local development
- lower operating cost
- more predictable behavior for core MVP flows
- graceful fallback when model calls fail

The LLM is used only to help with classification and structured extraction. It does not write directly to the database.

## Why separate routes, services, and repositories

This separation keeps concerns clearer:

- routes stay thin and HTTP-focused
- services own workflow logic
- repositories encapsulate queries

That makes the codebase easier to test and less painful to refactor as the product evolves.

## Known limitations

- webhook processing is synchronous and not queue-backed
- webhook idempotency should be strengthened before heavier production traffic
- the parser logic in `MessageRouter` is intentionally heuristic and still narrow
- no authentication or authorization exists yet for the REST API
- record expiration is modeled but not yet backed by cleanup jobs
- admin and moderation tooling have not been implemented

## Short-term backend priorities

Recommended next technical improvements:

1. add webhook idempotency using provider message ids
2. improve parser accuracy and expand test coverage
3. normalize time zone handling in user-facing event responses
4. introduce background retries or job processing for outbound failures
5. add authentication before exposing internal APIs more broadly
