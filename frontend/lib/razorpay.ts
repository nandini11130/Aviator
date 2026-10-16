export interface RazorpayOrder {
  key_id: string;
  order_id: string;
  amount: number;
  currency: string;
}

export interface RazorpayPaymentResponse {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

interface RazorpayFailure {
  error?: { description?: string };
}

interface RazorpayOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  order_id: string;
  handler: (response: RazorpayPaymentResponse) => void;
  modal: { ondismiss: () => void };
  theme: { color: string };
}

interface RazorpayInstance {
  open: () => void;
  on: (event: "payment.failed", handler: (response: RazorpayFailure) => void) => void;
}

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => RazorpayInstance;
  }
}

let scriptLoad: Promise<void> | undefined;

function loadRazorpay(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  if (!scriptLoad) {
    scriptLoad = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => {
        scriptLoad = undefined;
        reject(new Error("Could not load Razorpay Checkout. Check your connection and try again."));
      };
      document.body.appendChild(script);
    });
  }
  return scriptLoad;
}

export async function openRazorpayCheckout(
  order: RazorpayOrder,
  description: string
): Promise<RazorpayPaymentResponse> {
  await loadRazorpay();
  if (!window.Razorpay) {
    throw new Error("Razorpay Checkout did not initialize. Please try again.");
  }
  const Razorpay = window.Razorpay;

  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (callback: () => void) => {
      if (settled) return;
      settled = true;
      callback();
    };
    const checkout = new Razorpay({
      key: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || order.key_id,
      amount: order.amount,
      currency: order.currency,
      name: "Aviator",
      description,
      order_id: order.order_id,
      handler: (response) => finish(() => resolve(response)),
      modal: {
        ondismiss: () =>
          finish(() => reject(new Error("Payment was cancelled before completion."))),
      },
      theme: { color: "#60a5fa" },
    });
    checkout.on("payment.failed", (response) =>
      finish(() =>
        reject(new Error(response.error?.description || "Razorpay payment failed."))
      )
    );
    checkout.open();
  });
}
