# Paddington Bot Technical Documentation

This folder contains internal technical documentation for the backend MVP.

## Recommended reading order

1. [Architecture](./architecture.md)
2. [Backend Overview](./backend-overview.md)
3. [Database](./database.md)
4. [Webhook Flow](./webhook-flow.md)
5. [API Reference](./api-reference.md)
6. [Technical Decisions](./technical-decisions.md)

## Scope

This documentation is intended for internal use while building and evolving the backend. It focuses on:

- current architecture and responsibilities
- runtime flow from inbound WhatsApp message to outbound response
- data model and storage concerns
- current HTTP API surface
- key design choices and known limitations

## Assets

Place diagrams and screenshots in [`docs/assets/`](./assets/).

Suggested filename for the main architecture diagram:

- `architecture-overview.png`

Once the image is added, reference it from [Architecture](./architecture.md).
