"""The Google ADK multi-agent system: one root "concierge" agent the user
talks to, which delegates to four specialist sub-agents. ADK picks the right
sub-agent automatically based on each agent's `description`, so adding a new
specialist later (e.g. a RefundAgent) means adding one more `Agent` to
`sub_agents` - nothing else changes (Open/Closed Principle). Each sub-agent
is only given the tools it needs (Interface Segregation).
"""
from __future__ import annotations

from google.adk.agents import Agent

from app.config import Settings
from app.agents import tools

_INSTRUCTION_SEAT = """
You are the Flight Schedule specialist for Aviator. Use
`search_empty_seat_deals` to find scheduled flights. Always say that seat
availability and prices are estimates, not confirmed airline inventory or
fares. Mention flight number, route, departure time, estimated seats, cabin
class, and data update time. If a cabin class is mentioned, filter by it.

Format responses for readability:
- For two or more flights, use a Markdown table with columns Flight, Route,
  Departure, Cabin, Seats, Token, GST, and Total.
- For one flight, use a short heading and labeled bullet points.
- Show departure times in Asia/Kolkata local time, with date and timezone.
- Format currency as INR with two decimals. Do not concatenate multiple
  flights into one paragraph or repeat raw tool output.
- If no results are found, say so clearly; never invent availability.
"""

_INSTRUCTION_PRICING = """
You are the Pricing & Tax specialist for Aviator. Use `calculate_total_price`
to calculate an indicative demo amount plus GST for a given base amount and
cabin class. Always state that it is an estimate, and clearly separate the
token amount, GST amount, and total. Do not imply this is an airline fare.
"""

_INSTRUCTION_BOOKING = """
You are the Booking specialist for Aviator. `book_empty_seat` creates a
no-charge demo booking only; it does not reserve airline inventory or issue a
ticket. Always make that limitation clear. A matching active membership is
still required. Use `get_booking_status` to check an existing booking.
"""

_INSTRUCTION_SUPPORT = """
You are the Support specialist for Aviator. Use `get_subscription_policy` to
answer questions about subscription tiers, membership fees, and GST rules,
and `get_booking_status` to answer "where is my booking" questions. Be warm,
concise, and accurate - never invent prices or policies.
"""

_INSTRUCTION_ROOT = """
You are Aviator's concierge, the single assistant a traveller talks to. You
orchestrate four specialists: seat availability, pricing & tax, booking, and
support. Route each request to the right specialist, and if a request spans
multiple steps (e.g. "find and book me a seat"), call them in sequence.
Membership fees are paid through Razorpay. Never ask for a flight booking
payment: flight bookings are demos and do not reserve a real seat or issue a
ticket. Treat displayed flight prices and seat counts as estimates.
Keep responses concise and scan-friendly. Use short paragraphs and bullets.
Flight availability and prices shown by Aviator may be estimates. Demo
bookings never reserve a real airline seat or issue a ticket.
When presenting multiple flight options, use a Markdown table with one flight
per row and columns for flight, route, local departure time, cabin, seats,
token amount, GST, and total. Do not return several flight records as one
paragraph.
"""


def build_root_agent(settings: Settings) -> Agent:
    seat_agent = Agent(
        name="seat_availability_agent",
        model=settings.gemini_model,
        description=(
            "Finds scheduled flights and estimated availability, optionally "
            "filtered by cabin class (ECONOMY, BUSINESS, FIRST)."
        ),
        instruction=_INSTRUCTION_SEAT,
        tools=[tools.search_empty_seat_deals],
    )

    pricing_agent = Agent(
        name="pricing_tax_agent",
        model=settings.gemini_model,
        description="Calculates token amount + GST pricing for a seat booking.",
        instruction=_INSTRUCTION_PRICING,
        tools=[tools.calculate_total_price],
    )

    booking_agent = Agent(
        name="booking_agent",
        model=settings.gemini_model,
        description=(
            "Creates a no-charge demo booking and checks booking status; it "
            "does not reserve airline inventory or issue a ticket."
        ),
        instruction=_INSTRUCTION_BOOKING,
        tools=[tools.book_empty_seat, tools.get_booking_status],
    )

    support_agent = Agent(
        name="support_agent",
        model=settings.gemini_model,
        description=(
            "Answers FAQs about subscription tiers, membership fees, GST"
            " rules, and booking status."
        ),
        instruction=_INSTRUCTION_SUPPORT,
        tools=[tools.get_subscription_policy, tools.get_booking_status],
    )

    return Agent(
        name="aviator_concierge",
        model=settings.gemini_model,
        description="Main Aviator assistant that routes requests to specialist sub-agents.",
        instruction=_INSTRUCTION_ROOT,
        sub_agents=[seat_agent, pricing_agent, booking_agent, support_agent],
    )
