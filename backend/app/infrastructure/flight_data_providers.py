"""Flight data provider adapters.

`MockFlightDataProvider` synthesises a realistic, fully self-contained set of
flights/seat inventories so the whole product works with zero external
contracts. `AviationStackFlightDataProvider` is a real adapter for
api.aviationstack.com's free tier: it pulls live flight schedules, but - like
every public aviation API - it has no seat-map/empty-seat feed, so empty-seat
counts are synthesised on top of real flight numbers. Swap in a GDS/airline
inventory feed later by adding another `FlightDataProvider` implementation;
nothing else in the app needs to change (Open/Closed Principle).
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone

import httpx

from app.domain.entities import Flight, SeatInventory
from app.domain.ports import FlightDataProvider
from app.domain.value_objects import CabinClass, Money

# Indian domestic and international routes, served by major carriers. Airport
# codes are IATA; Amadeus/AviationStack both recognise them directly.
_ROUTES = [
    ("DEL", "BOM", "Air India", "AI"),
    ("BOM", "BLR", "IndiGo", "6E"),
    ("BLR", "HYD", "Air India", "AI"),
    ("DEL", "GOI", "SpiceJet", "SG"),
    ("MAA", "DEL", "Air India", "AI"),
    ("CCU", "BOM", "IndiGo", "6E"),
    ("DEL", "PNQ", "IndiGo", "6E"),
    ("BOM", "AMD", "Akasa Air", "QP"),
    ("DEL", "LKO", "IndiGo", "6E"),
    ("BLR", "COK", "Air India Express", "IX"),
    ("HYD", "VTZ", "IndiGo", "6E"),
    ("DEL", "JAI", "SpiceJet", "SG"),
    ("BOM", "GOI", "Akasa Air", "QP"),
    ("CCU", "GAU", "IndiGo", "6E"),
    ("DEL", "IXC", "Air India", "AI"),
    ("MAA", "BLR", "IndiGo", "6E"),
    ("DEL", "DXB", "Air India", "AI"),
    ("DEL", "SIN", "IndiGo", "6E"),
    ("BOM", "LHR", "British Airways", "BA"),
    ("BLR", "BKK", "Thai Airways", "TG"),
]

_BASE_TOKEN_MINOR: dict[CabinClass, int] = {
    CabinClass.ECONOMY: 50_000,  # INR 500
    CabinClass.BUSINESS: 150_000,  # INR 1500
    CabinClass.FIRST: 300_000,  # INR 3000
}

_MAX_EMPTY_SEATS: dict[CabinClass, int] = {
    CabinClass.ECONOMY: 6,
    CabinClass.BUSINESS: 3,
    CabinClass.FIRST: 1,
}


class MockFlightDataProvider(FlightDataProvider):
    """Deterministic-ish synthetic data, reseeded on every call so the demo
    always looks "live" without needing a real-time job scheduler.
    """

    def __init__(self, seed: int | None = None):
        self._random = random.Random(seed)

    def fetch_live_inventory(self) -> list[tuple[Flight, SeatInventory]]:
        now = datetime.now(timezone.utc)
        results: list[tuple[Flight, SeatInventory]] = []
        for index, (origin, destination, airline, code) in enumerate(_ROUTES):
            departure = now + timedelta(hours=self._random.randint(2, 20))
            flight = Flight(
                id=f"{code}{100 + index}-{departure.strftime('%Y%m%d')}",
                flight_number=f"{code}{100 + index}",
                airline=airline,
                origin=origin,
                destination=destination,
                departure_time=departure,
                arrival_time=departure + timedelta(hours=self._random.randint(1, 4)),
            )
            for cabin_class in CabinClass:
                empty_seats = self._random.randint(0, _MAX_EMPTY_SEATS[cabin_class])
                results.append(
                    (
                        flight,
                        SeatInventory(
                            flight_id=flight.id,
                            cabin_class=cabin_class,
                            empty_seats=empty_seats,
                            base_token_amount=Money(_BASE_TOKEN_MINOR[cabin_class]),
                            updated_at=now,
                        ),
                    )
                )
        return results


class AviationStackFlightDataProvider(FlightDataProvider):
    """Real-time flight schedules from aviationstack.com's free tier.

    Empty-seat counts are not published by any public aviation API, so they
    are synthesised per class around a small, realistic "last-minute deal"
    range. Replace this synthesis with a real GDS/airline seat-map feed once
    you have one, behind the same `FlightDataProvider` interface.
    """

    def __init__(self, api_key: str, base_url: str = "https://api.aviationstack.com/v1"):
        self._api_key = api_key
        self._base_url = base_url

    def fetch_live_inventory(self) -> list[tuple[Flight, SeatInventory]]:
        response = httpx.get(
            f"{self._base_url}/flights",
            params={
                "access_key": self._api_key,
                "flight_status": "scheduled",
                "limit": 100,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json().get("data", [])

        results: list[tuple[Flight, SeatInventory]] = []
        now = datetime.now(timezone.utc)
        seen_segments: set[tuple[str, str, str, str]] = set()
        for entry in payload:
            departure_iso = entry.get("departure", {}).get("scheduled")
            arrival_iso = entry.get("arrival", {}).get("scheduled")
            origin = entry.get("departure", {}).get("iata")
            destination = entry.get("arrival", {}).get("iata")
            flight_number = entry.get("flight", {}).get("iata")
            if (
                not departure_iso
                or not arrival_iso
                or not origin
                or not destination
                or not flight_number
            ):
                continue
            departure_time = datetime.fromisoformat(departure_iso)
            if departure_time <= now:
                continue
            segment_key = (origin, destination, departure_iso, arrival_iso)
            if segment_key in seen_segments:
                continue
            seen_segments.add(segment_key)
            flight_id = f"{flight_number}-{departure_iso}"
            flight = Flight(
                id=flight_id,
                flight_number=flight_number,
                airline=entry.get("airline", {}).get("name", "Unknown"),
                origin=origin,
                destination=destination,
                departure_time=departure_time,
                arrival_time=datetime.fromisoformat(arrival_iso),
            )
            for cabin_class in CabinClass:
                estimate = random.Random(f"{flight_id}:{cabin_class.value}")
                empty_seats = estimate.randint(0, _MAX_EMPTY_SEATS[cabin_class])
                results.append(
                    (
                        flight,
                        SeatInventory(
                            flight_id=flight.id,
                            cabin_class=cabin_class,
                            empty_seats=empty_seats,
                            base_token_amount=Money(_BASE_TOKEN_MINOR[cabin_class]),
                            updated_at=now,
                        ),
                    )
                )
        return results


class AmadeusFlightOffersProvider(FlightDataProvider):
    """Real adapter for the Amadeus Self-Service "Flight Offers Search" API -
    the same GDS data Skyscanner, Google Flights, and every OTA are built on
    top of. Free developer account at https://developers.amadeus.com.

    `numberOfBookableSeats` is the industry-standard "seats left at this
    fare" figure (GDS convention caps the number it will ever report at 9,
    even when more are actually open). No public API - including
    Skyscanner's - publishes a more granular, truly live empty-seat count;
    that lives only inside each airline's private reservation system.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        environment: str = "test",
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = (
            "https://api.amadeus.com" if environment == "production" else "https://test.api.amadeus.com"
        )
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token
        response = httpx.post(
            f"{self._base_url}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._api_key,
                "client_secret": self._api_secret,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = time.time() + payload.get("expires_in", 1800) - 60
        return self._token

    def fetch_live_inventory(self) -> list[tuple[Flight, SeatInventory]]:
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        # "Last-minute" means tomorrow, not today: same-day searches routinely
        # return zero offers once today's booking cutoff has passed.
        departure_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc)
        results: list[tuple[Flight, SeatInventory]] = []

        for origin, destination, airline, _code in _ROUTES:
            for cabin_class in CabinClass:
                try:
                    response = httpx.get(
                        f"{self._base_url}/v2/shopping/flight-offers",
                        headers=headers,
                        params={
                            "originLocationCode": origin,
                            "destinationLocationCode": destination,
                            "departureDate": departure_date,
                            "adults": 1,
                            "travelClass": cabin_class.value,
                            "max": 1,
                            "currencyCode": "INR",
                        },
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    offers = response.json().get("data", [])
                except httpx.HTTPError:
                    # This route/date/cabin combination has no GDS offer right
                    # now - skip it rather than failing the whole refresh.
                    continue
                if not offers:
                    continue

                offer = offers[0]
                segment = offer["itineraries"][0]["segments"][0]
                flight_number = f"{segment['carrierCode']}{segment['number']}"
                flight = Flight(
                    id=f"{flight_number}-{departure_date}-{cabin_class.value}",
                    flight_number=flight_number,
                    airline=airline,
                    origin=origin,
                    destination=destination,
                    departure_time=datetime.fromisoformat(segment["departure"]["at"]),
                    arrival_time=datetime.fromisoformat(segment["arrival"]["at"]),
                )
                results.append(
                    (
                        flight,
                        SeatInventory(
                            flight_id=flight.id,
                            cabin_class=cabin_class,
                            empty_seats=int(offer.get("numberOfBookableSeats", 0)),
                            base_token_amount=Money(_BASE_TOKEN_MINOR[cabin_class]),
                            updated_at=now,
                        ),
                    )
                )
        return results
