import Link from "next/link";
import { CABIN_TIERS } from "@/lib/types";

function ArrowIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-4 w-4">
      <path
        d="M4.167 10h11.666m0 0L10 4.167M15.833 10 10 15.833"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PlaneIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <path
        d="m21 3-7.2 18-3.9-7.9L2 9.2 21 3Zm0 0L9.9 13.1"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const steps = [
  {
    number: "01",
    title: "Choose your cabin",
    description: "Pick Economy, Business, or First to find the membership that fits your travel style.",
  },
  {
    number: "02",
    title: "Explore flight schedules",
    description: "Browse selected Delhi domestic schedules with clearly labeled estimated availability and prices.",
  },
  {
    number: "03",
    title: "Try a demo booking",
    description: "Save a no-charge demo booking with a matching membership. It does not reserve a seat or issue a ticket.",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden bg-[#080d20] text-white">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-0 h-[740px] bg-[radial-gradient(ellipse_at_75%_10%,rgba(40,103,231,0.2),transparent_50%),radial-gradient(ellipse_at_10%_20%,rgba(231,181,73,0.08),transparent_40%)]" />

      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8 lg:px-12">
        <Link href="/" className="flex items-center gap-3" aria-label="Aviator home">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-aviator-gold text-aviator-midnight">
            <PlaneIcon />
          </span>
          <span className="text-xl font-bold tracking-tight">aviator</span>
        </Link>

        <nav className="flex items-center gap-3 sm:gap-7" aria-label="Main navigation">
          <a href="#how-it-works" className="hidden text-sm text-white/65 transition hover:text-white sm:block">
            How it works
          </a>
          <a href="#membership" className="hidden text-sm text-white/65 transition hover:text-white sm:block">
            Membership
          </a>
          <Link
            href="/login"
            className="rounded-full border border-white/15 px-4 py-2 text-sm font-medium transition hover:border-white/40 hover:bg-white/5 sm:px-5"
          >
            Sign in
          </Link>
        </nav>
      </header>

      <section className="relative z-10 mx-auto grid max-w-7xl items-center gap-14 px-5 pb-20 pt-12 sm:px-8 sm:pt-20 lg:grid-cols-[1.05fr_0.95fr] lg:gap-10 lg:px-12 lg:pb-28 lg:pt-24">
        <div className="max-w-2xl">
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-aviator-gold/20 bg-aviator-gold/[0.08] px-3.5 py-2 text-xs font-medium tracking-wide text-aviator-gold sm:text-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-aviator-gold" />
            Flight schedule demo
          </div>
          <h1 className="text-5xl font-semibold leading-[1.07] tracking-[-0.045em] sm:text-6xl lg:text-[4.35rem]">
            Find your next flight.
            <br />
            <span className="text-aviator-gold">Explore routes with Aviator.</span>
          </h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-slate-300 sm:text-lg sm:leading-8">
            Explore scheduled flights and estimated cabin availability. Join a
            membership to try the Aviator demo experience.
          </p>

          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/login"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-aviator-gold px-6 py-3.5 font-semibold text-aviator-midnight shadow-[0_8px_30px_rgba(231,181,73,0.16)] transition hover:-translate-y-0.5 hover:brightness-105"
            >
              Find your next flight <ArrowIcon />
            </Link>
            <a
              href="#how-it-works"
              className="inline-flex items-center justify-center rounded-full border border-white/15 px-6 py-3.5 font-medium text-white/85 transition hover:border-white/35 hover:bg-white/[0.04]"
            >
              See how it works
            </a>
          </div>

          <div className="mt-10 flex flex-wrap items-center gap-x-7 gap-y-3 border-t border-white/10 pt-6 text-sm text-slate-400">
            <span className="flex items-center gap-2">
              <span className="text-aviator-gold">✦</span> Economy to First
            </span>
            <span className="flex items-center gap-2">
              <span className="text-aviator-gold">✦</span> Secure checkout
            </span>
            <span className="flex items-center gap-2">
              <span className="text-aviator-gold">✦</span> Estimates clearly labeled
            </span>
          </div>
        </div>

        <div className="relative mx-auto w-full max-w-[540px] lg:ml-auto">
          <div className="absolute -inset-8 rounded-full bg-blue-500/10 blur-3xl" />
          <div className="relative rounded-[2rem] border border-white/10 bg-[#111a32]/90 p-4 shadow-2xl shadow-black/40 backdrop-blur sm:p-6">
            <div className="flex items-center justify-between px-1 pb-5">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
                  A little inspiration
                </p>
                <p className="mt-1 text-lg font-semibold">Your next getaway</p>
              </div>
              <span className="rounded-full border border-emerald-300/15 bg-emerald-300/[0.08] px-3 py-1.5 text-xs font-medium text-emerald-200">
                Flight preview
              </span>
            </div>

            <div className="rounded-2xl border border-white/[0.08] bg-[#0b1226] p-5 sm:p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs text-slate-400">A quick escape</p>
                  <p className="mt-1 text-sm font-semibold">Explore a new route</p>
                </div>
                <span className="rounded-lg bg-white/[0.06] px-2.5 py-1.5 text-xs text-slate-300">
                  One way
                </span>
              </div>
              <div className="mt-8 flex items-center justify-between gap-3">
                <div>
                  <p className="text-3xl font-semibold tracking-tight sm:text-4xl">DEL</p>
                  <p className="mt-1 text-xs text-slate-400">New Delhi</p>
                </div>
                <div className="flex flex-1 flex-col items-center px-2">
                  <div className="flex w-full items-center">
                    <span className="h-2 w-2 rounded-full border-2 border-aviator-gold" />
                    <span className="h-px flex-1 border-t border-dashed border-slate-600" />
                    <span className="rotate-45 text-aviator-gold"><PlaneIcon /></span>
                    <span className="h-px flex-1 border-t border-dashed border-slate-600" />
                    <span className="h-2 w-2 rounded-full bg-aviator-gold" />
                  </div>
                  <span className="mt-2 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    Your next stop
                  </span>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-semibold tracking-tight sm:text-4xl">GOI</p>
                  <p className="mt-1 text-xs text-slate-400">Goa</p>
                </div>
              </div>

              <div className="mt-8 flex items-center justify-between border-t border-white/10 pt-5">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-400/10 text-blue-200">
                    <PlaneIcon />
                  </span>
                  <div>
                    <p className="text-sm font-medium">Make room for a getaway</p>
                    <p className="mt-0.5 text-xs text-slate-400">Choose a cabin to get started</p>
                  </div>
                </div>
                <span className="text-2xl text-aviator-gold">✦</span>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-3">
              {CABIN_TIERS.map((tier) => (
                <div key={tier.tier} className="rounded-xl border border-white/[0.08] bg-white/[0.035] p-3">
                  <p className="text-xs text-slate-400">{tier.label}</p>
                  <p className="mt-1 text-sm font-semibold">₹{tier.monthlyFeeInr}<span className="text-[10px] font-normal text-slate-500"> /mo</span></p>
                </div>
              ))}
            </div>
          </div>
          <div className="absolute -bottom-5 -left-4 hidden rounded-2xl border border-white/10 bg-[#151e37] px-4 py-3 shadow-xl sm:block">
            <p className="text-xs text-slate-400">Pick your way to fly</p>
            <p className="mt-1 text-sm font-semibold"><span className="text-aviator-gold">3 cabins</span> · one destination</p>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="relative z-10 border-y border-white/[0.08] bg-white/[0.02]">
        <div className="mx-auto max-w-7xl px-5 py-16 sm:px-8 lg:px-12 lg:py-20">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-aviator-gold">A simpler journey</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Three steps to take off.</h2>
            <p className="mt-3 text-slate-400">Less searching. More looking forward to where you&apos;re going.</p>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {steps.map((step) => (
              <article key={step.number} className="rounded-2xl border border-white/[0.08] bg-[#0d1429] p-6 sm:p-7">
                <span className="text-sm font-semibold tracking-[0.16em] text-aviator-gold">{step.number}</span>
                <h3 className="mt-6 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">{step.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="membership" className="relative z-10 mx-auto max-w-7xl px-5 py-16 sm:px-8 lg:px-12 lg:py-24">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-aviator-gold">Memberships</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Pick your cabin.</h2>
          </div>
          <p className="max-w-md text-sm leading-6 text-slate-400">
            Choose a membership to explore schedules for that cabin. Membership
            fees are charged; demo bookings do not have a booking payment.
          </p>
        </div>

        <div className="mt-9 grid gap-4 md:grid-cols-3">
          {CABIN_TIERS.map((tier, index) => (
            <article
              key={tier.tier}
              className={`flex flex-col rounded-2xl border p-6 sm:p-7 ${
                index === 1
                  ? "border-aviator-gold/40 bg-gradient-to-b from-aviator-gold/[0.11] to-white/[0.025] shadow-[0_12px_50px_rgba(231,181,73,0.06)]"
                  : "border-white/10 bg-white/[0.025]"
              }`}
            >
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-semibold">{tier.label}</h3>
                {index === 1 && (
                  <span className="rounded-full bg-aviator-gold/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-aviator-gold">
                    Popular
                  </span>
                )}
              </div>
              <p className="mt-6 text-4xl font-semibold tracking-tight">
                ₹{tier.monthlyFeeInr}
                <span className="ml-1 text-sm font-normal text-slate-400">/ month</span>
              </p>
              <div className="my-6 h-px bg-white/10" />
              <p className="text-sm text-slate-300">
                Demo price estimate from{" "}
                <span className="font-semibold text-white">₹{tier.perSeatFromInr}</span>
                <span className="text-slate-400"> + estimated GST</span>
              </p>
              <p className="mt-3 flex-1 text-sm leading-6 text-slate-400">
                Explore scheduled {tier.label.toLowerCase()} cabin flights. Availability and
                prices are estimates, not confirmed airline inventory or fares.
              </p>
              <Link
                href="/login"
                className={`mt-7 inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-semibold transition hover:-translate-y-0.5 ${
                  index === 1
                    ? "bg-aviator-gold text-aviator-midnight hover:brightness-105"
                    : "border border-white/15 text-white hover:border-white/35 hover:bg-white/[0.04]"
                }`}
              >
                Explore {tier.label} <ArrowIcon />
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="relative z-10 px-5 pb-16 sm:px-8 lg:px-12 lg:pb-24">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 rounded-3xl border border-white/10 bg-[radial-gradient(ellipse_at_85%_20%,rgba(231,181,73,0.12),transparent_40%),#10182f] px-6 py-9 sm:px-10 sm:py-11 lg:flex-row lg:items-center lg:px-14">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-aviator-gold">Your next trip starts here</p>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">Ready when you are.</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">Sign in, choose your cabin, and see where you could go.</p>
          </div>
          <Link
            href="/login"
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-full bg-white px-6 py-3.5 text-sm font-semibold text-aviator-midnight transition hover:-translate-y-0.5 hover:bg-blue-50"
          >
            Get started <ArrowIcon />
          </Link>
        </div>
      </section>

      <footer className="relative z-10 border-t border-white/[0.08]">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-6 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12">
          <span className="font-semibold tracking-wide text-slate-300">✈ Aviator</span>
          <span>
            Schedules are informational; seat counts and prices are estimates.
            Demo bookings do not reserve seats or issue tickets.
          </span>
        </div>
      </footer>
    </main>
  );
}
