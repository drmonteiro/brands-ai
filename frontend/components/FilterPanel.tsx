"use client";

import { ChevronDown, X } from "lucide-react";

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
      if (size === "boutique") { minStores = 1; maxStores = 5; }
      else if (size === "medium") { minStores = 6; maxStores = 20; }
      else if (size === "large") { minStores = 21; maxStores = null; }
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
      if (range === "under_500") { minPrice = 0.01; maxPrice = 499.99; }
      else if (range === "500_1000") { minPrice = 500; maxPrice = 999.99; }
      else if (range === "1000_2000") { minPrice = 1000; maxPrice = 1999.99; }
      else if (range === "over_2000") { minPrice = 2000; maxPrice = null; }
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

  const hasActiveFilters = Boolean(
    activeFilters.storeSize || activeFilters.fitForLanca || activeFilters.priceRange
  );

  const pillClass = (isActive: boolean) =>
    `px-2.5 py-1 text-[11px] font-medium rounded border transition-all ${
      isActive 
        ? "bg-lanca-ink text-white border-lanca-ink shadow-sm" 
        : "bg-white text-muted-foreground border-border hover:border-lanca-gold/60 hover:text-foreground"
    }`;

  const groupLabelClass = "text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground w-20 flex-shrink-0 lg:w-auto lg:mr-2 flex-shrink-0";

  return (
    <details className="group lg:contents" open={hasActiveFilters || undefined}>
      <summary className="flex cursor-pointer list-none items-center justify-between py-1 text-[13px] font-medium text-foreground lg:hidden">
        Filtros{hasActiveFilters ? " (ativos)" : ""}
        <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
      </summary>
    <div className="flex flex-col gap-2.5 py-2 lg:flex-row lg:flex-wrap lg:items-center lg:gap-x-8 lg:py-0">
      
      {/* Fit Lança Row */}
      <div className="flex items-center">
        <span className={groupLabelClass}>Qualidade</span>
        <div className="flex flex-wrap gap-1.5">
          <button 
            onClick={() => handleFitToggle("high")} 
            className={pillClass(activeFilters.fitForLanca === "high")}
          >Alta</button>
          <button 
            onClick={() => handleFitToggle("medium")} 
            className={pillClass(activeFilters.fitForLanca === "medium")}
          >Média</button>
        </div>
      </div>

      {/* Store Size Row */}
      <div className="flex items-center">
        <span className={groupLabelClass}>Dimensão</span>
        <div className="flex flex-wrap gap-1.5">
          <button 
            onClick={() => handleStoreSizeToggle("boutique")} 
            className={pillClass(activeFilters.storeSize === "boutique")}
          >Boutique</button>
          <button 
            onClick={() => handleStoreSizeToggle("medium")} 
            className={pillClass(activeFilters.storeSize === "medium")}
          >6-20 Lojas</button>
          <button 
            onClick={() => handleStoreSizeToggle("large")} 
            className={pillClass(activeFilters.storeSize === "large")}
          >20+ Lojas</button>
        </div>
      </div>

      {/* Price Row & Clear */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center">
          <span className={groupLabelClass}>Preço</span>
          <div className="flex flex-wrap gap-1.5">
            <button 
              onClick={() => handlePriceRangeToggle("under_500")} 
              className={pillClass(activeFilters.priceRange === "under_500")}
            >{"<"} 500€</button>
            <button 
              onClick={() => handlePriceRangeToggle("500_1000")} 
              className={pillClass(activeFilters.priceRange === "500_1000")}
            >500-1k€</button>
            <button 
              onClick={() => handlePriceRangeToggle("1000_2000")} 
              className={pillClass(activeFilters.priceRange === "1000_2000")}
            >1k-2k€</button>
            <button 
              onClick={() => handlePriceRangeToggle("over_2000")} 
              className={pillClass(activeFilters.priceRange === "over_2000")}
            >{">"} 2k€</button>
          </div>
        </div>

        {hasActiveFilters && (
          <button
            onClick={clearAllFilters}
            className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-rose-500 transition-colors bg-rose-50/50 hover:bg-rose-50 px-2 py-1 rounded"
          >
            <X className="h-3 w-3" />
            Limpar
          </button>
        )}
      </div>

    </div>
    </details>
  );
}
