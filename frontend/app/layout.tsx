import type { Metadata } from "next";
import { DM_Serif_Display, Outfit } from "next/font/google";
import "./globals.css";

const dmSerif = DM_Serif_Display({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-serif",
  display: "swap",
});

const outfit = Outfit({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Confeções Lança - Lead Generation System",
  description: "Agentic lead generation ecosystem for boutique US menswear retailers",
  icons: {
    icon: "/lanca-logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt" className={`${dmSerif.variable} ${outfit.variable}`}>
      <body className="font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
