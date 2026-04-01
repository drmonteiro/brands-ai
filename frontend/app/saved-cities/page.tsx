"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { 
    ArrowLeft, 
    Globe, 
    Users, 
    RefreshCw, 
    MapPin, 
    TrendingUp,
    Database,
    ChevronRight,
    Search,
    BarChart3,
} from "lucide-react";
import { BrandCard } from "@/components/BrandCard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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

    useEffect(() => {
        fetchCities();
    }, []);

    const fetchCities = async () => {
        setIsLoadingCities(true);
        try {
            const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const response = await fetch(`${API_URL}/api/cities`);
            const data = await response.json();
            setSavedCities(data.cities || []);
        } catch (error) {
            console.error("Error fetching cities:", error);
            setSavedCities([]);
        } finally {
            setIsLoadingCities(false);
        }
    };

    const fetchProspectsForCity = async (city: string) => {
        setIsLoadingProspects(true);
        setSelectedCity(city);
        try {
            const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const response = await fetch(`${API_URL}/api/prospects?city=${encodeURIComponent(city)}`);
            const data = await response.json();
            setProspects(data.prospects || []);
        } catch (error) {
            console.error("Error fetching prospects:", error);
            setProspects([]);
        } finally {
            setIsLoadingProspects(false);
        }
    };

    const handleSendEmail = async (brandName: string, brandData: any) => {
        try {
            const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const response = await fetch(`${API_URL}/api/email/send`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    brand_name: brandName,
                    to_email: brandData.contactEmail || "comercial@lanca.pt",
                }),
            });
            return response.ok;
        } catch (error) {
            console.error("Email error:", error);
            return false;
        }
    };

    const safeCities = Array.isArray(savedCities) ? savedCities : [];
    const totalProspectsCount = safeCities.reduce((acc, c) => acc + (c.total_prospects || 0), 0);
    const safeProspects = Array.isArray(prospects) ? prospects : [];
    const avgScore = safeProspects.length > 0 
        ? Math.round(safeProspects.reduce((acc, p) => acc + (p.fit_score ?? p.fitScore ?? 0), 0) / safeProspects.length) 
        : 0;

    return (
        <div className="flex h-screen bg-background overflow-hidden font-sans">
            {/* Cities Sidebar */}
            <aside className="w-[320px] bg-white border-r border-border flex flex-col">
                {/* Sidebar Header */}
                <div className="p-5 border-b border-border">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-9 h-9 bg-lanca-yellowLight rounded-lg flex items-center justify-center">
                            <Database className="h-4 w-4 text-lanca-yellowDark" />
                        </div>
                        <div>
                            <h2 className="text-sm font-semibold text-foreground">Cidades Guardadas</h2>
                            <p className="text-xs text-muted-foreground">{safeCities.length} cidades · {totalProspectsCount} marcas</p>
                        </div>
                    </div>
                </div>

                {/* Cities List */}
                <div className="flex-1 overflow-y-auto p-3">
                    {isLoadingCities ? (
                        <div className="flex items-center justify-center py-16">
                            <RefreshCw className="h-5 w-5 text-muted-foreground animate-spin" />
                        </div>
                    ) : safeCities.length === 0 ? (
                        <div className="text-center py-16 px-4">
                            <Database className="h-8 w-8 text-muted-foreground/30 mx-auto mb-3" />
                            <p className="text-sm text-muted-foreground mb-1">Sem cidades guardadas</p>
                            <p className="text-xs text-muted-foreground/60">Faça uma pesquisa na página de Prospeção</p>
                        </div>
                    ) : safeCities.map((cityData) => (
                        <button
                            key={cityData.city}
                            onClick={() => fetchProspectsForCity(cityData.city)}
                            className={`w-full flex items-center gap-3 p-3 rounded-lg transition-all duration-200 text-left mb-1 ${
                                selectedCity === cityData.city
                                    ? "bg-lanca-yellowLight border border-lanca-yellow/20 shadow-gold-sm"
                                    : "hover:bg-muted/50"
                            }`}
                        >
                            <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors ${
                                selectedCity === cityData.city 
                                    ? "bg-lanca-yellow text-lanca-black" 
                                    : "bg-muted text-muted-foreground"
                            }`}>
                                <MapPin className="h-4 w-4" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <span className={`text-sm font-medium block truncate ${
                                    selectedCity === cityData.city ? "text-foreground" : "text-foreground"
                                }`}>
                                    {cityData.city}
                                </span>
                                <span className="text-xs text-muted-foreground">
                                    {cityData.total_prospects} marcas encontradas
                                </span>
                            </div>
                            <ChevronRight className={`h-4 w-4 flex-shrink-0 transition-colors ${
                                selectedCity === cityData.city ? "text-lanca-yellowDark" : "text-muted-foreground/30"
                            }`} />
                        </button>
                    ))}
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto bg-background">
                {/* Header */}
                <header className="sticky top-0 z-40 bg-white border-b border-border px-6 lg:px-8 py-4">
                    <div className="flex justify-between items-center">
                        <div className="flex items-center gap-4">
                            <Link href="/">
                                <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground hover:text-foreground rounded-lg">
                                    <ArrowLeft className="h-4 w-4" />
                                    <span className="text-sm">Voltar</span>
                                </Button>
                            </Link>
                            {selectedCity && (
                                <>
                                    <div className="h-5 w-px bg-border" />
                                    <div className="flex items-center gap-2">
                                        <MapPin className="h-4 w-4 text-lanca-yellow" />
                                        <span className="text-sm font-semibold text-foreground">{selectedCity}</span>
                                        <Badge className="text-xs bg-muted text-muted-foreground border-border rounded-md">
                                            {safeProspects.length} marcas
                                        </Badge>
                                    </div>
                                </>
                            )}
                        </div>
                    </div>
                </header>

                <div className="p-6 lg:p-8 max-w-[1200px] mx-auto">
                    {!selectedCity ? (
                        /* Empty State */
                        <div className="flex flex-col items-center justify-center h-[60vh] text-center smooth-entry">
                            <div className="w-16 h-16 bg-muted rounded-xl flex items-center justify-center mb-6">
                                <Search className="h-7 w-7 text-muted-foreground/40" />
                            </div>
                            <h3 className="text-xl font-semibold text-foreground mb-2">Selecione uma cidade</h3>
                            <p className="text-sm text-muted-foreground max-w-sm mb-8">
                                Escolha uma cidade na lista à esquerda para ver as marcas encontradas pela IA.
                            </p>
                            <div className="flex items-center gap-8 px-8 py-4 bg-white rounded-xl border border-border shadow-soft">
                                <div className="text-center">
                                    <p className="text-xs text-muted-foreground mb-1">Total de Marcas</p>
                                    <p className="text-2xl font-bold text-foreground">{totalProspectsCount}</p>
                                </div>
                                <div className="h-10 w-px bg-border" />
                                <div className="text-center">
                                    <p className="text-xs text-muted-foreground mb-1">Cidades</p>
                                    <p className="text-2xl font-bold text-foreground">{safeCities.length}</p>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-6 smooth-entry">
                            {/* Stats Row */}
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                <div className="bg-white p-5 rounded-xl border border-border shadow-soft">
                                    <div className="flex items-center gap-2 mb-3 text-muted-foreground">
                                        <Users className="h-4 w-4" />
                                        <span className="text-xs font-medium uppercase tracking-wide">Marcas</span>
                                    </div>
                                    <p className="text-2xl font-bold text-foreground">{safeProspects.length}</p>
                                </div>
                                <div className="bg-white p-5 rounded-xl border border-border shadow-soft">
                                    <div className="flex items-center gap-2 mb-3 text-muted-foreground">
                                        <TrendingUp className="h-4 w-4" />
                                        <span className="text-xs font-medium uppercase tracking-wide">Score Médio</span>
                                    </div>
                                    <p className="text-2xl font-bold text-foreground">{avgScore}%</p>
                                </div>
                                <div className="bg-lanca-black p-5 rounded-xl shadow-medium col-span-2">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-xs text-white/50 font-medium uppercase tracking-wide mb-1">Cidade Selecionada</p>
                                            <p className="text-2xl font-bold text-white">{selectedCity}</p>
                                        </div>
                                        <div className="w-12 h-12 bg-lanca-yellow rounded-lg flex items-center justify-center">
                                            <Globe className="h-6 w-6 text-lanca-black" />
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Prospects Header */}
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm font-semibold text-foreground">
                                    Marcas encontradas em {selectedCity}
                                </h3>
                            </div>

                            {/* Prospects Grid */}
                            {isLoadingProspects ? (
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                                    {[1, 2, 3, 4].map(i => (
                                        <div key={i} className="h-64 rounded-xl bg-white border border-border animate-pulse" />
                                    ))}
                                </div>
                            ) : safeProspects.length === 0 ? (
                                <div className="text-center py-16 bg-white rounded-xl border border-border">
                                    <Database className="h-8 w-8 text-muted-foreground/30 mx-auto mb-3" />
                                    <p className="text-sm text-muted-foreground">Nenhuma marca encontrada nesta cidade.</p>
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
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
