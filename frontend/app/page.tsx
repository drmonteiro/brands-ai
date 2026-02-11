"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { BrandLead } from "@/lib/types";
import { BrandCard } from "@/components/BrandCard";
import { FilterPanel, ProspectFilters } from "@/components/FilterPanel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, Sparkles, Globe2, Target, Users, ArrowRight, MapPin, Database, RefreshCw, CheckCircle2 } from "lucide-react";

export default function Home() {
  const [city, setCity] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [verifiedBrands, setVerifiedBrands] = useState<BrandLead[]>([]);
  const [filteredBrands, setFilteredBrands] = useState<BrandLead[]>([]);
  const [exchangeRate, setExchangeRate] = useState<number>(1.08);
  const [forceRefresh, setForceRefresh] = useState(false);
  const [isCached, setIsCached] = useState(false);
  const [searchedCity, setSearchedCity] = useState("");
  const [approvalState, setApprovalState] = useState<{
    type: "discovery" | "persistence";
    threadId: string;
    queries?: string[];
    potentialBrands?: BrandLead[];
  } | null>(null);
  const [filters, setFilters] = useState<ProspectFilters>({
    storeSize: null,
    priceRange: null,
    minStores: null,
    maxStores: null,
    minPrice: null,
    maxPrice: null,
  });

  const handleResume = async (threadId: string, node: string, action: string, data?: any) => {
    console.log("[Resume] Resuming for thread:", threadId, "at node:", node);
    setIsSearching(true);
    setApprovalState(null);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/prospect/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: threadId,
          node: node,
          action: action,
          data: data,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Falha ao retomar pesquisa");
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No response stream");

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const messages = buffer.split("\n\n");
        buffer = messages.pop() || "";

        for (const message of messages) {
          if (message.startsWith("data: ")) {
            try {
              const result = JSON.parse(message.slice(6));
              if (result.type === "complete") {
                setVerifiedBrands(result.verifiedBrands || []);
                setExchangeRate(result.exchangeRate || 1.08);
              } else if (result.type === "waiting_approval") {
                setApprovalState({
                  type: result.next_node === "discovery" ? "discovery" : "persistence",
                  threadId: result.thread_id,
                  queries: result.queries,
                  potentialBrands: result.potential_brands,
                });
                setIsSearching(false);
                return; // Wait for next approval
              } else if (result.type === "error") {
                console.error("Resume error:", result.message);
                alert("Erro ao retomar: " + result.message);
              }
            } catch (e) {
              console.warn("Failed to parse resume SSE", e);
            }
          }
        }
      }
    } catch (error: any) {
      console.error("Resume connection error:", error);
      alert("Erro ao ligar ao servidor para retomar: " + error.message);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSearch = async () => {
    console.log("[Search] Initiating for city:", city);
    if (!city.trim()) {
      alert("Por favor, introduza o nome de uma cidade");
      return;
    }

    setIsSearching(true);
    setVerifiedBrands([]);
    setIsCached(false);
    setSearchedCity(city.trim());

    try {
      console.log("[Search] Fetching from API...");
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

      const response = await fetch(`${API_URL}/api/prospect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city: city.trim(), force_refresh: forceRefresh }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Falha ao iniciar pesquisa");
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response stream");
      }

      console.log("[Search] Stream opened, reading events...");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          console.log("[SSE] Stream ended");
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const messages = buffer.split("\n\n");
        buffer = messages.pop() || "";

        for (const message of messages) {
          if (message.startsWith("data: ")) {
            try {
              const jsonStr = message.slice(6);
              const data = JSON.parse(jsonStr);
              console.log("[SSE] Received event:", data.type);

              if (data.type === "complete") {
                console.log("[SSE] Complete! Brands:", data.verifiedBrands?.length, "Cached:", data.cached);
                setVerifiedBrands(data.verifiedBrands || []);
                setExchangeRate(data.exchangeRate || 1.08);
                setIsCached(data.cached === true);
              } else if (data.type === "error") {
                console.error("[SSE] Error from server:", data.message);
                alert("Erro no servidor: " + data.message);
              } else if (data.type === "progress") {
                console.log("[SSE] Progress:", data.message);
              } else if (data.type === "waiting_approval") {
                console.log("[SSE] Waiting for approval at:", data.next_node);
                setIsSearching(false); // Stop the main spinner
                setApprovalState({
                  type: data.next_node === "discovery" ? "discovery" : "persistence",
                  threadId: data.thread_id,
                  queries: data.queries,
                  potentialBrands: data.potential_brands,
                });
              }
            } catch (parseError) {
              console.warn("[SSE] Failed to parse:", message.slice(0, 200));
            }
          }
        }
      }

      if (buffer.startsWith("data: ")) {
        try {
          const data = JSON.parse(buffer.slice(6));
          if (data.type === "complete") {
            setVerifiedBrands(data.verifiedBrands || []);
            setExchangeRate(data.exchangeRate || 1.08);
            setIsCached(data.cached === true);
          }
        } catch {
          console.warn("[SSE] Could not parse final buffer");
        }
      }
    } catch (error: any) {
      console.error("Search error:", error);
      alert("Erro ao ligar ao servidor: " + error.message);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSendEmail = async (brand: BrandLead) => {
    try {
      const response = await fetch("http://127.0.0.1:8000/api/approve-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          brandName: brand.name,
          brandData: brand,
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || "Falha ao enviar email");
      }
    } catch (error) {
      console.error("Email error:", error);
      throw error;
    }
  };

  // Fetch filtered prospects from API
  const fetchFilteredProspects = async () => {
    if (!city.trim()) return;

    try {
      const params = new URLSearchParams();
      params.append("city", city.trim());

      if (filters.minStores !== null && filters.minStores !== undefined) params.append("min_stores", filters.minStores.toString());
      if (filters.maxStores !== null && filters.maxStores !== undefined) params.append("max_stores", filters.maxStores.toString());
      if (filters.minPrice !== null && filters.minPrice !== undefined) params.append("min_price", filters.minPrice.toString());
      if (filters.maxPrice !== null && filters.maxPrice !== undefined) params.append("max_price", filters.maxPrice.toString());

      const response = await fetch(`http://127.0.0.1:8000/api/prospects?${params.toString()}`);

      if (!response.ok) {
        throw new Error("Falha ao obter prospects filtrados");
      }

      const data = await response.json();

      // Convert API response to BrandLead format
      const prospects = data.prospects?.map((p: any) => {
        const materialComposition = typeof p.material_composition === 'string'
          ? JSON.parse(p.material_composition)
          : (p.material_composition || []);

        return {
          name: p.name,
          websiteUrl: p.website_url,
          storeCount: p.store_count,
          averageSuitPriceUSD: (p.avg_suit_price_eur || 0) * exchangeRate, // Convert EUR to USD
          city: p.city,
          originCountry: p.country,
          verified: p.avg_suit_price_eur > 0,
          brandStyle: p.brand_style,
          businessModel: p.business_model,
          companyOverview: p.description || p.company_overview || "Informação não disponível",
          detailedDescription: p.detailed_description || "",
          storeLocations: typeof p.store_locations === 'string' ? JSON.parse(p.store_locations) : (p.store_locations || []),
          verificationLog: [
            `Pontuação: ${p.final_score?.toFixed(1)}/100`,
            `Similar a: ${p.most_similar_client || "N/D"}`,
          ],
          passesConstraints: true,
          woolPercentage: materialComposition.length > 0 ? materialComposition[0] : null,
          madeToMeasure: p.made_to_measure || false,
          locationQuality: p.location_quality || (p.location_score > 0 ? "premium" : "standard"),
          locationScore: p.location_score || 0,
          fitScore: p.fit_score || 0
        };
      }) || [];

      setFilteredBrands(prospects);
    } catch (error) {
      console.error("Filter error:", error);
      // Fallback to local filtering if API fails
      applyLocalFilters();
    }
  };

  // Apply filters locally (fallback)
  const applyLocalFilters = () => {
    let filtered = [...verifiedBrands];

    if (filters.minStores !== null) {
      filtered = filtered.filter(b => b.storeCount >= filters.minStores!);
    }
    if (filters.maxStores !== null) {
      filtered = filtered.filter(b => b.storeCount <= filters.maxStores!);
    }
    if (filters.minPrice !== null) {
      filtered = filtered.filter(b => b.averageSuitPriceUSD >= filters.minPrice! / exchangeRate);
    }
    if (filters.maxPrice !== null) {
      filtered = filtered.filter(b => b.averageSuitPriceUSD <= filters.maxPrice! / exchangeRate);
    }

    setFilteredBrands(filtered);
  };

  // Apply filters when they change
  useEffect(() => {
    if (verifiedBrands.length > 0) {
      // Try API first, fallback to local
      const hasApiFilters = filters.minStores !== null || filters.maxStores !== null ||
        filters.minPrice !== null || filters.maxPrice !== null;

      if (hasApiFilters && city.trim()) {
        fetchFilteredProspects();
      } else {
        applyLocalFilters();
      }
    } else {
      setFilteredBrands([]);
    }
  }, [filters, verifiedBrands, city, exchangeRate]);

  // Initialize filtered brands when verified brands change
  useEffect(() => {
    if (verifiedBrands.length > 0) {
      setFilteredBrands(verifiedBrands);
    }
  }, [verifiedBrands]);

  const suggestedCities = ["Boston", "Austin", "Portland", "Charleston", "San Francisco"];

  return (
    <div className="min-h-screen">
      {/* Top Application Bar */}
      <header className="bg-white border-b border-zinc-200 sticky top-0 z-20 px-8 py-4 flex justify-between items-center shadow-sm">
        <div>
          <h1 className="text-xl font-bold text-zinc-900">Prospecção de Clientes</h1>
          <p className="text-xs text-zinc-500 font-medium">Confeções Lança • Sistema de Gestão</p>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-50 border border-zinc-200 rounded-lg">
            <Users className="h-3.5 w-3.5 text-zinc-400" />
            <span className="text-[10px] font-bold text-zinc-600 uppercase">Acesso Administrador</span>
          </div>
          <Button variant="outline" className="h-10 rounded-lg border-zinc-200 text-xs font-bold uppercase">
            Exportar Dados
          </Button>
        </div>
      </header>

      <main className="p-8">
        {/* Search & Tool Area */}
        <div className="bg-white p-8 border border-zinc-200 rounded-2xl shadow-sm relative overflow-hidden group mb-12">
          <div className="mb-6 flex justify-between items-end">
            <div>
              <h2 className="text-2xl font-bold text-zinc-900">Nova Pesquisa</h2>
              <p className="text-xs text-zinc-500 font-medium">DEFINIR PARÂMETROS DE MERCADO</p>
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer group/check">
                <input
                  type="checkbox"
                  checked={forceRefresh}
                  onChange={(e) => setForceRefresh(e.target.checked)}
                  className="w-4 h-4 rounded border-zinc-300 text-blue-600 focus:ring-blue-500 transition-all cursor-pointer"
                />
                <span className="text-[10px] font-bold text-zinc-500 uppercase">Ignorar Cache</span>
              </label>
            </div>
          </div>

          <div className="flex gap-4">
            <div className="flex-1 relative">
              <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-blue-500" />
              <Input
                type="text"
                placeholder="Introduza o nome da cidade (ex: Milan, London, New York)..."
                value={city}
                onChange={(e) => setCity(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                className="h-14 pl-12 pr-4 border-zinc-200 rounded-xl bg-zinc-50 focus:bg-white text-base"
              />
            </div>
            <Button
              onClick={handleSearch}
              disabled={isSearching}
              className="h-14 px-10 bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm rounded-xl"
            >
              {isSearching ? <RefreshCw className="h-4 w-4 animate-spin" /> : "Iniciar Pesquisa IA"}
            </Button>
          </div>

          <div className="mt-6 flex items-center gap-4">
            <span className="text-[10px] font-bold text-zinc-400 uppercase">Sugestões:</span>
            <div className="flex gap-4">
              {suggestedCities.map((sc) => (
                <button
                  key={sc}
                  onClick={() => setCity(sc)}
                  className="text-[10px] font-bold text-zinc-500 hover:text-blue-600 uppercase transition-colors"
                >
                  {sc}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Results Area */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-start">
          {/* Filter Sidebar (only show if results) */}
          <aside className="lg:col-span-3 lg:sticky lg:top-32 space-y-8">
            <div className="bg-white p-6 border border-zinc-200 rounded-xl shadow-sm">
              <div className="flex items-center gap-2 mb-6 pb-4 border-b border-zinc-100">
                <Target className="h-4 w-4 text-blue-600" />
                <h4 className="text-[10px] font-bold tracking-widest uppercase text-zinc-900">Filtros</h4>
              </div>
              <FilterPanel
                onFilterChange={setFilters}
                activeFilters={filters}
              />
            </div>

            <div className="bg-blue-50/50 p-6 border border-blue-100 rounded-xl">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="h-3.5 w-3.5 text-blue-600" />
                <span className="text-[9px] font-bold tracking-widest uppercase text-blue-600">DICA IA</span>
              </div>
              <p className="text-[11px] text-zinc-600 leading-relaxed font-medium">
                O foco em boutiques de 1-5 lojas maximiza a diversificação geográfica e reduz a dependência de grandes contas.
              </p>
            </div>
          </aside>

          {/* Main Content Area */}
          <div className="lg:col-span-9 space-y-8">
            {/* Approval Node */}
            {approvalState && (
              <div className="animate-fade-in bg-white p-8 border-2 border-blue-600 rounded-2xl shadow-xl relative overflow-hidden mb-12">
                <div className="absolute top-0 right-0 p-4">
                  <div className="flex gap-1">
                    <div className="w-1 h-1 rounded-full bg-blue-600 animate-pulse" />
                    <div className="w-1 h-1 rounded-full bg-blue-600 animate-pulse stagger-1" />
                  </div>
                </div>
                <h3 className="text-xl font-bold text-zinc-900 mb-2">
                  {approvalState.type === "discovery" ? "Intervenção Humana: Validar Queries" : "Intervenção Humana: Seleção de Alvos"}
                </h3>
                <p className="text-xs text-zinc-500 font-medium mb-8">
                  O sistema Alphaia requer validação estratégica antes de proceder para a próxima fase.
                </p>

                {approvalState.type === "discovery" ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
                    {approvalState.queries?.map((q, idx) => (
                      <div key={idx} className="p-4 bg-zinc-50 border border-zinc-100 flex items-center gap-3">
                        <Search className="h-3.5 w-3.5 text-zinc-400" />
                        <span className="text-xs font-medium text-zinc-900 truncate">{q}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-8">
                    {approvalState.potentialBrands?.map((brand, idx) => (
                      <div key={idx} className="p-4 bg-zinc-50 border border-zinc-100 flex justify-between items-center">
                        <span className="text-[10px] font-bold uppercase truncate pr-4">{brand.name}</span>
                        <span className="text-[10px] font-bold text-blue-600">${brand.averageSuitPriceUSD ? brand.averageSuitPriceUSD.toFixed(0) : "0"}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex gap-4">
                  <Button
                    onClick={() => handleResume(
                      approvalState.threadId,
                      approvalState.type,
                      "approve",
                      approvalState.type === "discovery" ? { queries: approvalState.queries } : { brands: approvalState.potentialBrands }
                    )}
                    className="flex-1 h-12 bg-zinc-950 hover:bg-zinc-800 text-white font-bold tracking-widest text-[10px] uppercase rounded-none"
                  >
                    Confirmar e Prosseguir
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setApprovalState(null)}
                    className="w-40 h-12 border-zinc-200 text-zinc-400 font-bold tracking-widest text-[10px] uppercase rounded-none"
                  >
                    Cancelar
                  </Button>
                </div>
              </div>
            )}

            {/* Results Grid / List */}
            {isSearching ? (
              <div className="bg-white p-20 border border-zinc-200 rounded-2xl text-center shadow-sm">
                <div className="inline-block mb-8">
                  <div className="h-14 w-14 border-4 border-zinc-100 border-t-blue-600 rounded-full animate-spin" />
                </div>
                <h3 className="text-2xl font-bold text-zinc-900 mb-2 overflow-hidden whitespace-nowrap">
                  Explorando <span className="text-blue-600">{searchedCity || city}...</span>
                </h3>
                <div className="h-1.5 w-48 bg-zinc-100 mx-auto mt-6 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-600 animate-progress-lux" />
                </div>
                <p className="text-[10px] font-bold text-zinc-400 uppercase tracking-[0.2em] mt-6">A ANALISAR MERCADO EM TEMPO REAL</p>
              </div>
            ) : filteredBrands.length === 0 ? (
              <div className="bg-white p-32 border border-zinc-200 text-center border-dashed">
                <Globe2 className="h-12 w-12 text-zinc-100 mx-auto mb-6" />
                <h3 className="text-xl font-serif text-zinc-400">Aguardando Parâmetros de Pesquisa</h3>
                <p className="text-xs text-zinc-300 mt-2 uppercase tracking-widest">Introduza uma cidade no terminal de prospecção acima</p>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="flex items-center justify-between pb-6 border-b border-zinc-100">
                  <div className="flex items-center gap-4">
                    <span className="px-3 py-1 bg-zinc-900 text-white text-[10px] font-bold tracking-widest uppercase">
                      {filteredBrands.length} RESULTADOS EM {searchedCity || city}
                    </span>
                    {isCached && (
                      <span className="flex items-center gap-1.5 px-3 py-1 bg-zinc-50 border border-zinc-200 text-zinc-400 text-[9px] font-bold uppercase tracking-widest">
                        <Database className="h-3 w-3" />
                        CACHE
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-zinc-400 uppercase">Ordernar:</span>
                    <select className="bg-transparent text-[10px] font-bold uppercase outline-none cursor-pointer text-zinc-700">
                      <option>Fit Score</option>
                      <option>Preço (Desc)</option>
                      <option>Preço (Asc)</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-6">
                  {filteredBrands.map((brand, idx) => (
                    <BrandCard
                      key={idx}
                      brand={brand}
                      onSendEmail={handleSendEmail}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </main >

      <footer className="mt-20 border-t border-zinc-200 bg-white p-12">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8 text-zinc-400">
          <p className="text-[10px] font-bold tracking-widest uppercase">
            © 2024 CONFEÇÕES LANÇA • PROSPECÇÃO INTELIGENTE
          </p>
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-blue-500" />
              <span className="text-[9px] font-bold tracking-widest text-zinc-400 uppercase">Motor GPT-4o Otimizado</span>
            </div>
            <div className="h-4 w-[1px] bg-zinc-200" />
            <div className="flex items-center gap-2">
              <Database className="h-3.5 w-3.5 text-zinc-400" />
              <span className="text-[9px] font-bold tracking-widest text-zinc-400 uppercase">PostgreSQL + pgvector</span>
            </div>
          </div>
        </div>
      </footer >
    </div >
  );
}
