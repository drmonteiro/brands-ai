"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { FilterPanel, ProspectFilters } from "@/components/FilterPanel";
import {
    MapPin,
    ArrowLeft,
    Users,
    DollarSign,
    Star,
    RefreshCw,
    ChevronRight,
    Database,
    Search,
    Filter,
    Mail,
    Info,
    Sparkles,
    CheckCircle2
} from "lucide-react";

import { BrandLead } from "@/lib/types";
import { BrandCard } from "@/components/BrandCard";

interface CityStats {
    city: string;
    total_prospects: number;
    avg_score: number;
    avg_price_eur: number;
    last_searched: string;
}

export default function SavedCitiesPage() {
    const [cities, setCities] = useState<CityStats[]>([]);
    const [selectedCity, setSelectedCity] = useState<string | null>(null);
    const [prospects, setProspects] = useState<BrandLead[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isLoadingProspects, setIsLoadingProspects] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [activeFilters, setActiveFilters] = useState<ProspectFilters>({
        storeSize: null,
        priceRange: null,
        minStores: null,
        maxStores: null,
        minPrice: null,
        maxPrice: null,
    });

    const exchangeRate = 1.08;

    const filteredProspects = useMemo(() => {
        return prospects.filter((prospect) => {
            if (activeFilters.minStores != null || activeFilters.maxStores != null) {
                const storeCount = prospect.storeCount || 0;
                if (activeFilters.minStores != null && storeCount < activeFilters.minStores) return false;
                if (activeFilters.maxStores != null && storeCount > activeFilters.maxStores) return false;
            }
            if (activeFilters.minPrice != null || activeFilters.maxPrice != null) {
                // Convert USD back to EUR for filter comparison if necessary, or compare with USD
                // Here we usually filter by EUR in backend, but locally we'll use USD for consistency
                const price = prospect.averageSuitPriceUSD || 0;
                if (price === 0) return false;
                // Note: FilterPanel uses EUR, so we convert filters to USD
                if (activeFilters.minPrice != null && price < activeFilters.minPrice * exchangeRate) return false;
                if (activeFilters.maxPrice != null && price > activeFilters.maxPrice * exchangeRate) return false;
            }
            return true;
        });
    }, [prospects, activeFilters]);

    useEffect(() => {
        fetchCities();
    }, []);

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    const fetchCities = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await fetch(`${API_URL}/api/cities`);
            if (!response.ok) throw new Error("Falha ao obter cidades");
            const data = await response.json();
            setCities(data.cities || []);

            // Auto-select first city if available and none selected
            if (data.cities && data.cities.length > 0 && !selectedCity) {
                fetchProspectsForCity(data.cities[0].city);
            }
        } catch (err) {
            console.error("Error fetching cities:", err);
            setError("Erro ao carregar cidades guardadas");
        } finally {
            setIsLoading(false);
        }
    };

    const fetchProspectsForCity = async (city: string) => {
        setIsLoadingProspects(true);
        setSelectedCity(city);
        try {
            const response = await fetch(`${API_URL}/api/prospects?city=${encodeURIComponent(city)}&limit=50`);
            if (!response.ok) throw new Error("Falha ao obter prospects");
            const data = await response.json();

            const mappedProspects: BrandLead[] = (data.prospects || []).map((p: any) => {
                const materialComposition = typeof p.material_composition === 'string'
                    ? JSON.parse(p.material_composition)
                    : (p.material_composition || []);

                return {
                    name: p.name,
                    websiteUrl: p.website_url,
                    storeCount: p.store_count,
                    averageSuitPriceUSD: (p.avg_suit_price_eur || 0) * exchangeRate,
                    city: p.city,
                    originCountry: p.country,
                    verified: p.avg_suit_price_eur > 0,
                    brandStyle: p.brand_style,
                    businessModel: p.business_model,
                    companyOverview: p.company_overview || p.description || "Informação não disponível",
                    detailedDescription: p.detailed_description || "",
                    storeLocations: typeof p.store_locations === 'string' ? JSON.parse(p.store_locations) : (p.store_locations || []),
                    verificationLog: [
                        `Pontuação: ${p.final_score?.toFixed(1)}/100`,
                        `Similar a: ${p.most_similar_client || "N/D"}`,
                        p.similarity_explanation ? `Explicação: ${p.similarity_explanation}` : ""
                    ].filter(Boolean) as string[],
                    passesConstraints: true,
                    woolPercentage: materialComposition.length > 0 ? materialComposition[0] : null,
                    madeToMeasure: p.made_to_measure || false,
                    locationQuality: p.location_quality || (p.location_score > 0 ? "premium" : "standard"),
                    locationScore: p.location_score || 0,
                    fitScore: p.fit_score || 0
                };
            });

            setProspects(mappedProspects);
        } catch (err) {
            console.error("Error fetching prospects:", err);
            setProspects([]);
        } finally {
            setIsLoadingProspects(false);
        }
    };

    const handleSendEmail = (brand: BrandLead) => {
        const recipientEmail = "d.rmonteiro@hotmail.com";
        const subject = `🚀 Novo Potencial Cliente para Lança: ${brand.name}`;
        const body = `Olá Paulo,\n\nEncontrei este potencial cliente premium:\n\nNome: ${brand.name}\nWebsite: ${brand.websiteUrl}\nCidade: ${brand.city}\nScore: ${brand.verificationLog?.[0] || "N/D"}\n\nDescrição: ${brand.companyOverview}\n\nAtenciosamente,\nEquipa Lança Prospector AI`;
        const mailtoLink = `mailto:${recipientEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
        window.location.href = mailtoLink;
    };

    return (
        <div className="min-h-screen">
            {/* Top Application Bar */}
            <header className="bg-white border-b border-zinc-200 sticky top-0 z-20 px-8 py-4 flex justify-between items-center shadow-sm">
                <div>
                    <h1 className="text-xl font-bold text-zinc-900">Arquivo Histórico</h1>
                    <p className="text-xs text-zinc-500 font-medium">Confeções Lança • Prospecção de Mercado</p>
                </div>
                <div className="flex items-center gap-6">
                    <Link href="/" className="inline-flex items-center gap-2 text-[10px] font-bold tracking-widest uppercase text-zinc-400 hover:text-zinc-900 transition-colors">
                        <ArrowLeft className="h-3.5 w-3.5" />
                        Nova Pesquisa
                    </Link>
                </div>
            </header>

            <main className="p-8">
                <div className="grid lg:grid-cols-12 gap-12">
                    {/* Sidebar: Cities List - More Compact */}
                    <aside className="lg:col-span-2 space-y-6">
                        <div className="bg-white border-r border-zinc-200 h-full p-4 pr-6">
                            <div className="flex items-center justify-between mb-6 pb-4 border-b border-zinc-100">
                                <h2 className="text-[10px] font-bold tracking-widest uppercase text-zinc-400">CIDADES</h2>
                                <button onClick={fetchCities} className="text-zinc-300 hover:text-blue-600 transition-colors">
                                    <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
                                </button>
                            </div>

                            {isLoading ? (
                                <div className="space-y-4">
                                    {[1, 2, 3].map(i => <div key={i} className="h-16 bg-zinc-50 animate-pulse rounded-none" />)}
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {cities.map((cityData) => (
                                        <button
                                            key={cityData.city}
                                            onClick={() => fetchProspectsForCity(cityData.city)}
                                            className={`w-full p-3 rounded-lg transition-all text-left flex justify-between items-center group/item mb-1 ${selectedCity === cityData.city
                                                ? "bg-blue-50 text-blue-700 font-bold"
                                                : "text-zinc-600 hover:bg-zinc-50"
                                                }`}
                                        >
                                            <div className="min-w-0 pr-2">
                                                <p className="text-xs truncate">{cityData.city}</p>
                                                <p className={`text-[9px] ${selectedCity === cityData.city ? "text-blue-500" : "text-zinc-400"}`}>
                                                    {cityData.total_prospects} registos
                                                </p>
                                            </div>
                                            {selectedCity === cityData.city && <div className="w-1.5 h-1.5 rounded-full bg-blue-600 shrink-0" />}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </aside>

                    {/* Main Content Area - Wider */}
                    <div className="lg:col-span-10">
                        {!selectedCity ? (
                            <div className="bg-white p-32 text-center border border-zinc-200 border-dashed">
                                <Search className="h-12 w-12 text-zinc-100 mx-auto mb-6" />
                                <h3 className="text-xl font-serif text-zinc-400">Selecione uma Cidade para Explorar</h3>
                                <p className="text-[10px] font-bold text-zinc-300 mt-2 uppercase tracking-widest">Acesso aos registos históricos de prospecção</p>
                            </div>
                        ) : isLoadingProspects ? (
                            <div className="bg-white p-32 text-center border border-zinc-200">
                                <RefreshCw className="h-10 w-10 text-[#C9A84C] animate-spin mx-auto mb-6" />
                                <p className="text-[10px] font-bold tracking-[0.3em] uppercase text-zinc-400">A Carregar Base de Dados...</p>
                            </div>
                        ) : (
                            <div className="space-y-12">
                                {/* Header Results */}
                                <div className="flex justify-between items-end pb-8 border-b border-zinc-200">
                                    <div>
                                        <div className="flex items-center gap-2 mb-4">
                                            <div className="w-8 h-1 bg-blue-600 rounded-full" />
                                            <span className="text-[10px] font-bold text-blue-600 uppercase tracking-widest">RELATÓRIO DE MERCADO</span>
                                        </div>
                                        <h2 className="text-3xl font-bold text-zinc-900 capitalize">{selectedCity}</h2>
                                    </div>
                                    <div className="bg-zinc-50 p-4 border border-zinc-100 flex items-center gap-6">
                                        <div className="text-center px-4">
                                            <p className="text-[9px] font-bold text-zinc-400 uppercase tracking-widest mb-1">Total</p>
                                            <p className="text-lg font-serif">{filteredProspects.length}</p>
                                        </div>
                                        <div className="w-px h-8 bg-zinc-200" />
                                        <div className="text-center px-4">
                                            <p className="text-[9px] font-bold text-zinc-400 uppercase tracking-widest mb-1">Score Médio</p>
                                            <p className="text-lg font-bold text-blue-600">
                                                {(prospects.reduce((acc, p) => acc + (parseFloat(p.verificationLog?.[0]?.split(': ')[1]?.split('/')[0] || "0")), 0) / (prospects.length || 1)).toFixed(1)}
                                            </p>
                                        </div>
                                    </div>
                                </div>

                                {/* Internal Sub-grid for Filters Sidebar + Results List */}
                                <div className="grid grid-cols-12 gap-10">
                                    {/* Sub-sidebar for Filters */}
                                    <aside className="col-span-12 lg:col-span-3">
                                        <FilterPanel onFilterChange={setActiveFilters} activeFilters={activeFilters} />

                                        <div className="mt-6 p-4 bg-blue-50/50 border border-blue-100 rounded-xl">
                                            <p className="text-[10px] text-blue-600 font-bold uppercase mb-2">Análise Histórica</p>
                                            <p className="text-[11px] text-zinc-500 leading-relaxed font-medium">
                                                Estes resultados representam o estado do mercado à data da última prospecção.
                                            </p>
                                        </div>
                                    </aside>

                                    {/* Main Results Column */}
                                    <div className="col-span-12 lg:col-span-9 space-y-6">
                                        {filteredProspects.map((brand, idx) => (
                                            <BrandCard
                                                key={idx}
                                                brand={brand}
                                                onSendEmail={handleSendEmail}
                                            />
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}
