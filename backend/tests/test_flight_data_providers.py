from datetime import datetime, timedelta, timezone

from app.domain.value_objects import CabinClass
from app.infrastructure.flight_data_providers import AviationStackFlightDataProvider


def test_aviationstack_provider_filters_and_deduplicates_delhi_domestic_flights(monkeypatch):
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

    assert captured["dep_iata"] == "DEL"
    assert captured["limit"] == 100
    assert len(first_result) == len(CabinClass)
    assert all(flight.destination == "BOM" for flight, _ in first_result)
    assert [inventory.empty_seats for _, inventory in first_result] == [
        inventory.empty_seats for _, inventory in second_result
    ]
