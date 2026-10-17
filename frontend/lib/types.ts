export type CabinClass = "ECONOMY" | "BUSINESS" | "FIRST";

export interface Money {
  amount_minor: number;
  currency: string;
}

export interface PriceBreakdown {
  token_amount: Money;
  tax_amount: Money;
  total: Money;
}

export interface Deal {
  flight_id: string;
  flight_number: string;
  airline: string;
  origin: string;
  destination: string;
  departure_time: string;
  cabin_class: CabinClass;
  empty_seats: number;
  price: PriceBreakdown;
  data_source: string;
  availability_is_estimated: boolean;
  price_is_estimated: boolean;
  data_updated_at: string;
}

export interface Booking {
  id: string;
  flight_id: string;
  cabin_class: CabinClass;
  status: string;
  token_amount: Money;
  tax_amount: Money;
  total_amount: Money;
  checkout_url: string | null;
  created_at: string;
}

export interface Subscription {
  tier: CabinClass;
  status: string;
  started_at: string;
  renews_at: string | null;
}

export interface DemoPass {
  active: boolean;
  purchased_at: string | null;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
}

export const CABIN_TIERS: { tier: CabinClass; label: string; monthlyFeeInr: number; perSeatFromInr: number }[] = [
  { tier: "ECONOMY", label: "Economy", monthlyFeeInr: 499, perSeatFromInr: 500 },
  { tier: "BUSINESS", label: "Business", monthlyFeeInr: 999, perSeatFromInr: 1500 },
  { tier: "FIRST", label: "First", monthlyFeeInr: 1999, perSeatFromInr: 3000 },
];

export function formatMoney(money: Money): string {
  return `${money.currency} ${(money.amount_minor / 100).toFixed(2)}`;
}
