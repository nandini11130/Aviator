from datetime import datetime, timedelta, timezone

from app.domain.value_objects import CabinClass
from app.infrastructure.flight_data_providers import AviationStackFlightDataProvider


def test_aviationstack_provider_keeps_domestic_and_international_routes(monkeypatch):
    future = (datetime.now(timezone.utc) + timedelta(hours=3)).replace(microsecond=0)
    departure = future.isoformat()
    arrival = (future + timedelta(hours=2)).isoformat()
    payload = {
        "data": [
            {
                "flight": {"iata": "AI2433"},
                "airline": {"name": "Air India"},
                "departure": {"iata": "DEL", "scheduled": departure},
                "arrival": {"iata": "BOM", "scheduled": arrival},
            },
            {
                "flight": {"iata": "VS8864"},
                "airline": {"name": "Partner Airline"},
                "departure": {"iata": "DEL", "scheduled": departure},
                "arrival": {"iata": "BOM", "scheduled": arrival},
            },
            {
                "flight": {"iata": "AI9999"},
                "airline": {"name": "Air India"},
                "departure": {"iata": "DEL", "scheduled": departure},
                "arrival": {"iata": "LHR", "scheduled": arrival},
            },
            {
                "flight": {"iata": "BA123"},
                "airline": {"name": "British Airways"},
                "departure": {"iata": "BOM", "scheduled": departure},
                "arrival": {"iata": "LHR", "scheduled": arrival},
            },
        ]
    }

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    captured = {}

    def fake_get(url, *, params, timeout):
        captured.update(params)
        return Response()

    monkeypatch.setattr("app.infrastructure.flight_data_providers.httpx.get", fake_get)
    provider = AviationStackFlightDataProvider("test-key")

    first_result = provider.fetch_live_inventory()
    second_result = provider.fetch_live_inventory()

    assert "dep_iata" not in captured
    assert captured["limit"] == 100
    route_pairs = {
        (flight.origin, flight.destination) for flight, _ in first_result
    }
    assert route_pairs == {("DEL", "BOM"), ("DEL", "LHR"), ("BOM", "LHR")}
    assert len(first_result) == len(route_pairs) * len(CabinClass)
    assert [inventory.empty_seats for _, inventory in first_result] == [
        inventory.empty_seats for _, inventory in second_result
    ]
