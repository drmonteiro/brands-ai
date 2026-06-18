"use client";

import { SessionProvider } from "next-auth/react";
import { ReactNode, useEffect } from "react";
import { apiUrl } from "@/lib/apiBase";

export function AppProviders({ children }: { children: ReactNode }) {
  // Wake the backend (and warm its DB pool) once per session to mitigate
  // Azure cold start, so opening "Cidades guardadas" feels fast.
  useEffect(() => {
    try {
      if (sessionStorage.getItem("lanca_backend_warmed")) return;
      sessionStorage.setItem("lanca_backend_warmed", "1");
    } catch { /* ignore */ }
    fetch(apiUrl("/api/cities"), { method: "GET", cache: "no-store" }).catch(() => {});
  }, []);

  return (
    <SessionProvider>
      {children}
    </SessionProvider>
  );
}
