# API Reference

## Base assumptions

- Default local base URL: `http://localhost:8000`
- JSON is used for request and response bodies unless noted otherwise.
- Validation errors are returned by FastAPI as `422 Unprocessable Entity`.

## Health

### `GET /health`

Checks database and Redis connectivity.

Example response:

```json
{
  "status": "ok",
  "database": "ok",
  "redis": "ok"
}
```

## Exchange offers

### `GET /api/exchange-offers`

List exchange offers.

Query params:

- `offer_currency`
- `want_currency`
- `location`
- `status`
- `active_only` default `true`
- `limit` default `20`
- `offset` default `0`

Example:

```bash
curl "http://localhost:8000/api/exchange-offers?offer_currency=PEN&active_only=true"
```

### `POST /api/exchange-offers`

Create a new exchange offer.

Example request:

```json
{
  "user_id": 1,
  "offer_currency": "PEN",
  "want_currency": "GBP",
  "amount": "300",
  "location": "Leeds city centre",
  "notes": "Available after 6pm"
}
```

Example success response:

```json
{
  "id": 1,
  "user_id": 1,
  "offer_currency": "PEN",
  "want_currency": "GBP",
  "amount": "300.00",
  "location": "Leeds city centre",
  "notes": "Available after 6pm",
  "status": "active",
  "created_at": "2026-03-15T10:00:00Z",
  "expires_at": "2026-04-14T10:00:00Z"
}
```

Possible errors:

- `404` if `user_id` does not exist
- `422` if validation fails

## Listings

### `GET /api/listings`

List marketplace listings.

Query params:

- `category`
- `location`
- `search_text`
- `status`
- `active_only` default `true`
- `limit` default `20`
- `offset` default `0`

### `POST /api/listings`

Create a listing.

Example request:

```json
{
  "user_id": 1,
  "category": "item",
  "title": "Microwave",
  "description": "Good condition",
  "price": "25",
  "currency": "GBP",
  "location": "Headingley"
}
```

Example success response:

```json
{
  "id": 1,
  "user_id": 1,
  "category": "item",
  "title": "Microwave",
  "description": "Good condition",
  "price": "25.00",
  "currency": "GBP",
  "location": "Headingley",
  "status": "active",
  "created_at": "2026-03-15T10:00:00Z",
  "expires_at": "2026-04-14T10:00:00Z"
}
```

Possible errors:

- `404` if `user_id` does not exist
- `422` if validation fails

## Events

### `GET /api/events`

List community events.

Query params:

- `location`
- `status`
- `upcoming_only` default `true`
- `limit` default `20`
- `offset` default `0`

### `POST /api/events`

Create an event.

Example request:

```json
{
  "user_id": 1,
  "title": "Football match",
  "description": "Friendly game",
  "event_date": "2030-03-16T18:00:00Z",
  "location": "Hyde Park"
}
```

Example success response:

```json
{
  "id": 1,
  "user_id": 1,
  "title": "Football match",
  "description": "Friendly game",
  "event_date": "2030-03-16T18:00:00Z",
  "location": "Hyde Park",
  "status": "active",
  "created_at": "2026-03-15T10:00:00Z"
}
```

Possible errors:

- `404` if `user_id` does not exist
- `422` if validation fails

## Summary

### `GET /api/summary`

Returns an aggregated summary of active exchange offers, active listings, and upcoming events.

Example response:

```json
{
  "generated_at": "2026-03-15T10:00:00Z",
  "exchange_offers": {
    "count": 1,
    "items": [
      {
        "id": 1,
        "title": "PEN to GBP",
        "location": "Leeds city centre",
        "amount": "300.00",
        "currency": "PEN",
        "secondary_currency": "GBP",
        "event_date": null,
        "description": "Available after 6pm"
      }
    ]
  },
  "listings": {
    "count": 1,
    "items": []
  },
  "events": {
    "count": 1,
    "items": []
  }
}
```

## Meta webhook

### `GET /webhook/meta`

Verification endpoint used by Meta.

Example:

```bash
curl "http://localhost:8000/webhook/meta?hub.mode=subscribe&hub.verify_token=change-me&hub.challenge=12345"
```

Successful response body:

```text
12345
```

### `POST /webhook/meta`

Receives inbound Meta payloads and processes supported text messages.

Example request:

```json
{
  "entry": [
    {
      "changes": [
        {
          "value": {
            "contacts": [
              {
                "profile": {
                  "name": "Kenji"
                }
              }
            ],
            "messages": [
              {
                "from": "447700900123",
                "id": "wamid.test",
                "timestamp": "1741975200",
                "type": "text",
                "text": {
                  "body": "I want to exchange 300 soles for pounds in Leeds city centre"
                }
              }
            ]
          }
        }
      ]
    }
  ]
}
```

Example response:

```json
{
  "status": "accepted",
  "processed_messages": 1
}
```

## Notes

- The REST API is useful for admin tooling, testing, and future frontend integration.
- The webhook path is the primary production entrypoint for the bot itself.
- The current API does not yet expose authentication or authorization.
