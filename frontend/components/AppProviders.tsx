"use client";

import { SessionProvider } from "next-auth/react";
import { ReactNode, useEffect } from "react";
import { apiUrl } from "@/lib/apiBase";

export function AppProviders({ children }: { children: ReactNode }) {
  // Wake the backend once per session to mitigate Azure cold start. /health is
  // public, so this works before the session and auth token are ready.
  useEffect(() => {
    try {
      if (sessionStorage.getItem("lanca_backend_warmed")) return;
      sessionStorage.setItem("lanca_backend_warmed", "1");
    } catch { /* ignore */ }
    fetch(apiUrl("/health"), { method: "GET", cache: "no-store" }).catch(() => {});
  }, []);

  return (
    <SessionProvider>
      {children}
    </SessionProvider>
  );
}
