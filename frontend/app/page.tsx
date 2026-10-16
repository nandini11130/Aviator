import Link from "next/link";
import { CABIN_TIERS } from "@/lib/types";

export default function LandingPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <nav className="mb-16 flex items-center justify-between">
        <span className="text-xl font-bold tracking-tight">✈️ Aviator</span>
        <Link
          href="/login"
          className="rounded-full bg-aviator-sky px-5 py-2 text-sm font-semibold hover:bg-blue-600"
        >
          Sign in
        </Link>
      </nav>

      <section className="mb-20 text-center">
        <h1 className="mx-auto max-w-3xl text-4xl font-extrabold leading-tight sm:text-5xl">
          Fly on <span className="text-aviator-gold">empty seats</span>, for a fraction of the fare.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-blue-100/80">
          Subscribe to a cabin class. See last-minute empty seats appear in real time. Book one
          for a small token amount plus GST — e.g. ₹500 + GST for Economy — right up to departure.
        </p>
        <Link
          href="/login"
          className="mt-8 inline-block rounded-full bg-aviator-gold px-8 py-3 text-base font-semibold text-aviator-midnight hover:brightness-95"
        >
          Find tonight&apos;s empty seats
        </Link>
      </section>

      <section className="grid gap-6 sm:grid-cols-3">
        {CABIN_TIERS.map((tier) => (
          <div
            key={tier.tier}
            className="rounded-2xl border border-white/10 bg-white/5 p-6 text-left shadow-xl"
          >
            <h2 className="text-xl font-bold">{tier.label}</h2>
            <p className="mt-1 text-sm text-blue-100/70">
              ₹{tier.monthlyFeeInr}/month membership
            </p>
            <p className="mt-4 text-3xl font-extrabold">
              ₹{tier.perSeatFromInr}
              <span className="text-base font-medium text-blue-100/70"> + GST / seat</span>
            </p>
            <p className="mt-4 text-sm text-blue-100/70">
              Unlocks last-minute {tier.label.toLowerCase()} seats across every subscribed route.
            </p>
          </div>
        ))}
      </section>

      <section className="mt-20 grid gap-8 sm:grid-cols-4">
        {[
          ["1. Subscribe", "Pick Economy, Business, or First and activate your membership."],
          ["2. Watch live deals", "Our agents track empty seats across flights in real time."],
          ["3. Book in one tap", "Pay the token amount + GST to lock in the seat instantly."],
          ["4. Ask the concierge", "Chat with Aviator's AI concierge for recommendations anytime."],
        ].map(([title, body]) => (
          <div key={title}>
            <h3 className="font-semibold text-aviator-gold">{title}</h3>
            <p className="mt-2 text-sm text-blue-100/70">{body}</p>
          </div>
        ))}
      </section>
    </main>
  );
}
