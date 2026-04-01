"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
    Globe,
    Users,
    RefreshCw,
    MapPin,
    TrendingUp,
    Database,
    ChevronRight,
    Search,
    Download,
    Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { BrandCard } from "@/components/BrandCard";
import { FilterPanel, ProspectFilters } from "@/components/FilterPanel";
import { Button } from "@/components/ui/button";
import { BrandLead } from "@/lib/types";

interface CityData {
    city: string;
    total_prospects: number;
    avg_score: number;
    top_score: number;
    new_count: number;
    contacted_count: number;
    converted_count: number;
}

export default function SavedCitiesPage() {
    const [savedCities, setSavedCities] = useState<CityData[]>([]);
    const [prospects, setProspects] = useState<BrandLead[]>([]);
    const [selectedCity, setSelectedCity] = useState<string | null>(null);
    const [isLoadingCities, setIsLoadingCities] = useState(true);
    const [isLoadingProspects, setIsLoadingProspects] = useState(false);
    const [activeFilters, setActiveFilters] = useState<ProspectFilters>({});

    useEffect(() => { fetchCities(); }, []);
    useEffect(() => { if (selectedCity) fetchProspectsForCity(selectedCity); }, [activeFilters]);

    const fetchCities = async () => {
        setIsLoadingCities(true);
        try {
            const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const response = await fetch(`${API_URL}/api/cities`);
            const data = await response.json();
            setSavedCities(data.cities || []);
        } catch { setSavedCities([]); }
        finally { setIsLoadingCities(false); }
    };

    const fetchProspectsForCity = async (city: string) => {
        setIsLoadingProspects(true);
        if (selectedCity !== city) {
            setActiveFilters({});
            setSelectedCity(city);
        }
        try {
            const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const params = new URLSearchParams({ city });
            if (activeFilters.minStores) params.append("min_stores", activeFilters.minStores.toString());
            if (activeFilters.maxStores) params.append("max_stores", activeFilters.maxStores.toString());
            if (activeFilters.minPrice) params.append("min_price", activeFilters.minPrice.toString());
            if (activeFilters.maxPrice) params.append("max_price", activeFilters.maxPrice.toString());
            if (activeFilters.fitForLanca === 'high') params.append("min_score", "70");
            if (activeFilters.fitForLanca === 'medium') params.append("min_score", "50");
            const response = await fetch(`${API_URL}/api/prospects?${params.toString()}`);
            const data = await response.json();
            setProspects(data.prospects || []);
        } catch { setProspects([]); }
        finally { setIsLoadingProspects(false); }
    };

    const handleSendEmail = async (brandName: string, brandData: any) => {
        try {
            const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const response = await fetch(`${API_URL}/api/email/draft`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ brandName, brandData }),
            });
            if (response.ok) {
                const data = await response.json();
                if (data.mailto) { window.location.href = data.mailto; return true; }
            }
            return false;
        } catch { return false; }
    };

    const handleExportCSV = () => {
        if (!selectedCity) return;
        const params = new URLSearchParams({ city: selectedCity });
        if (activeFilters.minStores) params.append("min_stores", activeFilters.minStores.toString());
        if (activeFilters.maxStores) params.append("max_stores", activeFilters.maxStores.toString());
        if (activeFilters.minPrice) params.append("min_price", activeFilters.minPrice.toString());
        if (activeFilters.maxPrice) params.append("max_price", activeFilters.maxPrice.toString());
        if (activeFilters.fitForLanca === 'high') params.append("min_score", "70");
        if (activeFilters.fitForLanca === 'medium') params.append("min_score", "50");
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        window.open(`${API_URL}/api/export/csv?${params.toString()}`, '_blank');
    };

    const handleDeleteCity = async () => {
        if (!selectedCity) return;
        if (!window.confirm(`Eliminar ${selectedCity} e todas as suas marcas?`)) return;
        try {
            const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const response = await fetch(`${API_URL}/api/cities/${encodeURIComponent(selectedCity)}`, { method: 'DELETE' });
            if (response.ok) {
                toast.success(`Cidade ${selectedCity} eliminada.`);
                setSelectedCity(null);
                setProspects([]);
                fetchCities();
            } else { toast.error("Erro ao eliminar."); }
        } catch { toast.error("Erro ao eliminar."); }
    };

    const safeCities = Array.isArray(savedCities) ? savedCities : [];
    const totalProspectsCount = safeCities.reduce((acc, c) => acc + (c.total_prospects || 0), 0);
    const safeProspects = Array.isArray(prospects) ? prospects : [];
    const avgScore = safeProspects.length > 0
        ? Math.round(safeProspects.reduce((acc, p) => acc + (p.fit_score ?? p.fitScore ?? 0), 0) / safeProspects.length)
        : 0;

    return (
        <div className="flex h-screen bg-background overflow-hidden font-sans">

            {/* Left Panel — City List */}
            <aside className="w-[280px] bg-white border-r border-border flex flex-col flex-shrink-0">

                {/* Panel Header */}
                <div className="h-16 px-5 flex items-center border-b border-border">
                    <div>
                        <h2 className="text-[13px] font-semibold text-foreground tracking-tight">Cidades Guardadas</h2>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                            {safeCities.length} cidades · {totalProspectsCount} marcas
                        </p>
                    </div>
                </div>

                {/* City List */}
                <div className="flex-1 overflow-y-auto p-2">
                    {isLoadingCities ? (
                        <div className="flex items-center justify-center py-16">
                            <RefreshCw className="h-4 w-4 text-muted-foreground/30 animate-spin" />
                        </div>
                    ) : safeCities.length === 0 ? (
                        <div className="text-center py-16 px-4">
                            <Database className="h-6 w-6 text-muted-foreground/25 mx-auto mb-2" />
                            <p className="text-[12px] text-muted-foreground mb-1">Sem cidades guardadas</p>
                            <Link href="/" className="text-[11px] text-[#D4A514] hover:underline">
                                Fazer uma pesquisa →
                            </Link>
                        </div>
                    ) : safeCities.map((cityData) => {
                        const isActive = selectedCity === cityData.city;
                        return (
                            <button
                                key={cityData.city}
                                onClick={() => fetchProspectsForCity(cityData.city)}
                                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md transition-all duration-150 text-left mb-0.5 ${
                                    isActive
                                        ? "bg-[#111111] text-white"
                                        : "text-foreground hover:bg-muted/60"
                                }`}
                            >
                                <MapPin className={`h-3.5 w-3.5 flex-shrink-0 ${isActive ? "text-[#F5C518]" : "text-muted-foreground/50"}`} />
                                <div className="flex-1 min-w-0">
                                    <span className="text-[13px] font-medium block truncate capitalize">
                                        {cityData.city}
                                    </span>
                                    <span className={`text-[11px] block ${isActive ? "text-white/50" : "text-muted-foreground"}`}>
                                        {cityData.total_prospects} marcas
                                    </span>
                                </div>
                                <ChevronRight className={`h-3.5 w-3.5 flex-shrink-0 ${isActive ? "text-white/30" : "text-muted-foreground/20"}`} />
                            </button>
                        );
                    })}
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto flex flex-col">

                {/* Top Bar */}
                <header className="h-16 bg-white border-b border-border px-6 flex items-center justify-between sticky top-0 z-40 flex-shrink-0">
                    <div className="flex items-center gap-3">
                        {selectedCity ? (
                            <>
                                <MapPin className="h-4 w-4 text-[#F5C518]" />
                                <span className="text-[15px] font-semibold text-foreground capitalize">{selectedCity}</span>
                                <span className="text-[12px] text-muted-foreground bg-muted px-2 py-0.5 rounded-md">
                                    {safeProspects.length} marcas
                                </span>
                            </>
                        ) : (
                            <span className="text-[15px] font-semibold text-foreground">Base de Dados</span>
                        )}
                    </div>

                    {selectedCity && (
                        <div className="flex items-center gap-2">
                            {safeProspects.length > 0 && (
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleExportCSV}
                                    className="h-8 text-[12px] gap-1.5 rounded-md border-border"
                                >
                                    <Download className="h-3.5 w-3.5" />
                                    CSV
                                </Button>
                            )}
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleDeleteCity}
                                className="h-8 text-[12px] gap-1.5 rounded-md border-border text-muted-foreground hover:text-rose-600 hover:border-rose-200 hover:bg-rose-50 transition-colors"
                            >
                                <Trash2 className="h-3.5 w-3.5" />
                                Eliminar
                            </Button>
                        </div>
                    )}
                </header>

                <div className="p-6 lg:p-8 flex-1">
                    {!selectedCity ? (

                        /* Empty State */
                        <div className="flex flex-col items-center justify-center h-full text-center smooth-entry">
                            <div className="w-12 h-12 bg-muted rounded-lg flex items-center justify-center mb-5">
                                <Search className="h-5 w-5 text-muted-foreground/40" />
                            </div>
                            <h3 className="text-[16px] font-semibold text-foreground mb-1">Selecione uma cidade</h3>
                            <p className="text-[13px] text-muted-foreground max-w-sm mb-8">
                                Escolha uma cidade à esquerda para ver as marcas encontradas pela IA.
                            </p>
                            <div className="flex items-center gap-8 px-8 py-5 bg-white rounded-lg border border-border">
                                <div className="text-center">
                                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Marcas</p>
                                    <p className="text-2xl font-bold text-foreground">{totalProspectsCount}</p>
                                </div>
                                <div className="h-8 w-px bg-border" />
                                <div className="text-center">
                                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Cidades</p>
                                    <p className="text-2xl font-bold text-foreground">{safeCities.length}</p>
                                </div>
                            </div>
                        </div>

                    ) : (
                        <div className="space-y-6 smooth-entry">

                            {/* City Header */}
                            <div className="mb-6 pb-5 flex items-end justify-between border-b border-border/50">
                                <div>
                                    <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground/50 mb-1.5 flex items-center gap-1.5">
                                        <Globe className="h-3 w-3 text-[#D4A514]" />
                                        Resultados da Prospeção
                                    </p>
                                    <h2 className="text-3xl font-bold text-foreground capitalize flex items-center gap-3">
                                        {selectedCity}
                                        <span className="text-[13px] font-medium text-muted-foreground bg-muted px-2.5 py-1 rounded-md align-middle flex items-center gap-1">
                                            {safeProspects.length} marcas
                                        </span>
                                    </h2>
                                </div>
                            </div>

                            {/* Filters */}
                            <div className="bg-white rounded-lg border border-border p-4">
                                <FilterPanel
                                    activeFilters={activeFilters}
                                    onFilterChange={setActiveFilters}
                                />
                            </div>

                            {/* Prospects Grid */}
                            {isLoadingProspects ? (
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                    {[1, 2, 3, 4].map(i => (
                                        <div key={i} className="h-56 rounded-lg bg-white border border-border animate-pulse" />
                                    ))}
                                </div>
                            ) : safeProspects.length === 0 ? (
                                <div className="text-center py-16 bg-white rounded-lg border border-border">
                                    <Database className="h-6 w-6 text-muted-foreground/25 mx-auto mb-2" />
                                    <p className="text-[13px] text-muted-foreground">Nenhuma marca encontrada nesta cidade.</p>
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                    {safeProspects.map((brand) => (
                                        <BrandCard
                                            key={brand.id}
                                            brand={brand}
                                            onSendEmail={handleSendEmail}
                                        />
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
