import "./globals.css";

export const metadata = {
  title: "CargoTrk | Universal Cargo Intelligence & Multi-Carrier Tracking API",
  description: "Real-time enterprise cargo tracking platform for 20+ air cargo carriers and all major ocean shipping lines. Metered subscription and API-first data orchestration.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      </head>
      <body>{children}</body>
    </html>
  );
}
