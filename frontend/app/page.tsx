"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  Search, 
  MapPin, 
  RefreshCw, 
  ArrowRight, 
  Users, 
  TrendingUp,
  Globe,
  Sparkles,
  CheckCircle2,
} from "lucide-react";

export default function Home() {
  const [city, setCity] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [forceRefresh, setForceRefresh] = useState(false);
  const [searchedCity, setSearchedCity] = useState("");
  const [searchComplete, setSearchComplete] = useState(false);

  const handleSearch = async () => {
    if (!city.trim()) return;
    setIsSearching(true);
    setSearchComplete(false);
    setSearchedCity(city.trim());

    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${API_URL}/api/prospect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city: city.trim(), force_refresh: forceRefresh }),
      });

      if (!response.ok) throw new Error("Falha ao iniciar pesquisa");

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response stream");

      while (true) {
        const { done } = await reader.read();
        if (done) break;
      }
      
      setSearchComplete(true);
    } catch (error: any) {
      console.error("Search error:", error);
      alert("Erro ao pesquisar: " + error.message);
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
      {/* Page Header */}
      <header className="bg-white border-b border-border sticky top-0 z-40 px-6 lg:px-10 py-4">
        <div className="max-w-6xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-lg font-semibold text-foreground">Prospeção de Marcas</h1>
            <p className="text-sm text-muted-foreground">Encontre novas marcas por cidade</p>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/saved-cities">
              <Button variant="outline" size="sm" className="text-sm gap-2 rounded-lg">
                <MapPin className="h-4 w-4" />
                <span className="hidden sm:inline">Cidades Guardadas</span>
              </Button>
            </Link>
            <Link href="/clients">
              <Button variant="outline" size="sm" className="text-sm gap-2 rounded-lg">
                <Users className="h-4 w-4" />
                <span className="hidden sm:inline">Clientes</span>
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 lg:px-10 py-12 lg:py-20">
        {/* Hero Section */}
        <div className="text-center mb-16 smooth-entry">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-lanca-yellowLight border border-lanca-yellow/20 rounded-full mb-6">
            <Sparkles className="h-3.5 w-3.5 text-lanca-yellowDark" />
            <span className="text-xs font-medium text-lanca-yellowDark">Motor de Prospeção com IA</span>
          </div>
          <h2 className="text-4xl lg:text-5xl font-bold text-foreground mb-4 tracking-tight">
            Descubra novos <span className="text-lanca-yellow">parceiros</span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-xl mx-auto">
            Insira uma cidade e a nossa IA encontra as melhores marcas de moda masculina para a Lança.
          </p>
        </div>

        {/* Search Box */}
        <div className="w-full max-w-2xl mx-auto mb-16 smooth-entry" style={{ animationDelay: "0.1s" }}>
          <div className="bg-white p-2 rounded-xl shadow-medium border border-border">
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground/40" />
                <Input
                  type="text"
                  placeholder="Ex: Milano, London, Paris..."
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  className="h-14 pl-12 pr-4 border-none focus-visible:ring-0 text-base placeholder:text-muted-foreground/40 rounded-lg bg-transparent"
                />
              </div>
              <Button
                onClick={handleSearch}
                disabled={isSearching || !city.trim()}
                className="h-14 px-8 bg-lanca-black hover:bg-lanca-charcoal text-white font-medium rounded-lg transition-all duration-200 shadow-soft"
              >
                {isSearching ? (
                  <div className="flex items-center gap-2">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>A pesquisar...</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span>Pesquisar</span>
                    <ArrowRight className="h-4 w-4" />
                  </div>
                )}
              </Button>
            </div>
            {/* Options row */}
            <div className="flex items-center justify-between px-4 pt-2 pb-1">
              <label className="flex items-center gap-2.5 cursor-pointer group">
                <div className={`w-9 h-5 rounded-full p-0.5 transition-colors duration-200 ${forceRefresh ? 'bg-lanca-yellow' : 'bg-gray-200'}`}>
                  <div className={`w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${forceRefresh ? 'translate-x-4' : 'translate-x-0'}`} />
                </div>
                <input
                  type="checkbox"
                  checked={forceRefresh}
                  onChange={(e) => setForceRefresh(e.target.checked)}
                  className="hidden"
                />
                <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
                  Forçar nova pesquisa
                </span>
              </label>
              {searchComplete && (
                <div className="flex items-center gap-1.5 text-emerald-600">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span className="text-xs font-medium">Pesquisa concluída para {searchedCity}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Success banner */}
        {searchComplete && (
          <div className="w-full max-w-2xl mx-auto mb-16 smooth-entry">
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-emerald-900">Pesquisa concluída com sucesso!</p>
                  <p className="text-xs text-emerald-700">Resultados para <strong>{searchedCity}</strong> guardados na base de dados.</p>
                </div>
              </div>
              <Link href="/saved-cities">
                <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs gap-1.5">
                  Ver resultados <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            </div>
          </div>
        )}

        {/* Suggested Cities */}
        <div className="w-full max-w-3xl mx-auto mb-20 smooth-entry" style={{ animationDelay: "0.2s" }}>
          <div className="flex items-center gap-3 mb-5">
            <Globe className="h-4 w-4 text-muted-foreground/50" />
            <p className="text-sm font-medium text-muted-foreground">Cidades sugeridas</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestedCities.map((c) => (
              <button
                key={c}
                onClick={() => { setCity(c); }}
                className="px-4 py-2 bg-white border border-border text-sm text-muted-foreground rounded-lg hover:border-lanca-yellow hover:text-foreground hover:shadow-gold-sm transition-all duration-200"
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        {/* Quick Access Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 max-w-3xl mx-auto smooth-entry" style={{ animationDelay: "0.3s" }}>
          <Link href="/saved-cities" className="group">
            <div className="card-lanca p-6 flex items-start gap-4">
              <div className="w-12 h-12 bg-lanca-yellowLight rounded-lg flex items-center justify-center flex-shrink-0 group-hover:bg-lanca-yellow transition-colors duration-200">
                <MapPin className="h-5 w-5 text-lanca-yellowDark group-hover:text-lanca-black transition-colors duration-200" />
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-semibold text-foreground mb-1 group-hover:text-lanca-yellowDark transition-colors">Cidades Guardadas</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Consulte todas as marcas encontradas, organizadas por cidade. Filtre e analise cada prospect.
                </p>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground/30 mt-1 group-hover:text-lanca-yellow group-hover:translate-x-1 transition-all duration-200 flex-shrink-0" />
            </div>
          </Link>

          <Link href="/clients" className="group">
            <div className="card-lanca p-6 flex items-start gap-4">
              <div className="w-12 h-12 bg-lanca-yellowLight rounded-lg flex items-center justify-center flex-shrink-0 group-hover:bg-lanca-yellow transition-colors duration-200">
                <Users className="h-5 w-5 text-lanca-yellowDark group-hover:text-lanca-black transition-colors duration-200" />
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-semibold text-foreground mb-1 group-hover:text-lanca-yellowDark transition-colors">Rede de Clientes</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Veja os nossos parceiros ativos em todo o mundo — o portfolio de excelência da Lança.
                </p>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground/30 mt-1 group-hover:text-lanca-yellow group-hover:translate-x-1 transition-all duration-200 flex-shrink-0" />
            </div>
          </Link>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-6 text-center bg-white">
        <p className="text-xs text-muted-foreground">
          Confeções Lança © 2026 · Desde 1973 · Plataforma Comercial
        </p>
      </footer>
    </div>
  );
}
