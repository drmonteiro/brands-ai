"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { X, Check } from "lucide-react";

interface FilterPanelProps {
  onFilterChange: (filters: ProspectFilters) => void;
  activeFilters: ProspectFilters;
}

export interface ProspectFilters {
  storeSize?: "boutique" | "medium" | "large" | null;
  priceRange?: "under_500" | "500_1000" | "1000_2000" | "over_2000" | null;
  minStores?: number | null;
  maxStores?: number | null;
  minPrice?: number | null;
  maxPrice?: number | null;
}

export function FilterPanel({ onFilterChange, activeFilters }: FilterPanelProps) {
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
      minStores: null,
      maxStores: null,
      minPrice: null,
      maxPrice: null,
    });
  };

  const hasActiveFilters =
    activeFilters.storeSize !== null ||
    activeFilters.priceRange !== null;

  return (
    <div className="p-4 bg-white border border-zinc-200 rounded-xl h-full shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <h3 className="font-medium text-sm text-gray-900 uppercase tracking-widest">Filtros</h3>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={clearAllFilters}
            className="text-xs text-gray-400 hover:text-gray-900 h-auto p-0 hover:bg-transparent"
          >
            Limpar
          </Button>
        )}
      </div>

      <div className="space-y-8">
        {/* Store Size Filters */}
        <div>
          <h4 className="text-sm font-semibold text-gray-900 mb-4">Dimensão da Loja</h4>
          <div className="space-y-3">
            <label className="flex items-center gap-3 cursor-pointer group">
              <div className={`w-4 h-4 rounded border transition-colors flex items-center justify-center
                ${activeFilters.storeSize === "boutique" ? "bg-blue-600 border-blue-600" : "border-zinc-300 group-hover:border-blue-400"}
              `}>
                {activeFilters.storeSize === "boutique" && <Check className="w-3 h-3 text-white" />}
              </div>
              <input
                type="checkbox"
                checked={activeFilters.storeSize === "boutique"}
                onChange={() => handleStoreSizeToggle("boutique")}
                className="sr-only"
              />
              <span className={`text-sm ${activeFilters.storeSize === "boutique" ? "text-gray-900 font-medium" : "text-gray-600"}`}>
                Boutique <span className="text-gray-400 text-xs ml-1">(1-5)</span>
              </span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer group">
              <div className={`w-4 h-4 rounded border transition-colors flex items-center justify-center
                ${activeFilters.storeSize === "medium" ? "bg-blue-600 border-blue-600" : "border-zinc-300 group-hover:border-blue-400"}
              `}>
                {activeFilters.storeSize === "medium" && <Check className="w-3 h-3 text-white" />}
              </div>
              <input
                type="checkbox"
                checked={activeFilters.storeSize === "medium"}
                onChange={() => handleStoreSizeToggle("medium")}
                className="sr-only"
              />
              <span className={`text-sm ${activeFilters.storeSize === "medium" ? "text-gray-900 font-medium" : "text-gray-600"}`}>
                Medium <span className="text-gray-400 text-xs ml-1">(6-20)</span>
              </span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer group">
              <div className={`w-4 h-4 rounded border transition-colors flex items-center justify-center
                ${activeFilters.storeSize === "large" ? "bg-blue-600 border-blue-600" : "border-zinc-300 group-hover:border-blue-400"}
              `}>
                {activeFilters.storeSize === "large" && <Check className="w-3 h-3 text-white" />}
              </div>
              <input
                type="checkbox"
                checked={activeFilters.storeSize === "large"}
                onChange={() => handleStoreSizeToggle("large")}
                className="sr-only"
              />
              <span className={`text-sm ${activeFilters.storeSize === "large" ? "text-gray-900 font-medium" : "text-gray-600"}`}>
                Large <span className="text-gray-400 text-xs ml-1">(20+)</span>
              </span>
            </label>
          </div>
        </div>

        {/* Separator */}
        <div className="h-px bg-gray-100" />

        {/* Price Range Filters */}
        <div>
          <h4 className="text-sm font-semibold text-gray-900 mb-4">Preço (EUR)</h4>
          <div className="space-y-3">
            <label className="flex items-center gap-3 cursor-pointer group">
              <div className={`w-4 h-4 rounded border transition-colors flex items-center justify-center
                ${activeFilters.priceRange === "under_500" ? "bg-blue-600 border-blue-600" : "border-zinc-300 group-hover:border-blue-400"}
              `}>
                {activeFilters.priceRange === "under_500" && <Check className="w-3 h-3 text-white" />}
              </div>
              <input
                type="checkbox"
                checked={activeFilters.priceRange === "under_500"}
                onChange={() => handlePriceRangeToggle("under_500")}
                className="sr-only"
              />
              <span className={`text-sm ${activeFilters.priceRange === "under_500" ? "text-gray-900 font-medium" : "text-gray-600"}`}>
                &lt; €500
              </span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer group">
              <div className={`w-4 h-4 rounded border transition-colors flex items-center justify-center
                ${activeFilters.priceRange === "500_1000" ? "bg-blue-600 border-blue-600" : "border-zinc-300 group-hover:border-blue-400"}
              `}>
                {activeFilters.priceRange === "500_1000" && <Check className="w-3 h-3 text-white" />}
              </div>
              <input
                type="checkbox"
                checked={activeFilters.priceRange === "500_1000"}
                onChange={() => handlePriceRangeToggle("500_1000")}
                className="sr-only"
              />
              <span className={`text-sm ${activeFilters.priceRange === "500_1000" ? "text-gray-900 font-medium" : "text-gray-600"}`}>
                €500 - €1.000
              </span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer group">
              <div className={`w-4 h-4 rounded border transition-colors flex items-center justify-center
                ${activeFilters.priceRange === "1000_2000" ? "bg-blue-600 border-blue-600" : "border-zinc-300 group-hover:border-blue-400"}
              `}>
                {activeFilters.priceRange === "1000_2000" && <Check className="w-3 h-3 text-white" />}
              </div>
              <input
                type="checkbox"
                checked={activeFilters.priceRange === "1000_2000"}
                onChange={() => handlePriceRangeToggle("1000_2000")}
                className="sr-only"
              />
              <span className={`text-sm ${activeFilters.priceRange === "1000_2000" ? "text-gray-900 font-medium" : "text-gray-600"}`}>
                €1.000 - €2.000
              </span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer group">
              <div className={`w-4 h-4 rounded border transition-colors flex items-center justify-center
                ${activeFilters.priceRange === "over_2000" ? "bg-blue-600 border-blue-600" : "border-zinc-300 group-hover:border-blue-400"}
              `}>
                {activeFilters.priceRange === "over_2000" && <Check className="w-3 h-3 text-white" />}
              </div>
              <input
                type="checkbox"
                checked={activeFilters.priceRange === "over_2000"}
                onChange={() => handlePriceRangeToggle("over_2000")}
                className="sr-only"
              />
              <span className={`text-sm ${activeFilters.priceRange === "over_2000" ? "text-gray-900 font-medium" : "text-gray-600"}`}>
                &gt; €2.000
              </span>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}
