import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Stock Intelligence",
  description: "Evidence-first stock opportunity research terminal",
  icons: {
    icon: "/stock-intelligence-mark.svg",
    shortcut: "/stock-intelligence-mark.svg",
    apple: "/stock-intelligence-mark.svg",
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
