"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ChatWidget } from "@/components/ChatWidget";
import { FlightDealCard } from "@/components/FlightDealCard";
import { TierCard } from "@/components/TierCard";
import { CABIN_TIERS, type Booking, type CabinClass, type Deal, type Subscription } from "@/lib/types";

const POLL_INTERVAL_MS = 15_000;

export default function DashboardPage() {
  const router = useRouter();
  const { userId, loading, callApi, signOutUser } = useAuth();

  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [busyTier, setBusyTier] = useState<CabinClass | null>(null);
  const [busyFlightId, setBusyFlightId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !userId) {
      router.replace("/login");
    }
  }, [loading, userId, router]);

  const refresh = useCallback(async () => {
    try {
      const [sub, liveDeals, myBookings] = await Promise.all([
        callApi<Subscription | null>("/api/subscriptions/me"),
        callApi<Deal[]>("/api/flights/empty-seats"),
        callApi<Booking[]>("/api/bookings"),
      ]);
      setSubscription(sub);
      setDeals(liveDeals);
      setBookings(myBookings);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [callApi]);

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
      // Dev-activate skips real payment so the tier unlocks instantly; swap
      // for the /api/subscriptions checkout_url flow once Stripe is live.
      await callApi("/api/subscriptions/dev-activate", {
        method: "POST",
        body: JSON.stringify({ tier }),
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
    try {
      const booking = await callApi<Booking>("/api/bookings", {
        method: "POST",
        body: JSON.stringify({ flight_id: deal.flight_id, cabin_class: deal.cabin_class }),
      });
      // Dev-confirm stands in for completing Stripe Checkout + webhook.
      await callApi(`/api/bookings/${booking.id}/dev-confirm`, { method: "POST" });
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
    <main className="mx-auto max-w-4xl px-6 py-10 pb-24">
      <header className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-bold">✈️ Aviator</h1>
        <button onClick={signOutUser} className="text-sm text-blue-100/60 hover:text-white">
          Sign out
        </button>
      </header>

      {error && (
        <div className="mb-6 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">Your membership</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {CABIN_TIERS.map((tier) => (
            <TierCard
              key={tier.tier}
              tier={tier.tier}
              label={tier.label}
              monthlyFeeInr={tier.monthlyFeeInr}
              isActive={subscription?.tier === tier.tier && subscription?.status === "ACTIVE"}
              busy={busyTier === tier.tier}
              onSubscribe={handleSubscribe}
            />
          ))}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">Live last-minute empty seats</h2>
        <div className="space-y-3">
          {deals.length === 0 && (
            <p className="text-sm text-blue-100/60">No empty seats right now — check back soon.</p>
          )}
          {deals.map((deal) => (
            <FlightDealCard
              key={`${deal.flight_id}-${deal.cabin_class}`}
              deal={deal}
              canBook={subscription?.tier === deal.cabin_class && subscription?.status === "ACTIVE"}
              busy={busyFlightId === deal.flight_id}
              onBook={handleBook}
            />
          ))}
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
              <span className="font-semibold">{booking.status}</span>
            </div>
          ))}
        </div>
      </section>

      <ChatWidget />
    </main>
  );
}
