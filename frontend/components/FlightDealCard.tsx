import { formatMoney, type Deal } from "@/lib/types";

interface FlightDealCardProps {
  deal: Deal;
  canBook: boolean;
  busy: boolean;
  onBook: (deal: Deal) => void;
  onGetAccess: () => void;
}

export function FlightDealCard({
  deal,
  canBook,
  busy,
  onBook,
  onGetAccess,
}: FlightDealCardProps) {
  const departure = new Date(deal.departure_time);
  return (
    <article className="grid gap-5 rounded-2xl border border-white/10 bg-[linear-gradient(110deg,rgba(255,255,255,0.055),rgba(255,255,255,0.02))] p-5 transition hover:border-white/20 sm:grid-cols-[1fr_auto] sm:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md bg-white/[0.07] px-2 py-1 text-xs font-semibold text-blue-50">
            {deal.flight_number}
          </span>
          <span className="text-sm font-medium text-blue-100/80">{deal.airline}</span>
          <span className="rounded-full border border-aviator-gold/20 bg-aviator-gold/[0.08] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-aviator-gold">
            {deal.cabin_class}
          </span>
        </div>
        <div className="mt-4 flex items-center gap-4">
          <div>
            <p className="text-2xl font-semibold tracking-tight">{deal.origin}</p>
            <p className="mt-0.5 text-xs text-blue-100/50">Origin</p>
          </div>
          <div className="flex min-w-16 flex-1 items-center">
            <span className="h-2 w-2 rounded-full border border-aviator-gold" />
            <span className="h-px flex-1 border-t border-dashed border-white/20" />
            <span className="px-2 text-aviator-gold">✈</span>
            <span className="h-px flex-1 border-t border-dashed border-white/20" />
            <span className="h-2 w-2 rounded-full bg-aviator-gold" />
          </div>
          <div className="text-right">
            <p className="text-2xl font-semibold tracking-tight">{deal.destination}</p>
            <p className="mt-0.5 text-xs text-blue-100/50">Destination</p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-blue-100/65">
          <span>Departs {departure.toLocaleString()}</span>
          <span>{deal.empty_seats} estimated seat{deal.empty_seats === 1 ? "" : "s"}</span>
          <span>
            Updated {new Date(deal.data_updated_at).toLocaleString()}
          </span>
        </div>
        <p className="mt-2 text-[11px] text-blue-100/40">
          {deal.data_source}. Seat availability and fare are estimates only.
        </p>
      </div>
      <div className="flex items-center justify-between gap-4 border-t border-white/[0.08] pt-4 sm:block sm:border-0 sm:pt-0 sm:text-right">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-blue-100/45">
            Estimated total · checkout
          </p>
          <p className="mt-0.5 text-xl font-bold">{formatMoney(deal.price.total)}</p>
          <p className="mt-1 text-xs text-blue-100/55">
            {formatMoney(deal.price.token_amount)} + {formatMoney(deal.price.tax_amount)} GST
          </p>
        </div>
        <button
          disabled={busy}
          onClick={() => (canBook ? onBook(deal) : onGetAccess())}
          title={!canBook ? "A verified demo pass or matching active tier is required." : undefined}
          className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:cursor-wait disabled:opacity-50 sm:mt-3 ${
            canBook
              ? "bg-aviator-gold text-aviator-midnight hover:brightness-110"
              : "border border-aviator-gold/30 bg-aviator-gold/[0.08] text-aviator-gold hover:bg-aviator-gold/[0.14]"
          }`}
        >
          {busy ? "Opening payment..." : canBook ? "Book" : "Unlock with ₹1 pass"}
        </button>
      </div>
    </article>
  );
}
