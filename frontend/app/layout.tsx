import type { Metadata } from "next";

import { Nav } from "@/components/nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "Construction Ops Automation",
  description:
    "Airtable operations system for bids, purchase orders and invoicing.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="flex h-full flex-col">
        <Nav />
        <main className="min-h-0 flex-1">{children}</main>
      </body>
    </html>
  );
}
