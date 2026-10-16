import type { Metadata } from "next";
import { Providers } from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aviator — Last-minute empty seats, member prices",
  description:
    "Subscribe by cabin class and book last-minute empty seats for a small token amount plus GST.",
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
