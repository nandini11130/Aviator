"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ChatWidget } from "@/components/ChatWidget";
import { FlightDealCard } from "@/components/FlightDealCard";
import { TierCard } from "@/components/TierCard";
import {
  CABIN_TIERS,
  type Booking,
  type CabinClass,
  type Deal,
  type DemoPass,
  type Subscription,
  formatMoney,
} from "@/lib/types";
import { openRazorpayCheckout } from "@/lib/razorpay";

const POLL_INTERVAL_MS = 15_000;

export default function DashboardPage() {
  const router = useRouter();
  const { userId, loading, callApi, signOutUser } = useAuth();
  const isLocalDevelopment = process.env.NODE_ENV !== "production";

  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [subscriptionLoaded, setSubscriptionLoaded] = useState(false);
  const [demoPass, setDemoPass] = useState<DemoPass | null>(null);
  const [demoPassLoaded, setDemoPassLoaded] = useState(false);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [visibleDealCount, setVisibleDealCount] = useState(12);
  const [originFilter, setOriginFilter] = useState("");
  const [destinationFilter, setDestinationFilter] = useState("");
  const [airlineFilter, setAirlineFilter] = useState("");
  const [cabinFilter, setCabinFilter] = useState<CabinClass | "">("");
  const [departureDateFilter, setDepartureDateFilter] = useState("");
  const [sortBy, setSortBy] = useState<
    "lowest_price" | "earliest_departure" | "most_estimated_seats"
  >("lowest_price");
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [busyTier, setBusyTier] = useState<CabinClass | null>(null);
  const [buyingDemoPass, setBuyingDemoPass] = useState(false);
  const [busyFlightId, setBusyFlightId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const activeSubscription =
    subscription?.status.toUpperCase() === "ACTIVE" ? subscription : null;
  const activeTierIndex = activeSubscription
    ? CABIN_TIERS.findIndex((tier) => tier.tier === activeSubscription.tier)
    : -1;
  const visibleTiers = activeSubscription
    ? CABIN_TIERS.slice(activeTierIndex + 1)
    : CABIN_TIERS;
  const filteredDeals = useMemo(() => {
    const origin = originFilter.trim().toUpperCase();
    const destination = destinationFilter.trim().toUpperCase();
    const matches = deals.filter(
      (deal) =>
        deal.origin.toUpperCase().includes(origin) &&
        deal.destination.toUpperCase().includes(destination) &&
        deal.airline.toLowerCase().includes(airlineFilter.trim().toLowerCase()) &&
        (!cabinFilter || deal.cabin_class === cabinFilter) &&
        (!departureDateFilter ||
          (() => {
            const departure = new Date(deal.departure_time);
            const localDate = [
              departure.getFullYear(),
              String(departure.getMonth() + 1).padStart(2, "0"),
              String(departure.getDate()).padStart(2, "0"),
            ].join("-");
            return localDate === departureDateFilter;
          })())
    );
    return matches.sort((first, second) => {
      if (sortBy === "lowest_price") {
        return first.price.total.amount_minor - second.price.total.amount_minor;
      }
      if (sortBy === "most_estimated_seats") {
        return second.empty_seats - first.empty_seats;
      }
      return (
        new Date(first.departure_time).getTime() -
        new Date(second.departure_time).getTime()
      );
    });
  }, [deals, originFilter, destinationFilter, airlineFilter, cabinFilter, departureDateFilter, sortBy]);
  const visibleDeals = filteredDeals.slice(0, visibleDealCount);
  const routeCount = new Set(
    filteredDeals.map((deal) => `${deal.origin}-${deal.destination}`)
  ).size;
  const airlineCount = new Set(filteredDeals.map((deal) => deal.airline)).size;
  const lowestEstimatedFare = filteredDeals.reduce<Deal | null>(
    (lowest, deal) =>
      !lowest || deal.price.total.amount_minor < lowest.price.total.amount_minor
        ? deal
        : lowest,
    null
  );

  useEffect(() => {
    if (!loading && !userId) {
      router.replace("/login");
    }
  }, [loading, userId, router]);

  useEffect(() => {
    setVisibleDealCount(12);
  }, [
    originFilter,
    destinationFilter,
    airlineFilter,
    cabinFilter,
    departureDateFilter,
    sortBy,
  ]);

  const refresh = useCallback(async () => {
    try {
      const [sub, pass, liveDeals, myBookings] = await Promise.all([
        callApi<Subscription | null>("/api/subscriptions/me"),
        callApi<DemoPass>("/api/payments/demo-pass"),
        callApi<Deal[]>("/api/flights/empty-seats"),
        callApi<Booking[]>("/api/bookings"),
      ]);
      setSubscription(sub);
      setSubscriptionLoaded(true);
      setDemoPass(pass);
      setDemoPassLoaded(true);
      setDeals(liveDeals);
      setBookings(myBookings);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [callApi]);

  const handleBuyDemoPass = async () => {
    setBuyingDemoPass(true);
    setError(null);
    setNotice(null);
    try {
      const order = await callApi<{
        key_id: string;
        order_id: string;
        amount: number;
        currency: string;
      }>("/api/payments/demo-pass-order", { method: "POST" });
      const payment = await openRazorpayCheckout(order, "Aviator one-time demo pass");
      await callApi("/api/payments/verify", {
        method: "POST",
        body: JSON.stringify(payment),
      });
      setNotice("Demo pass activated. You can now start demo booking checkout.");
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBuyingDemoPass(false);
    }
  };

  const activateLocalDemoPass = async () => {
    setError(null);
    setNotice(null);
    try {
      await callApi<DemoPass>("/api/payments/dev-demo-pass", { method: "POST" });
      setNotice("Local test pass activated without a payment.");
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const showDemoPass = () => {
    document.getElementById("demo-pass")?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  };

  useEffect(() => {
    if (!userId) return;
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [userId, refresh]);

  const handleSubscribe = async (tier: CabinClass) => {
    setBusyTier(tier);
    setError(null);
    try {
      const order = await callApi<{
        key_id: string;
        order_id: string;
        amount: number;
        currency: string;
      }>("/api/payments/subscription-order", {
        method: "POST",
        body: JSON.stringify({ tier }),
      });
      const payment = await openRazorpayCheckout(order, `${tier} membership`);
      await callApi("/api/payments/verify", {
        method: "POST",
        body: JSON.stringify(payment),
      });
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusyTier(null);
    }
  };

  const handleBook = async (deal: Deal) => {
    setBusyFlightId(deal.flight_id);
    setError(null);
    setNotice(null);
    try {
      const order = await callApi<{
        booking_id: string;
        key_id: string;
        order_id: string;
        amount: number;
        currency: string;
        estimated_total: { amount_minor: number; currency: string };
        demo_only: boolean;
      }>("/api/payments/booking-order", {
        method: "POST",
        body: JSON.stringify({ flight_id: deal.flight_id, cabin_class: deal.cabin_class }),
      });
      if (
        order.amount !== deal.price.total.amount_minor ||
        order.currency !== deal.price.total.currency
      ) {
        throw new Error(
          "The flight estimate changed. Please review the latest amount and try again."
        );
      }
      const payment = await openRazorpayCheckout(
        order,
        `Demo booking · ${deal.flight_number} · no airline ticket`
      );
      await callApi("/api/payments/verify", {
        method: "POST",
        body: JSON.stringify(payment),
      });
      setNotice(
        `Demo payment received: ${formatMoney(order.estimated_total)}. This confirms only a demo booking; no airline seat was reserved and no ticket was issued.`
      );
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusyFlightId(null);
    }
  };

  if (loading || !userId) {
    return <main className="p-10 text-center">Loading...</main>;
  }

  return (
    <main className="mx-auto max-w-7xl px-5 py-8 pb-28 sm:px-8 lg:px-12">
      <header className="mb-10 flex items-center justify-between border-b border-white/10 pb-5">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-aviator-gold text-xl text-aviator-midnight">✈</span>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Aviator</h1>
            <p className="text-xs text-blue-100/50">Flexible travel, better choices</p>
          </div>
        </div>
        <button onClick={signOutUser} className="text-sm text-blue-100/60 hover:text-white">
          Sign out
        </button>
      </header>

      <section className="mb-10 overflow-hidden rounded-[2rem] border border-white/10 bg-[radial-gradient(ellipse_at_85%_15%,rgba(61,120,242,0.22),transparent_45%),linear-gradient(135deg,rgba(255,255,255,0.07),rgba(255,255,255,0.02))] p-6 sm:p-9">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-aviator-gold">
          Flexible travel discovery
        </p>
        <div className="mt-3 grid gap-6 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <h2 className="max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
              Find a flight that fits your plans — and your budget.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-blue-100/65 sm:text-base">
              Compare scheduled routes by price estimate, departure, airline,
              and cabin. Ask the ADK concierge to search using natural-language
              preferences.
            </p>
          </div>
          <a
            href="#flight-search"
            className="inline-flex w-fit items-center rounded-full bg-aviator-gold px-5 py-3 text-sm font-semibold text-aviator-midnight transition hover:brightness-110"
          >
            Explore flight options ↓
          </a>
        </div>
        <div className="mt-7 grid grid-cols-2 gap-3 lg:max-w-2xl">
          {[
            { label: "Matching options", value: filteredDeals.length },
            { label: "Routes", value: routeCount },
            { label: "Airlines", value: airlineCount },
            {
              label: "Lowest estimate",
              value: lowestEstimatedFare
                ? formatMoney(lowestEstimatedFare.price.total)
                : "—",
            },
          ].map((metric) => (
            <div
              key={metric.label}
              className="rounded-2xl border border-white/10 bg-black/15 px-4 py-3"
            >
              <p className="text-[11px] uppercase tracking-wider text-blue-100/45">
                {metric.label}
              </p>
              <p className="mt-1 text-lg font-semibold">{metric.value}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-blue-100/45">
          Schedule-based estimates only — not confirmed fares, unsold seats, or
          airline inventory.
        </p>
      </section>

      {error && (
        <div className="mb-6 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-6 rounded-xl border border-emerald-400/30 bg-emerald-500/10 p-4 text-sm text-emerald-100">
          {notice}
        </div>
      )}

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">Your membership</h2>
        {!subscriptionLoaded ? (
          <p className="text-sm text-blue-100/60">Checking your membership…</p>
        ) : (
          <>
            {activeSubscription && (
              <p className="mb-4 text-sm text-blue-100/70">
                Your current plan is{" "}
                {CABIN_TIERS[activeTierIndex]?.label ?? activeSubscription.tier}.
                {visibleTiers.length > 0
                  ? " Choose a higher tier to upgrade."
                  : " You’re already on the highest tier."}
              </p>
            )}
            {!activeSubscription && (
              <p className="mb-4 text-sm text-blue-100/70">
                Choose one plan to get started.
              </p>
            )}
            <div
              className={`grid gap-4 ${
                activeSubscription ? "max-w-3xl sm:grid-cols-2" : "sm:grid-cols-3"
              }`}
            >
              {visibleTiers.map((tier) => (
                <TierCard
                  key={tier.tier}
                  tier={tier.tier}
                  label={tier.label}
                  monthlyFeeInr={tier.monthlyFeeInr}
                  isActive={false}
                  busy={busyTier === tier.tier}
                  onSubscribe={handleSubscribe}
                />
              ))}
            </div>
          </>
        )}
      </section>

      <section
        id="demo-pass"
        className="mb-10 rounded-2xl border border-aviator-gold/20 bg-aviator-gold/5 p-5"
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">One-time demo pass · ₹1</h2>
            <p className="mt-1 max-w-2xl text-sm text-blue-100/70">
              Unlock paid demo booking checkout across all cabin classes.
              Flight search is free; each booking checkout charges its displayed
              estimated total. No ticket is issued and no airline seat is
              reserved. This pass is one-time, not a subscription.
            </p>
            {demoPass?.active && (
              <p className="mt-2 text-sm font-semibold text-emerald-200">
                Demo pass active
              </p>
            )}
          </div>
          {!demoPass?.active && demoPassLoaded && (
            <div className="flex shrink-0 flex-col gap-2">
              <button
                type="button"
                disabled={buyingDemoPass}
                onClick={handleBuyDemoPass}
                className="rounded-xl bg-aviator-sky px-5 py-3 text-sm font-semibold disabled:opacity-50"
              >
                {buyingDemoPass ? "Opening Razorpay..." : "Get demo pass for ₹1"}
              </button>
              {isLocalDevelopment && (
                <button
                  type="button"
                  onClick={activateLocalDemoPass}
                  className="text-xs text-blue-100/60 underline underline-offset-2 hover:text-white"
                >
                  Activate a local test pass (no payment)
                </button>
              )}
            </div>
          )}
          {!demoPassLoaded && (
            <span className="text-sm text-blue-100/60">Checking demo access…</span>
          )}
        </div>
      </section>

      <section id="flight-search" className="mb-12 scroll-mt-8">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-aviator-gold">
              Flight discovery
            </p>
            <h2 className="mt-1 text-2xl font-semibold">Explore schedules</h2>
          </div>
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-blue-100/60">
            {filteredDeals.length} matching options
          </span>
        </div>
        <p className="mb-3 text-sm text-blue-100/60">
          Filter by airport IATA code, such as DEL, LHR, or JFK. Domestic and
          international schedules are shown when returned by the provider.
        </p>
        <p className="mb-4 rounded-xl border border-aviator-gold/20 bg-aviator-gold/5 p-4 text-sm text-blue-100/80">
          Schedule data is from AviationStack. Seat availability and prices are
          estimates, not airline inventory or fares. Demo bookings are
          available to matching members or demo-pass holders, but do not reserve
          a seat or issue a ticket. Selecting Book opens Razorpay for the
          displayed estimated total as a demo payment; membership charges are
          separate.
        </p>
        <div className="mb-4 grid gap-3 rounded-2xl border border-white/10 bg-white/[0.035] p-4 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-sm text-blue-100/80">
            From (airport code)
            <input
              type="search"
              value={originFilter}
              onChange={(event) => setOriginFilter(event.target.value)}
              placeholder="e.g. DEL"
              className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-white placeholder:text-blue-100/40"
            />
          </label>
          <label className="text-sm text-blue-100/80">
            To (airport code)
            <input
              type="search"
              value={destinationFilter}
              onChange={(event) => setDestinationFilter(event.target.value)}
              placeholder="e.g. LHR"
              className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-white placeholder:text-blue-100/40"
            />
          </label>
          <label className="text-sm text-blue-100/80">
            Airline
            <input
              type="search"
              value={airlineFilter}
              onChange={(event) => setAirlineFilter(event.target.value)}
              placeholder="Any airline"
              className="mt-1 w-full rounded-xl border border-white/10 bg-[#0c142b] px-3 py-2 text-white placeholder:text-blue-100/40"
            />
          </label>
          <label className="text-sm text-blue-100/80">
            Cabin
            <select
              value={cabinFilter}
              onChange={(event) =>
                setCabinFilter(event.target.value as CabinClass | "")
              }
              className="mt-1 w-full rounded-xl border border-white/10 bg-[#0c142b] px-3 py-2 text-white"
            >
              <option value="">All cabins</option>
              {CABIN_TIERS.map((tier) => (
                <option key={tier.tier} value={tier.tier}>
                  {tier.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-blue-100/80">
            Departure date
            <input
              type="date"
              value={departureDateFilter}
              onChange={(event) => setDepartureDateFilter(event.target.value)}
              className="mt-1 w-full rounded-xl border border-white/10 bg-[#0c142b] px-3 py-2 text-white"
            />
          </label>
          <label className="text-sm text-blue-100/80">
            Sort options
            <select
              value={sortBy}
              onChange={(event) =>
                setSortBy(
                  event.target.value as
                    | "lowest_price"
                    | "earliest_departure"
                    | "most_estimated_seats"
                )
              }
              className="mt-1 w-full rounded-xl border border-white/10 bg-[#0c142b] px-3 py-2 text-white"
            >
              <option value="lowest_price">Lowest estimated total</option>
              <option value="earliest_departure">Earliest departure</option>
              <option value="most_estimated_seats">Most estimated seats</option>
            </select>
          </label>
          <button
            type="button"
            onClick={() => {
              setOriginFilter("");
              setDestinationFilter("");
              setAirlineFilter("");
              setCabinFilter("");
              setDepartureDateFilter("");
              setSortBy("lowest_price");
            }}
            className="self-end rounded-xl border border-white/10 px-4 py-2 text-sm text-blue-100/70 transition hover:bg-white/[0.06]"
          >
            Clear filters
          </button>
        </div>
        <div className="space-y-3">
          {filteredDeals.length === 0 && (
            <p className="text-sm text-blue-100/60">
              {deals.length === 0
                ? "No scheduled flights with estimated availability were found. Try again later."
                : "No flights match those route filters. Try another airport code."}
            </p>
          )}
          {visibleDeals.map((deal) => (
            <FlightDealCard
              key={`${deal.flight_id}-${deal.cabin_class}`}
              deal={deal}
              canBook={
                demoPass?.active ||
                (subscription?.tier === deal.cabin_class &&
                  subscription?.status === "ACTIVE")
              }
              busy={busyFlightId === deal.flight_id}
              onBook={handleBook}
              onGetAccess={showDemoPass}
            />
          ))}
          {visibleDealCount < filteredDeals.length && (
            <button
              type="button"
              onClick={() => setVisibleDealCount((count) => count + 12)}
              className="w-full rounded-xl border border-white/10 px-4 py-3 text-sm font-medium text-blue-100/70 transition hover:bg-white/[0.05] hover:text-white"
            >
              Show more options ({filteredDeals.length - visibleDealCount} remaining)
            </button>
          )}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Your bookings</h2>
        <div className="space-y-2">
          {bookings.length === 0 && <p className="text-sm text-blue-100/60">No bookings yet.</p>}
          {bookings.map((booking) => (
            <div
              key={booking.id}
              className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-3 text-sm"
            >
              <span>
                {booking.flight_id} · {booking.cabin_class}
              </span>
              <span className="font-semibold">
                {booking.status === "DEMO_CONFIRMED"
                  ? "Demo only · not a ticket"
                  : booking.status === "DEMO_PENDING_PAYMENT"
                    ? "Payment pending · demo only"
                    : booking.status === "DEMO_PAID"
                      ? "Paid demo · not a ticket"
                  : booking.status}
              </span>
            </div>
          ))}
        </div>
      </section>

      <ChatWidget />
    </main>
  );
}
