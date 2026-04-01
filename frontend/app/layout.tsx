import type { Metadata } from "next";
import { Inter, Playfair_Display } from "next/font/google";
import "./globals.css";
import { AppProviders } from "@/components/AppProviders";
import { Toaster } from "sonner";

const inter = Inter({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Confeções Lança | Plataforma Comercial",
  description: "Plataforma de pesquisa e gestão comercial da Confeções Lança. Desde 1973.",
  icons: {
    icon: "/lanca-logo.png",
  },
};

import { Sidebar } from "@/components/Sidebar";

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
