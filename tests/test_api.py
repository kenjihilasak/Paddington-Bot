"""REST API tests."""

from __future__ import annotations


def test_create_records_and_summary(client, create_user) -> None:
    user_id = create_user()

    exchange_response = client.post(
        "/api/exchange-offers",
        json={
            "user_id": user_id,
            "offer_currency": "PEN",
            "want_currency": "GBP",
            "amount": "300",
            "location": "Leeds city centre",
        },
    )
    assert exchange_response.status_code == 201

    listing_response = client.post(
        "/api/listings",
        json={
            "user_id": user_id,
            "title": "Microwave",
            "description": "Good condition",
            "price": "25",
            "currency": "GBP",
            "location": "Headingley",
        },
    )
    assert listing_response.status_code == 201

    event_response = client.post(
        "/api/events",
        json={
            "user_id": user_id,
            "title": "Football match",
            "description": "Friendly game",
            "event_date": "2030-03-16T18:00:00Z",
            "location": "Hyde Park",
        },
    )
    assert event_response.status_code == 201

    summary_response = client.get("/api/summary")
    assert summary_response.status_code == 200
    data = summary_response.json()
    assert data["exchange_offers"]["count"] == 1
    assert data["listings"]["count"] == 1
    assert data["events"]["count"] == 1


def test_exchange_offer_filters(client, create_user) -> None:
    user_id = create_user()
    payload = {
        "user_id": user_id,
        "offer_currency": "PEN",
        "want_currency": "GBP",
        "amount": "300",
        "location": "Leeds city centre",
    }
    assert client.post("/api/exchange-offers", json=payload).status_code == 201

    response = client.get("/api/exchange-offers", params={"offer_currency": "PEN"})
    assert response.status_code == 200
    assert len(response.json()) == 1

