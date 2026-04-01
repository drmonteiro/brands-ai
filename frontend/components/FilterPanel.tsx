"use client";

import { Button } from "@/components/ui/button";
import { Check, X, SlidersHorizontal } from "lucide-react";

interface FilterPanelProps {
  onFilterChange: (filters: ProspectFilters) => void;
  activeFilters: ProspectFilters;
}

export interface ProspectFilters {
  storeSize?: "boutique" | "medium" | "large" | null;
  priceRange?: "under_500" | "500_1000" | "1000_2000" | "over_2000" | null;
  fitForLanca?: "high" | "medium" | "low" | null;
  minStores?: number | null;
  maxStores?: number | null;
  minPrice?: number | null;
  maxPrice?: number | null;
}

export function FilterPanel({ onFilterChange, activeFilters }: FilterPanelProps) {
  const handleFitToggle = (fit: "high" | "medium" | "low") => {
    onFilterChange({
      ...activeFilters,
      fitForLanca: activeFilters.fitForLanca === fit ? null : fit,
    });
  };

  const handleStoreSizeToggle = (size: "boutique" | "medium" | "large") => {
    const isActive = activeFilters.storeSize === size;

    let minStores: number | null = null;
    let maxStores: number | null = null;

    if (!isActive) {
      if (size === "boutique") {
        minStores = 1;
        maxStores = 5;
      } else if (size === "medium") {
        minStores = 6;
        maxStores = 20;
      } else if (size === "large") {
        minStores = 21;
        maxStores = null;
      }
    }

    onFilterChange({
      ...activeFilters,
      storeSize: isActive ? null : size,
      minStores: isActive ? null : minStores,
      maxStores: isActive ? null : maxStores,
    });
  };

  const handlePriceRangeToggle = (range: "under_500" | "500_1000" | "1000_2000" | "over_2000") => {
    const isActive = activeFilters.priceRange === range;

    let minPrice: number | null = null;
    let maxPrice: number | null = null;

    if (!isActive) {
      if (range === "under_500") {
        minPrice = 0.01;
        maxPrice = 499.99;
      } else if (range === "500_1000") {
        minPrice = 500;
        maxPrice = 999.99;
      } else if (range === "1000_2000") {
        minPrice = 1000;
        maxPrice = 1999.99;
      } else if (range === "over_2000") {
        minPrice = 2000;
        maxPrice = null;
      }
    }

    onFilterChange({
      ...activeFilters,
      priceRange: isActive ? null : range,
      minPrice: isActive ? null : minPrice,
      maxPrice: isActive ? null : maxPrice,
    });
  };

  const clearAllFilters = () => {
    onFilterChange({
      storeSize: null,
      priceRange: null,
      fitForLanca: null,
      minStores: null,
      maxStores: null,
      minPrice: null,
      maxPrice: null,
    });
  };

  const hasActiveFilters =
    activeFilters.storeSize !== null ||
    activeFilters.fitForLanca !== null ||
    activeFilters.priceRange !== null;

  return (
    <div className="bg-white border border-border rounded-xl shadow-soft p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">Filtros</h3>
        </div>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={clearAllFilters}
            className="text-xs text-muted-foreground hover:text-foreground h-auto py-1 px-2"
          >
            <X className="h-3 w-3 mr-1" />
            Limpar
          </Button>
        )}
      </div>

      <div className="space-y-6">
        {/* Fit Lança */}
        <div>
          <h4 className="text-xs font-semibold text-foreground mb-3 uppercase tracking-wide">Compatibilidade</h4>
          <div className="space-y-2">
            {[
              { key: "high" as const, label: "Alto", sublabel: "Ideal", color: "emerald" },
              { key: "medium" as const, label: "Médio", sublabel: "Potencial", color: "amber" },
            ].map(({ key, label, sublabel, color }) => (
              <label key={key} className="flex items-center gap-3 cursor-pointer group py-1">
                <div className={`w-4 h-4 rounded border-2 transition-colors flex items-center justify-center ${
                  activeFilters.fitForLanca === key 
                    ? `bg-${color}-500 border-${color}-500` 
                    : `border-gray-300 group-hover:border-${color}-400`
                }`}>
                  {activeFilters.fitForLanca === key && <Check className="w-3 h-3 text-white" />}
                </div>
                <input
                  type="checkbox"
                  checked={activeFilters.fitForLanca === key}
                  onChange={() => handleFitToggle(key)}
                  className="sr-only"
                />
                <span className={`text-sm ${activeFilters.fitForLanca === key ? "text-foreground font-medium" : "text-muted-foreground"}`}>
                  {label} <span className="text-xs text-muted-foreground/60">({sublabel})</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="h-px bg-border" />

        {/* Store Size */}
        <div>
          <h4 className="text-xs font-semibold text-foreground mb-3 uppercase tracking-wide">Dimensão</h4>
          <div className="space-y-2">
            {[
              { key: "boutique" as const, label: "Boutique", sublabel: "1-5 lojas" },
              { key: "medium" as const, label: "Média", sublabel: "6-20 lojas" },
              { key: "large" as const, label: "Grande", sublabel: "20+ lojas" },
            ].map(({ key, label, sublabel }) => (
              <label key={key} className="flex items-center gap-3 cursor-pointer group py-1">
                <div className={`w-4 h-4 rounded border-2 transition-colors flex items-center justify-center ${
                  activeFilters.storeSize === key 
                    ? "bg-lanca-yellow border-lanca-yellow" 
                    : "border-gray-300 group-hover:border-lanca-yellowMid"
                }`}>
                  {activeFilters.storeSize === key && <Check className="w-3 h-3 text-lanca-black" />}
                </div>
                <input
                  type="checkbox"
                  checked={activeFilters.storeSize === key}
                  onChange={() => handleStoreSizeToggle(key)}
                  className="sr-only"
                />
                <span className={`text-sm ${activeFilters.storeSize === key ? "text-foreground font-medium" : "text-muted-foreground"}`}>
                  {label} <span className="text-xs text-muted-foreground/60">({sublabel})</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="h-px bg-border" />

        {/* Price Range */}
        <div>
          <h4 className="text-xs font-semibold text-foreground mb-3 uppercase tracking-wide">Preço (EUR)</h4>
          <div className="space-y-2">
            {[
              { key: "under_500" as const, label: "< €500" },
              { key: "500_1000" as const, label: "€500 - €1.000" },
              { key: "1000_2000" as const, label: "€1.000 - €2.000" },
              { key: "over_2000" as const, label: "> €2.000" },
            ].map(({ key, label }) => (
              <label key={key} className="flex items-center gap-3 cursor-pointer group py-1">
                <div className={`w-4 h-4 rounded border-2 transition-colors flex items-center justify-center ${
                  activeFilters.priceRange === key 
                    ? "bg-lanca-yellow border-lanca-yellow" 
                    : "border-gray-300 group-hover:border-lanca-yellowMid"
                }`}>
                  {activeFilters.priceRange === key && <Check className="w-3 h-3 text-lanca-black" />}
                </div>
                <input
                  type="checkbox"
                  checked={activeFilters.priceRange === key}
                  onChange={() => handlePriceRangeToggle(key)}
                  className="sr-only"
                />
                <span className={`text-sm ${activeFilters.priceRange === key ? "text-foreground font-medium" : "text-muted-foreground"}`}>
                  {label}
                </span>
              </label>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
