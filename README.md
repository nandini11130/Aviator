# ✈️ Aviator

A flight schedule and demo-booking experience. Flight search is free; a
one-time **₹1 Razorpay demo pass** unlocks paid demo checkout across cabin
classes. Each checkout charges the displayed estimated total; monthly
membership tiers (**Economy / Business / First**) are separate. Demo payments
do not reserve a real airline seat or issue a ticket.

Built with **Google ADK** (a 4-specialist multi-agent concierge over
Gemini), **Firebase** (Auth + Firestore + Hosting), and **Cloud Run**.

- [Architecture & SOLID design](docs/ARCHITECTURE.md)
- [Deployment guide (GCP/Firebase, from zero)](docs/DEPLOYMENT.md)

## Application flow

```mermaid
flowchart TD
    TRAVELER["Traveller"] --> WEB["Next.js frontend<br/>Firebase Hosting"]
    WEB -->|Sign in| AUTH["Firebase Authentication"]
    AUTH -->|Firebase ID token| WEB
    WEB --> API["FastAPI API<br/>Cloud Run"]
    WEB -->|Authenticated REST requests| API

    API -->|Search schedules and filters| SEARCH["Flight search use case"]
    SEARCH --> FLIGHTS["Flight data provider"]
    FLIGHTS -->|Scheduled flights and estimated seats/fares| API

    WEB -->|Chat question| CHAT["AI concierge endpoint"]
    CHAT -->|Clear route query| SEARCH
    CHAT -->|Other travel questions| ADK["Google ADK concierge"]
    ADK --> SPECIALISTS["Seat availability · Pricing · Booking · Support specialists"]
    SPECIALISTS -->|Tools call| USE_CASES["Application use cases"]

    WEB -->|Choose membership, demo pass, or demo booking| PAY_API["Razorpay order API"]
    PAY_API --> RAZORPAY["Razorpay Checkout"]
    RAZORPAY -->|Payment result| WEB
    WEB -->|Payment IDs and signature| VERIFY["Payment verification API"]
    VERIFY -->|Verify payment and ownership| RAZORPAY
    VERIFY -->|Verified subscription, demo pass, or demo booking| STORE["Firestore<br/>or local in-memory repositories"]
    VERIFY -->|Payment confirmation| WEB
    USE_CASES --> STORE
    STORE -->|Updated membership and booking state| API
    API -->|Confirmation and updated account| WEB
```

Flight schedules may be provided by an external schedule source, while seat
counts and fares are estimates. Demo checkout does not reserve airline
inventory or issue a ticket.

## Proposed solution wireframes

The diagrams below are conceptual screen layouts showing the main traveller
journey, not pixel-perfect designs.

```mermaid
flowchart LR
    subgraph HOME["1 · Discover"]
        direction TB
        H_NAV["AVIATOR                            Sign in"]
        H_HERO["Travel on your terms<br/>Make flexibility count."]
        H_CTA["Explore flights"]
        H_NAV --> H_HERO --> H_CTA
    end

    subgraph SEARCH["2 · Search flights"]
        direction TB
        S_NAV["AVIATOR                   Membership"]
        S_FILTERS["From [HYD]   To [PNQ]<br/>Date [Any date]   Cabin [Any cabin]"]
        S_NOTICE["Schedules shown with estimated seats and fares"]
        S_RESULT["6E337 · IndiGo<br/>HYD → PNQ · Economy<br/>Estimated total · View details"]
        S_NAV --> S_FILTERS --> S_NOTICE --> S_RESULT
    end

    subgraph CONCIERGE["3 · Ask Aviator AI"]
        direction TB
        C_TITLE["Aviator AI concierge"]
        C_PROMPT["Find Economy flights from Hyderabad to Pune"]
        C_REPLY["Matching schedule options<br/>Compare route, departure, and estimates"]
        C_TITLE --> C_PROMPT --> C_REPLY
    end

    subgraph CHECKOUT["4 · Demo checkout"]
        direction TB
        P_REVIEW["Review selected flight<br/>Estimated total and demo-only notice"]
        P_GATEWAY["Continue to Razorpay"]
        P_VERIFY["Payment verified"]
        P_DONE["Demo booking confirmation<br/>No airline seat reserved; no ticket issued"]
        P_REVIEW --> P_GATEWAY --> P_VERIFY --> P_DONE
    end

    HOME -->|Explore flights| SEARCH
    SEARCH -->|Ask a route question| CONCIERGE
    SEARCH -->|Choose a flight| CHECKOUT
    CONCIERGE -->|Review matching flights| SEARCH
```

## Repository layout

```
backend/    FastAPI + Google ADK agents (deploys to Cloud Run)
  app/domain/         entities, value objects, ports (interfaces)
  app/application/    use cases (business logic, framework-free)
  app/infrastructure/ Firestore/Stripe/Firebase/flight-data adapters
  app/agents/         Google ADK multi-agent system + tool functions
  app/api/            FastAPI routes + composition root (deps.py)
  tests/              unit tests against in-memory/mock adapters
frontend/   Next.js app (static export, deploys to Firebase Hosting)
infra/      firestore.rules, deploy scripts
docs/       architecture + deployment docs
```

## Quick start (zero cloud account required)

```powershell
# Backend
cd backend
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # set GOOGLE_API_KEY from aistudio.google.com (free)
.\.venv\Scripts\uvicorn app.main:app --reload --port 8080

# Frontend
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Visit http://localhost:3000 → **Continue as demo user** → browse flights →
chat with the concierge. Everything runs against in-memory
data and a mock payment gateway until you wire up real Firebase/Razorpay
credentials (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)).

## Run backend tests

```powershell
cd backend
py -m pytest tests -v
```

## Going live

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the full, from-scratch
walkthrough: creating a GCP project, enabling APIs, linking Firebase,
getting a free Gemini key, getting Stripe test keys, and deploying with
`infra/deploy-backend.ps1` (Cloud Run) and `infra/deploy-frontend.ps1`
(Firebase Hosting).
