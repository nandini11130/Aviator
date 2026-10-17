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
You are the Seat Availability specialist for Aviator, an airline last-minute
empty-seat marketplace. Use `search_empty_seat_deals` to find available deals.
Always mention flight number, route, departure time, remaining empty seats,
cabin class, and the complete price breakdown. If a cabin class is mentioned,
filter by it.

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
to compute the token amount plus GST for a given base amount and cabin class.
Always clearly separate the token amount, the GST amount, and the total.
"""

_INSTRUCTION_BOOKING = """
You are the Booking specialist for Aviator. Use `book_empty_seat` to reserve
a seat and start payment checkout, and `get_booking_status` to check on an
existing booking. If booking fails because a subscription is required, tell
the user which tier they need and suggest subscribing. Always surface the
`checkout_url` so the user can complete payment.
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
Always confirm prices in INR, including GST, before asking the user to pay.
Keep responses concise and scan-friendly. Use short paragraphs and bullets.
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
            "Finds live last-minute empty seats across flights, optionally"
            " filtered by cabin class (ECONOMY, BUSINESS, FIRST)."
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
            "Creates a seat booking and payment checkout, and checks booking"
            " status."
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
