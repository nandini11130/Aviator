# Aviator — Deployment Guide

This walks through taking Aviator from "runs on my laptop" to "live on
Google Cloud", using only free-tier resources. You said you have no GCP/
Firebase project yet — start at Step 1.

## 0. Run it locally first (no cloud account needed)

```powershell
# Backend
cd backend
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
# Edit .env: set GOOGLE_API_KEY from https://aistudio.google.com/app/apikey (free)
.\.venv\Scripts\uvicorn app.main:app --reload --port 8080

# Frontend (separate terminal)
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Open http://localhost:3000, click **Continue as demo user**, subscribe to a
tier, and book a seat. Everything works against in-memory data and the mock
payment gateway — no Stripe/Firebase/GCP account required yet.

## 1. Create a GCP project

1. Go to https://console.cloud.google.com/projectcreate and create a
   project (new accounts get $300 in free credits).
2. Note the **Project ID** (not the display name) — you'll use it everywhere
   below as `<PROJECT_ID>`.
3. Install the gcloud CLI: https://cloud.google.com/sdk/docs/install
4. Authenticate and select the project:
   ```powershell
   gcloud auth login
   gcloud config set project <PROJECT_ID>
   ```
5. Enable billing on the project (required even for free-tier usage) in the
   console under **Billing**.

## 2. Enable the required APIs

```powershell
gcloud services enable `
  run.googleapis.com `
  cloudbuild.googleapis.com `
  artifactregistry.googleapis.com `
  firestore.googleapis.com `
  aiplatform.googleapis.com `
  identitytoolkit.googleapis.com
```

## 3. Create a Firestore database

```powershell
gcloud firestore databases create --location=asia-south1
```
(Pick any supported region close to your users; `asia-south1` = Mumbai.)

## 4. Link a Firebase project (for Auth + Hosting)

1. Go to https://console.firebase.google.com/ → **Add project** → choose
   "Add Firebase to an existing GCP project" and pick `<PROJECT_ID>`.
2. **Build → Authentication → Get started → Sign-in method → Google** → enable.
3. **Build → Hosting → Get started** (just to provision it; the actual
   deploy happens via script later).
4. **Project settings → General → Your apps → Add app → Web app.** Copy the
   `apiKey`, `authDomain`, `projectId`, `appId` into
   `frontend/.env.local` as `NEXT_PUBLIC_FIREBASE_*`.
5. Install the Firebase CLI and log in:
   ```powershell
   npm install -g firebase-tools
   firebase login
   ```
6. Copy `.firebaserc.example` → `.firebaserc` and set your project id.

## 5. Get a Gemini API key (Google AI Studio — free)

https://aistudio.google.com/app/apikey → **Create API key**. Put it in
`backend/.env` locally and pass it to Cloud Run in Step 7 (as a secret, not
a plain env var, once you have real traffic).

## 6. Get Stripe test keys (free)

https://dashboard.stripe.com/register → **Developers → API keys** (use the
**test mode** keys, no card required). Put them in `backend/.env` as
`STRIPE_SECRET_KEY` / later create a webhook (Step 8) for
`STRIPE_WEBHOOK_SECRET`.

## 7. Deploy the backend to Cloud Run

```powershell
./infra/deploy-backend.ps1 -ProjectId <PROJECT_ID> -FirebaseProjectId <FIREBASE_PROJECT_ID> -Region asia-south1
```

If your Firebase project has a different project ID from your GCP project,
pass it separately with `-FirebaseProjectId <FIREBASE_PROJECT_ID>`.

This builds `backend/Dockerfile` with Cloud Build and deploys it with
`ENVIRONMENT=production`. After it finishes, grab the service URL:

```powershell
gcloud run services describe aviator-api --project <PROJECT_ID> --region asia-south1 --format "value(status.url)"
```

Then set the real secrets (don't bake them into source control):

```powershell
gcloud run services update aviator-api --project <PROJECT_ID> --region asia-south1 `
  --set-env-vars "GOOGLE_API_KEY=<your-ai-studio-key>,STRIPE_SECRET_KEY=<sk_test_...>,STRIPE_WEBHOOK_SECRET=<whsec_...>,FLIGHT_DATA_PROVIDER=mock"
```

> The Cloud Run service account needs the **Cloud Datastore User** role to
> read/write Firestore, and **Vertex AI User** if you switch Gemini to
> Vertex AI instead of an AI Studio key. Grant with:
> ```powershell
> gcloud projects add-iam-policy-binding <PROJECT_ID> `
>   --member="serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com" `
>   --role="roles/datastore.user"
> ```

## 8. Point Stripe's webhook at Cloud Run

Stripe dashboard → **Developers → Webhooks → Add endpoint** →
`https://<your-cloud-run-url>/api/webhooks/stripe`, subscribe to
`checkout.session.completed`. Copy the signing secret into
`STRIPE_WEBHOOK_SECRET` (Step 7's update command).

## 9. Deploy the frontend to Firebase Hosting

Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` to your Cloud Run
URL from Step 7, then:

```powershell
./infra/deploy-frontend.ps1
```

Your app is now live at `https://<PROJECT_ID>.web.app`.

## 10. Smoke test checklist

- [ ] `https://<cloud-run-url>/health` returns `{"status": "ok"}`
      (`/healthz` is also available)
- [ ] Sign in with Google on the live site
- [ ] Subscribe to a tier (real flow now goes through Stripe Checkout)
- [ ] See live empty-seat deals load
- [ ] Book a seat → redirected to Stripe Checkout → pay with a
      [test card](https://stripe.com/docs/testing) (`4242 4242 4242 4242`)
- [ ] Booking status flips to `CONFIRMED` after the webhook fires
- [ ] Chat with the concierge and ask it to find/book a seat

## Notes on "real-time" flight data

No public API — including Skyscanner's — publishes a true live empty-seat
count; airlines keep that in their own private inventory systems. Three
adapters are available (`FLIGHT_DATA_PROVIDER`):

- `mock` (default) — synthetic flights/seats, zero setup.
- `aviationstack` — real flight schedules from aviationstack.com's free
  tier; seat counts are still synthesised on top. Set `AVIATIONSTACK_API_KEY`.
- `amadeus` — real flights **and** real `numberOfBookableSeats` from the
  Amadeus Self-Service Flight Offers Search API — the same GDS data
  Skyscanner/Google Flights are themselves built on (GDS convention caps
  this number at 9, even when more seats are open). Free account at
  https://developers.amadeus.com; set `AMADEUS_API_KEY` and
  `AMADEUS_API_SECRET` (`AMADEUS_ENVIRONMENT=test` while developing, switch
  to `production` for real-world routes).

For a true seat-level feed you'd need a direct airline/GDS inventory
partnership (a business agreement, not a public API). Add it as one more
`FlightDataProvider` implementation; nothing else in the app needs to
change (see `FlightDataProvider` in `app/domain/ports.py`).
