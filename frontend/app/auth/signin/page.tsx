"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { Building2, Globe, Loader2, Lock, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function SignInInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/";
  const initialError = searchParams.get("error");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loadingAzure, setLoadingAzure] = useState(false);
  const [loadingAgent, setLoadingAgent] = useState(false);
  const [error, setError] = useState<string | null>(
    initialError ? "Não foi possível iniciar sessão. Tente novamente." : null
  );

  const handleAzure = () => {
    setLoadingAzure(true);
    signIn("azure-ad", { callbackUrl });
  };

  const handleAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoadingAgent(true);
    const res = await signIn("external-agent", {
      username,
      password,
      redirect: false,
      callbackUrl,
    });
    setLoadingAgent(false);
    if (res?.ok) {
      router.push(callbackUrl);
    } else {
      setError("Credenciais inválidas. Verifique o utilizador e a palavra-passe.");
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-[#111111] px-4 py-10">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="bg-white rounded-lg p-3 shadow-md mb-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/lanca-logo.png"
              alt="Confeções Lança"
              className="h-12 w-auto object-contain"
            />
          </div>
          <h1 className="text-white text-lg font-bold tracking-tight">
            Confeções Lança
          </h1>
          <p className="text-[#F5C518] text-[10px] font-bold uppercase tracking-[0.12em] mt-1">
            Plataforma Comercial
          </p>
        </div>

        <div className="bg-white rounded-xl border border-white/10 shadow-xl p-6">
          {error && (
            <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-[13px] text-rose-700">
              {error}
            </div>
          )}

          {/* Lança / Azure AD */}
          <div className="mb-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Equipa Lança
            </p>
            <Button
              onClick={handleAzure}
              disabled={loadingAzure}
              className="w-full h-11 bg-[#111111] hover:bg-[#222222] text-white rounded-md gap-2"
            >
              {loadingAzure ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Building2 className="h-4 w-4" />
              )}
              <span>Entrar com conta Lança</span>
            </Button>
          </div>

          {/* Divider */}
          <div className="flex items-center gap-3 my-5">
            <div className="h-px flex-1 bg-border" />
            <span className="text-[11px] text-muted-foreground">ou</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          {/* External agent credentials */}
          <form onSubmit={handleAgent}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
              <Globe className="h-3.5 w-3.5" />
              Agente externo
            </p>
            <div className="space-y-2.5">
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50" />
                <Input
                  type="text"
                  autoComplete="username"
                  placeholder="Utilizador"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="pl-9 h-11"
                  required
                />
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50" />
                <Input
                  type="password"
                  autoComplete="current-password"
                  placeholder="Palavra-passe"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-9 h-11"
                  required
                />
              </div>
              <Button
                type="submit"
                disabled={loadingAgent || !username || !password}
                variant="outline"
                className="w-full h-11 rounded-md gap-2 border-border"
              >
                {loadingAgent ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Globe className="h-4 w-4" />
                )}
                <span>Entrar como agente</span>
              </Button>
            </div>
          </form>
        </div>

        <p className="text-center text-white/30 text-[11px] mt-6">
          Confeções Lança · Desde 1973
        </p>
      </div>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-[#111111]">
          <Loader2 className="h-6 w-6 animate-spin text-white/50" />
        </div>
      }
    >
      <SignInInner />
    </Suspense>
  );
}
