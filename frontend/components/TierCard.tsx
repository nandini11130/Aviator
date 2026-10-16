import type { CabinClass } from "@/lib/types";

interface TierCardProps {
  tier: CabinClass;
  label: string;
  monthlyFeeInr: number;
  isActive: boolean;
  busy: boolean;
  onSubscribe: (tier: CabinClass) => void;
}

export function TierCard({ tier, label, monthlyFeeInr, isActive, busy, onSubscribe }: TierCardProps) {
  return (
    <div
      className={`rounded-2xl border p-5 ${
        isActive ? "border-aviator-gold bg-aviator-gold/10" : "border-white/10 bg-white/5"
      }`}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold">{label}</h3>
        {isActive && (
          <span className="rounded-full bg-aviator-gold px-2 py-0.5 text-xs font-semibold text-aviator-midnight">
            Active
          </span>
        )}
      </div>
      <p className="mt-1 text-sm text-blue-100/70">₹{monthlyFeeInr}/month membership</p>
      <button
        disabled={isActive || busy}
        onClick={() => onSubscribe(tier)}
        className="mt-4 w-full rounded-xl bg-aviator-sky px-4 py-2 text-sm font-semibold disabled:opacity-40"
      >
        {isActive ? "Subscribed" : busy ? "Starting checkout..." : "Subscribe"}
      </button>
    </div>
  );
}
