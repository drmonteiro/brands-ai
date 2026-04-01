"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Search,
  MapPin,
  RefreshCw,
  ArrowRight,
  Users,
  Globe,
  CheckCircle2,
  Loader2,
} from "lucide-react";

export default function Home() {
  const [city, setCity] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [forceRefresh, setForceRefresh] = useState(false);
  const [searchedCity, setSearchedCity] = useState("");
  const [searchComplete, setSearchComplete] = useState(false);
  const [progressMessages, setProgressMessages] = useState<string[]>([]);

  const handleSearch = async () => {
    if (!city.trim()) return;
    setIsSearching(true);
    setSearchComplete(false);
    setSearchedCity(city.trim());
    setProgressMessages([]);

    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${API_URL}/api/prospect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city: city.trim(), force_refresh: forceRefresh }),
      });

      if (!response.ok) throw new Error("Falha ao iniciar pesquisa.");

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response stream");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split('\n\n');
          buffer = parts.pop() || "";
          for (const part of parts) {
            if (part.startsWith('data: ')) {
              try {
                const data = JSON.parse(part.substring(6));
                if (data.message) {
                  setProgressMessages(prev => [...prev.slice(-3), data.message]);
                }
              } catch (e) {
                // ignore parse errors
              }
            }
          }
        }
        if (done) break;
      }

      setSearchComplete(true);
      toast.success(`Pesquisa concluída! Resultados para ${city.trim()} guardados.`);
    } catch (error: any) {
      toast.error("Erro ao pesquisar: " + error.message);
    } finally {
      setIsSearching(false);
    }
  };

  const suggestedCities = [
    "Milano", "London", "Paris", "Berlin",
    "Munich", "Zurich", "Madrid", "Barcelona",
    "Manchester", "Edinburgh", "Geneva", "Stockholm"
  ];

  return (
    <div className="min-h-screen bg-background font-sans">
      {/* Top Bar */}
      <header className="h-16 bg-white border-b border-border px-6 lg:px-10 flex items-center justify-between sticky top-0 z-40">
        <div>
          <h1 className="text-[15px] font-semibold text-foreground tracking-tight">Pesquisa de Marcas</h1>
          <p className="text-[12px] text-muted-foreground">Encontre novos parceiros por cidade</p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/saved-cities">
            <Button variant="outline" size="sm" className="h-8 text-xs gap-1.5 rounded-md border-border">
              <MapPin className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Cidades Guardadas</span>
            </Button>
          </Link>
          <Link href="/clients">
            <Button variant="outline" size="sm" className="h-8 text-xs gap-1.5 rounded-md border-border">
              <Users className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Clientes</span>
            </Button>
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-16 lg:py-24">

        {/* Header */}
        <div className="mb-12 smooth-entry">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#D4A514] mb-3">
            Motor de IA
          </p>
          <h2 className="text-3xl lg:text-4xl font-bold text-foreground mb-3 leading-[1.15]">
            Descubra novos parceiros
          </h2>
          <p className="text-[15px] text-muted-foreground leading-relaxed max-w-lg">
            Insira uma cidade e a nossa IA identifica as melhores marcas de moda masculina para a Lança.
          </p>
        </div>

        {/* Search Box */}
        <div className="mb-10 smooth-entry" style={{ animationDelay: "0.1s" }}>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50" />
              <Input
                type="text"
                placeholder="Ex: Milano, London, Paris..."
                value={city}
                onChange={(e) => setCity(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                className="h-11 pl-10 pr-4 text-[14px] rounded-md border-border bg-white focus-visible:ring-1 focus-visible:ring-[#F5C518]/60 placeholder:text-muted-foreground/40"
              />
            </div>
            <Button
              onClick={handleSearch}
              disabled={isSearching || !city.trim()}
              className="h-11 px-5 text-[13px] font-medium bg-[#111111] hover:bg-[#222222] text-white rounded-md transition-colors"
            >
              {isSearching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <div className="flex items-center gap-1.5">
                  <span>Pesquisar</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </div>
              )}
            </Button>
          </div>

          {/* Force refresh toggle */}
          <div className="flex items-center gap-2.5 mt-3 px-0.5">
            <label className="flex items-center gap-2 cursor-pointer">
              <div
                className={`w-8 h-4 rounded-full p-0.5 transition-colors duration-200 ${forceRefresh ? 'bg-[#F5C518]' : 'bg-border'}`}
                onClick={() => setForceRefresh(!forceRefresh)}
              >
                <div className={`w-3 h-3 rounded-full bg-white shadow-sm transition-transform duration-200 ${forceRefresh ? 'translate-x-4' : 'translate-x-0'}`} />
              </div>
              <span className="text-[12px] text-muted-foreground cursor-pointer select-none" onClick={() => setForceRefresh(!forceRefresh)}>
                Forçar nova pesquisa
              </span>
            </label>

            {searchComplete && (
              <div className="ml-auto flex items-center gap-1.5 text-emerald-600">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span className="text-[12px] font-medium">Concluído: {searchedCity}</span>
              </div>
            )}
          </div>

          {/* Progress */}
          {isSearching && progressMessages.length > 0 && (
            <div className="mt-4 bg-white border border-border rounded-md p-4 animate-fade-in">
              <p className="section-label mb-3">A processar</p>
              <div className="space-y-1.5 font-mono text-[12px]">
                {progressMessages.map((msg, i) => (
                  <div key={i} className={`flex gap-2 items-start ${i === progressMessages.length - 1 ? 'text-foreground' : 'text-muted-foreground/40'}`}>
                    <span className="text-[#D4A514] mt-px opacity-70">›</span>
                    <span className="leading-snug">{msg}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Success banner */}
        {searchComplete && (
          <div className="mb-10 smooth-entry">
            <div className="bg-white border border-emerald-200 rounded-md p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0" />
                <div>
                  <p className="text-[13px] font-medium text-foreground">Pesquisa concluída</p>
                  <p className="text-[12px] text-muted-foreground">Resultados para <strong>{searchedCity}</strong> guardados.</p>
                </div>
              </div>
              <Link href="/saved-cities">
                <Button size="sm" className="h-8 text-xs bg-emerald-600 hover:bg-emerald-700 text-white rounded-md gap-1.5">
                  Ver resultados <ArrowRight className="h-3 w-3" />
                </Button>
              </Link>
            </div>
          </div>
        )}

        {/* Suggested Cities */}
        <div className="mb-12 smooth-entry" style={{ animationDelay: "0.15s" }}>
          <div className="flex items-center gap-2 mb-4">
            <Globe className="h-3.5 w-3.5 text-muted-foreground/40" />
            <p className="section-label">Cidades sugeridas</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {suggestedCities.map((c) => (
              <button
                key={c}
                onClick={() => setCity(c)}
                className="px-3 py-1.5 bg-white border border-border text-[13px] text-muted-foreground rounded-md hover:border-[#F5C518]/60 hover:text-foreground transition-all duration-150"
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        {/* Quick Access */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 smooth-entry" style={{ animationDelay: "0.2s" }}>
          <Link href="/saved-cities" className="group">
            <div className="card-lanca p-5 flex items-start gap-4">
              <div className="w-9 h-9 bg-[#FEF9E7] rounded-md flex items-center justify-center flex-shrink-0 group-hover:bg-[#F5C518] transition-colors duration-200">
                <MapPin className="h-4 w-4 text-[#D4A514] group-hover:text-black transition-colors duration-200" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-[14px] font-semibold text-foreground mb-0.5">Cidades Guardadas</h3>
                <p className="text-[12px] text-muted-foreground leading-relaxed">
                  Consulte e filtre todas as marcas encontradas por cidade.
                </p>
              </div>
              <ArrowRight className="h-3.5 w-3.5 text-border mt-0.5 group-hover:text-[#F5C518] group-hover:translate-x-0.5 transition-all duration-150 flex-shrink-0" />
            </div>
          </Link>

          <Link href="/clients" className="group">
            <div className="card-lanca p-5 flex items-start gap-4">
              <div className="w-9 h-9 bg-[#FEF9E7] rounded-md flex items-center justify-center flex-shrink-0 group-hover:bg-[#F5C518] transition-colors duration-200">
                <Users className="h-4 w-4 text-[#D4A514] group-hover:text-black transition-colors duration-200" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-[14px] font-semibold text-foreground mb-0.5">Rede de Clientes</h3>
                <p className="text-[12px] text-muted-foreground leading-relaxed">
                  Veja os parceiros activos — o portfolio de excelência da Lança.
                </p>
              </div>
              <ArrowRight className="h-3.5 w-3.5 text-border mt-0.5 group-hover:text-[#F5C518] group-hover:translate-x-0.5 transition-all duration-150 flex-shrink-0" />
            </div>
          </Link>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-5 text-center bg-white">
        <p className="text-[11px] text-muted-foreground">
          Confeções Lança © 2026 · Desde 1973 · Plataforma Comercial Interna
        </p>
      </footer>
    </div>
  );
}
