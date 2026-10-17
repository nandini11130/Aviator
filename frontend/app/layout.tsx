import type { Metadata } from "next";
import { Providers } from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aviator — Flight schedules and demo bookings",
  description:
    "Compare scheduled flights using flexible preferences. Paid demo bookings use displayed estimated amounts and do not reserve airline seats.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-aviator-midnight text-white antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
