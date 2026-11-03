"use client";

import { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useSession } from "next-auth/react";
import {
    Globe,
    RefreshCw,
    MapPin,
    Database,
    ChevronRight,
    Search,
    Download,
    Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { FilterPanel, ProspectFilters } from "@/components/FilterPanel";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { BrandLead } from "@/lib/types";
import { apiFetch, fetchWithTimeout } from "@/lib/apiBase";
import { useDebouncedValue } from "@/lib/useDebouncedValue";

const BrandCard = dynamic(
  () => import("@/components/BrandCard").then((mod) => mod.BrandCard),
  {
    loading: () => <div className="h-56 rounded-lg bg-white border border-border animate-pulse" />,
  }
);

// localStorage, not sessionStorage, so the first click of a new session shows cities at once.
const CITIES_CACHE_KEY = "lanca_cities_cache_v1";
const PROSPECTS_TIMEOUT_MS = 20000;
const REGENERATE_POLL_MS = 4000;

type RegenerationSummary = {
    added: number;
    updated: number;
    hidden: number;
    kept_sales_work: number;
    unverified: number;
};

function describeRegeneration(s: RegenerationSummary): string {
    const parts = [`${s.added} novas`, `${s.updated} atualizadas`, `${s.hidden} escondidas`];
    if (s.kept_sales_work) parts.push(`${s.kept_sales_work} mantidas por já terem contacto`);
    if (s.unverified) parts.push(`${s.unverified} por verificar`);
    return parts.join(", ");
}

function readCitiesCache(): CityData[] | null {
    if (typeof window === "undefined") return null;
    try {
        const raw = localStorage.getItem(CITIES_CACHE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : null;
    } catch {
        return null;
    }
}

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
    const { data: session } = useSession();
    const managerName = session?.user?.name || "Comercial";

    // SSR and first client paint must match (no sessionStorage in initial state).
    // Cache is applied in useEffect after hydration to avoid mismatch errors.
    const [savedCities, setSavedCities] = useState<CityData[]>([]);
    const [prospects, setProspects] = useState<BrandLead[]>([]);
    const [selectedCity, setSelectedCity] = useState<string | null>(null);
    const [isLoadingCities, setIsLoadingCities] = useState(true);
    const [citiesError, setCitiesError] = useState<string | null>(null);
    const [isLoadingProspects, setIsLoadingProspects] = useState(false);
    const [activeFilters, setActiveFilters] = useState<ProspectFilters>({});
    const debouncedFilters = useDebouncedValue(activeFilters, 300);
    const [cityToDelete, setCityToDelete] = useState<string | null>(null);
    const [cityToRegenerate, setCityToRegenerate] = useState<string | null>(null);
    const [regeneratingCity, setRegeneratingCity] = useState<string | null>(null);
    const [regenerationStep, setRegenerationStep] = useState("");
    const [prospectsVersion, setProspectsVersion] = useState(0);

    const fetchCities = useCallback(async (silent = false) => {
        const hasCache = (readCitiesCache()?.length ?? 0) > 0;
        if (!silent && !hasCache) setIsLoadingCities(true);
        setCitiesError(null);

        let lastError: unknown;
        for (let attempt = 0; attempt < 2; attempt++) {
            try {
                const response = await fetchWithTimeout("/api/cities", {}, attempt === 0 ? 12000 : 15000);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();
                const cities: CityData[] = data.cities || [];
                setSavedCities(cities);
                setCitiesError(null);
                try { localStorage.setItem(CITIES_CACHE_KEY, JSON.stringify(cities)); } catch { /* ignore */ }
                setIsLoadingCities(false);
                return;
            } catch (e) {
                lastError = e;
                if (attempt === 0) await new Promise((r) => setTimeout(r, 800));
            }
        }

        console.error("[saved-cities] cities fetch failed:", lastError);
        if (!hasCache) setSavedCities([]);
        setCitiesError("Servidor offline ou a acordar. Clica em Tentar novamente.");
        setIsLoadingCities(false);
    }, []);

    useEffect(() => {
        const cached = readCitiesCache();
        if (cached?.length) {
            setSavedCities(cached);
            setIsLoadingCities(false);
            fetchCities(true);
            return;
        }
        fetchCities(false);
    }, [fetchCities]);

    useEffect(() => {
        if (!selectedCity) {
            setProspects([]);
            return;
        }
        let cancelled = false;
        const load = async () => {
            setIsLoadingProspects(true);
            try {
                const params = new URLSearchParams({ city: selectedCity, limit: "100" });
                if (debouncedFilters.minStores) params.append("min_stores", debouncedFilters.minStores.toString());
                if (debouncedFilters.maxStores) params.append("max_stores", debouncedFilters.maxStores.toString());
                if (debouncedFilters.minPrice) params.append("min_price", debouncedFilters.minPrice.toString());
                if (debouncedFilters.maxPrice) params.append("max_price", debouncedFilters.maxPrice.toString());
                if (debouncedFilters.fitForLanca === "high") params.append("min_score", "70");
                if (debouncedFilters.fitForLanca === "medium") params.append("min_score", "50");
                const response = await fetchWithTimeout(`/api/prospects?${params.toString()}`, {}, PROSPECTS_TIMEOUT_MS);
                if (!response.ok) {
                    const t = await response.text().catch(() => "");
                    throw new Error(t || `HTTP ${response.status}`);
                }
                const data = await response.json();
                if (!cancelled) setProspects(data.prospects || []);
            } catch (e) {
                console.error("[saved-cities] prospects fetch failed:", e);
                if (!cancelled) {
                    toast.error("Não foi possível carregar as marcas. Escolhe a cidade de novo para tentar outra vez.");
                    setSelectedCity(null);
                }
                if (!cancelled) setProspects([]);
            } finally {
                if (!cancelled) setIsLoadingProspects(false);
            }
        };
        load();
        return () => { cancelled = true; };
    }, [selectedCity, debouncedFilters, prospectsVersion]);

    // The search runs on the server, so coming back to a city picks up its progress.
    useEffect(() => {
        if (!selectedCity || regeneratingCity) return;
        let cancelled = false;
        apiFetch(`/api/prospect/status?city=${encodeURIComponent(selectedCity)}`)
            .then((response) => (response.ok ? response.json() : null))
            .then((data) => {
                if (!cancelled && data?.status === "running") setRegeneratingCity(selectedCity);
            })
            .catch(() => { /* the city still shows, without progress */ });
        return () => { cancelled = true; };
    }, [selectedCity, regeneratingCity]);

    useEffect(() => {
        if (!regeneratingCity) return;
        let cancelled = false;
        const poll = async () => {
            while (!cancelled) {
                await new Promise((resolve) => setTimeout(resolve, REGENERATE_POLL_MS));
                if (cancelled) return;
                try {
                    const response = await apiFetch(`/api/prospect/status?city=${encodeURIComponent(regeneratingCity)}`);
                    if (!response.ok) continue;
                    const data = await response.json();
                    if (cancelled) return;
                    const steps: string[] = data.progress || [];
                    if (steps.length) setRegenerationStep(steps[steps.length - 1]);
                    if (data.status === "running") continue;
                    setRegeneratingCity(null);
                    setRegenerationStep("");
                    if (data.status === "completed") {
                        toast.success(
                            data.summary
                                ? `${regeneratingCity}: ${describeRegeneration(data.summary)}.`
                                : `${regeneratingCity} atualizada.`,
                            { duration: 10000 }
                        );
                    } else {
                        toast.error(data.error || "Não foi possível regenerar. Nada foi alterado.");
                    }
                    setProspectsVersion((version) => version + 1);
                    fetchCities(true);
                    return;
                } catch (e) {
                    console.error("[saved-cities] regeneration poll failed:", e);
                }
            }
        };
        poll();
        return () => { cancelled = true; };
    }, [regeneratingCity, fetchCities]);

    const confirmRegenerate = async () => {
        const city = cityToRegenerate;
        if (!city) return;
        setCityToRegenerate(null);
        try {
            const response = await apiFetch(`/api/cities/${encodeURIComponent(city)}/regenerate`, { method: "POST" });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            setRegenerationStep("A iniciar…");
            setRegeneratingCity(city);
        } catch (e) {
            console.error("[saved-cities] regenerate failed:", e);
            toast.error("Não foi possível iniciar a regeneração.");
        }
    };

    const handleExportCSV = async () => {
        if (!selectedCity) return;
        const params = new URLSearchParams({ city: selectedCity });
        if (activeFilters.minStores) params.append("min_stores", activeFilters.minStores.toString());
        if (activeFilters.maxStores) params.append("max_stores", activeFilters.maxStores.toString());
        if (activeFilters.minPrice) params.append("min_price", activeFilters.minPrice.toString());
        if (activeFilters.maxPrice) params.append("max_price", activeFilters.maxPrice.toString());
        if (activeFilters.fitForLanca === 'high') params.append("min_score", "70");
        if (activeFilters.fitForLanca === 'medium') params.append("min_score", "50");
        try {
            // A plain link can't carry the auth token, so download it through a fetch.
            const response = await apiFetch(`/api/export/csv?${params.toString()}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const url = URL.createObjectURL(await response.blob());
            const link = document.createElement("a");
            link.href = url;
            link.download = `lanca-${selectedCity}.csv`;
            link.click();
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error("[saved-cities] export failed:", e);
            toast.error("Não foi possível exportar o CSV.");
        }
    };

    const handleDeleteCity = async (e?: React.MouseEvent) => {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        if (!selectedCity) return;
        setCityToDelete(selectedCity);
    };

    const confirmDeleteCity = async () => {
        if (!cityToDelete) return;
        try {
            const response = await apiFetch(`/api/cities/${encodeURIComponent(cityToDelete)}`,
                { method: "DELETE" }
            );
            if (response.ok) {
                toast.success(`Cidade ${cityToDelete} eliminada.`);
                setSelectedCity(null);
                setProspects([]);
                fetchCities();
            } else { toast.error("Erro ao eliminar."); }
        } catch { toast.error("Erro ao eliminar."); }
        finally { setCityToDelete(null); }
    };

    const safeCities = Array.isArray(savedCities) ? savedCities : [];
    const totalProspectsCount = safeCities.reduce((acc, c) => acc + (c.total_prospects || 0), 0);
    const safeProspects = Array.isArray(prospects) ? prospects : [];

    return (
        <div className="flex h-[calc(100dvh-3.5rem)] flex-col overflow-hidden bg-background font-sans md:h-screen lg:flex-row">

            {/* Left Panel — City List */}
            <aside className="flex w-full flex-shrink-0 flex-col border-b border-border bg-white lg:w-[280px] lg:border-b-0 lg:border-r">

                {/* Panel Header */}
                <div className="flex items-center border-b border-border px-5 py-3 lg:h-16 lg:py-0">
                    <div>
                        <h1 className="font-serif text-lg font-semibold text-foreground">Cidades guardadas</h1>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                            {isLoadingCities ? "A carregar..." : `${safeCities.length} cidades · ${totalProspectsCount} marcas`}
                        </p>
                    </div>
                </div>

                {/* City List */}
                <div className="flex gap-1 overflow-x-auto p-2 lg:block lg:flex-1 lg:overflow-y-auto" aria-busy={isLoadingCities}>
                    {isLoadingCities ? (
                        <div className="space-y-1.5 p-1">
                            {Array.from({ length: 7 }).map((_, i) => (
                                <div key={i} className="flex items-center gap-3 px-3 py-2.5">
                                    <Skeleton className="h-8 w-8 rounded-md" />
                                    <div className="flex-1 space-y-1.5">
                                        <Skeleton className="h-3 w-24" />
                                        <Skeleton className="h-2.5 w-16" />
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : citiesError ? (
                        <div className="text-center py-12 px-4">
                            <Database className="h-6 w-6 text-muted-foreground/25 mx-auto mb-2" />
                            <p className="text-[12px] text-muted-foreground mb-4">{citiesError}</p>
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() => fetchCities(false)}
                                className="h-8 text-[12px] gap-1.5"
                            >
                                <RefreshCw className="h-3.5 w-3.5" />
                                Tentar novamente
                            </Button>
                        </div>
                    ) : safeCities.length === 0 ? (
                        <div className="text-center py-16 px-4">
                            <Database className="h-6 w-6 text-muted-foreground/25 mx-auto mb-2" />
                            <p className="text-[12px] text-muted-foreground mb-1">Sem cidades guardadas</p>
                            <Link href="/" className="text-[11px] text-lanca-goldDeep hover:underline">
                                Fazer uma pesquisa →
                            </Link>
                        </div>
                    ) : safeCities.map((cityData) => {
                        const isActive = selectedCity === cityData.city;
                        return (
                            <button
                                key={cityData.city}
                                aria-current={isActive ? "true" : undefined}
                                onClick={() => {
                                    if (selectedCity !== cityData.city) setActiveFilters({});
                                    setSelectedCity(cityData.city);
                                }}
                                className={`flex flex-shrink-0 items-center gap-3 px-3 py-2 lg:py-2.5 lg:w-full rounded-md transition-all duration-150 text-left mb-0.5 ${
                                    isActive
                                        ? "bg-lanca-ink text-white"
                                        : "text-foreground hover:bg-muted/60"
                                }`}
                            >
                                <MapPin className={`hidden lg:block h-3.5 w-3.5 flex-shrink-0 ${isActive ? "text-lanca-gold" : "text-muted-foreground/50"}`} />
                                <div className="flex-1 min-w-0">
                                    <span className="text-[13px] font-medium block truncate capitalize">
                                        {cityData.city}
                                    </span>
                                    <span className={`text-[11px] block ${isActive ? "text-white/50" : "text-muted-foreground"}`}>
                                        {cityData.total_prospects} marcas
                                    </span>
                                </div>
                                <ChevronRight className={`hidden lg:block h-3.5 w-3.5 flex-shrink-0 ${isActive ? "text-white/30" : "text-muted-foreground/20"}`} />
                            </button>
                        );
                    })}
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto flex flex-col">

                {/* Top Bar */}
                <header className="sticky top-0 z-30 flex h-14 flex-shrink-0 items-center justify-between border-b border-border bg-white px-4 lg:h-16 lg:px-6">
                    <div className="flex items-center gap-3">
                        {selectedCity ? (
                            <>
                                <MapPin className="h-4 w-4 text-lanca-gold" />
                                <h2 className="font-serif text-xl font-semibold capitalize text-foreground">{selectedCity}</h2>
                                <span className="text-[12px] tabular-nums text-muted-foreground">
                                    {safeProspects.length} {safeProspects.length === 1 ? "marca" : "marcas"}
                                </span>
                            </>
                        ) : (
                            <h2 className="font-serif text-xl font-semibold text-foreground">Base de dados</h2>
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
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={Boolean(regeneratingCity)}
                                onClick={() => setCityToRegenerate(selectedCity)}
                                className="h-8 text-[12px] gap-1.5 rounded-md border-border"
                            >
                                <RefreshCw className={`h-3.5 w-3.5 ${regeneratingCity === selectedCity ? "animate-spin" : ""}`} />
                                Regenerar
                            </Button>
                            <Button
                                type="button"
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

                {regeneratingCity && (
                    <div role="status" className="flex items-center gap-2 border-b border-lanca-gold/40 bg-lanca-goldTint px-4 py-2 text-[12px] text-foreground lg:px-6">
                        <RefreshCw className="h-3.5 w-3.5 flex-shrink-0 animate-spin text-lanca-goldDeep" aria-hidden />
                        <span className="min-w-0 truncate">
                            A regenerar <span className="font-medium capitalize">{regeneratingCity}</span>
                            {regenerationStep ? `: ${regenerationStep}` : ""}
                        </span>
                    </div>
                )}

                <div className="flex-1 p-4 lg:p-8">
                    {!selectedCity ? (

                        /* Empty State */
                        <div className="flex flex-col items-center justify-center h-full text-center smooth-entry">
                            <div className="w-12 h-12 bg-muted rounded-lg flex items-center justify-center mb-5">
                                <Search className="h-5 w-5 text-muted-foreground/40" />
                            </div>
                            <h3 className="mb-1 font-serif text-2xl font-semibold text-foreground">Selecione uma cidade</h3>
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

                            {/* Filters */}
                            <div className="rounded border border-border bg-white px-4 py-2 lg:py-3">
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
                                    <p className="text-[13px] text-muted-foreground">Nenhuma marca com estes filtros.</p>
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                                    {safeProspects.map((brand) => (
                                        <BrandCard
                                            key={brand.id}
                                            brand={brand}
                                            managerName={managerName}
                                        />
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </main>

            {/* Custom Delete Confirmation Modal */}
            {cityToRegenerate && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
                    <div role="dialog" aria-modal="true" aria-labelledby="regenerate-title" className="w-full max-w-md rounded border border-border bg-white p-6 shadow-2xl">
                        <h3 id="regenerate-title" className="mb-2 font-serif text-xl font-semibold capitalize text-foreground">
                            Regenerar {cityToRegenerate}
                        </h3>
                        <p className="mb-2 text-sm text-muted-foreground">
                            Faz uma nova pesquisa com as regras atuais e revê as marcas já guardadas. Demora vários minutos.
                        </p>
                        <ul className="mb-6 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                            <li>Marcas que já não cumprem as regras ficam escondidas, sem serem apagadas.</li>
                            <li>Marcas contactadas ou convertidas nunca são escondidas.</li>
                            <li>Estados, notas e feedback mantêm-se.</li>
                        </ul>
                        <div className="flex justify-end gap-3">
                            <Button type="button" variant="ghost" onClick={() => setCityToRegenerate(null)} className="h-10 rounded">
                                Cancelar
                            </Button>
                            <Button type="button" onClick={confirmRegenerate} className="h-10 rounded bg-lanca-ink text-white hover:bg-lanca-charcoal">
                                Regenerar
                            </Button>
                        </div>
                    </div>
                </div>
            )}

            {cityToDelete && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
                    <div 
                        className="bg-white rounded-2xl w-full max-w-md shadow-2xl border border-border p-6 animate-in zoom-in-95 duration-200"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <h3 className="text-lg font-bold text-foreground mb-2">Eliminar Registo</h3>
                        <p className="text-sm text-muted-foreground mb-6">
                            Tens a certeza que queres eliminar a cidade <strong className="capitalize">{cityToDelete}</strong> e todas as suas marcas associadas? Esta ação não pode ser desfeita.
                        </p>
                        <div className="flex gap-3 justify-end">
                            <Button 
                                type="button" 
                                variant="ghost" 
                                onClick={() => setCityToDelete(null)}
                                className="h-10 rounded-xl"
                            >
                                Cancelar
                            </Button>
                            <Button 
                                type="button" 
                                onClick={confirmDeleteCity} 
                                className="bg-rose-600 hover:bg-rose-700 text-white h-10 rounded-xl"
                            >
                                Sim, Eliminar
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
