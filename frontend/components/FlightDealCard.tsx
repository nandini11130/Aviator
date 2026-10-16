import { formatMoney, type Deal } from "@/lib/types";

interface FlightDealCardProps {
  deal: Deal;
  canBook: boolean;
  busy: boolean;
  onBook: (deal: Deal) => void;
}

export function FlightDealCard({ deal, canBook, busy, onBook }: FlightDealCardProps) {
  const departure = new Date(deal.departure_time);
  return (
    <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-4">
      <div>
        <p className="font-semibold">
          {deal.flight_number} · {deal.airline}
        </p>
        <p className="text-sm text-blue-100/70">
          {deal.origin} → {deal.destination} · departs {departure.toLocaleString()}
        </p>
        <p className="mt-1 text-xs uppercase tracking-wide text-aviator-gold">
          {deal.cabin_class} · {deal.empty_seats} seat{deal.empty_seats === 1 ? "" : "s"} left
        </p>
      </div>
      <div className="text-right">
        <p className="text-lg font-bold">{formatMoney(deal.price.total)}</p>
        <p className="text-xs text-blue-100/60">
          {formatMoney(deal.price.token_amount)} + {formatMoney(deal.price.tax_amount)} GST
        </p>
        <button
          disabled={!canBook || busy}
          onClick={() => onBook(deal)}
          className="mt-2 rounded-lg bg-aviator-gold px-4 py-1.5 text-sm font-semibold text-aviator-midnight disabled:opacity-40"
        >
          {busy ? "Booking..." : "Book seat"}
        </button>
      </div>
    </div>
  );
}
