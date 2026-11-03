import type { Metadata } from "next";
import dynamic from "next/dynamic";
import localFont from "next/font/local";
import "./globals.css";
import { AppProviders } from "@/components/AppProviders";
import { Toaster } from "sonner";

// Bundled rather than fetched from Google at build time, which failed a deploy.
const inter = localFont({
  src: "./fonts/inter-latin-wght-normal.woff2",
  weight: "100 900",
  variable: "--font-sans",
  display: "swap",
});

const playfair = localFont({
  src: "./fonts/playfair-display-latin-wght-normal.woff2",
  weight: "400 900",
  variable: "--font-serif",
  display: "swap",
});

const Sidebar = dynamic(
  () => import("@/components/Sidebar").then((mod) => mod.Sidebar),
  {
    loading: () => (
      <aside className="w-[72px] lg:w-[260px] bg-[#111111] h-screen flex-shrink-0 border-r border-white/[0.06]" />
    ),
  }
);

export const metadata: Metadata = {
  title: "Confeções Lança | Plataforma Comercial",
  description: "Plataforma de pesquisa e gestão comercial da Confeções Lança. Desde 1973.",
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
    <html lang="pt" className={`${inter.variable} ${playfair.variable} scroll-smooth`}>
      <body className="font-sans antialiased text-foreground bg-background">
        <AppProviders>
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 overflow-y-auto">
              {children}
            </main>
          </div>
          <Toaster
            position="bottom-right"
            richColors
            toastOptions={{
              style: { borderRadius: '6px', fontSize: '13px' },
            }}
          />
        </AppProviders>
      </body>
    </html>
  );
}
