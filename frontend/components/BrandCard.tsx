"use client";

import { useState } from "react";
import { BrandLead } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Globe,
  Mail,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  ShieldCheck,
  Sparkles,
  MapPin
} from "lucide-react";

interface BrandCardProps {
  brand: BrandLead;
  onSendEmail?: (brand: BrandLead) => void;
}

export function BrandCard({ brand, onSendEmail }: BrandCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [emailStatus, setEmailStatus] = useState<"idle" | "sending" | "sent">("idle");

  const handleSendEmail = () => {
    setEmailStatus("sending");
    if (onSendEmail) {
      onSendEmail(brand);
    }
    // Simulate sending for UI feedback
    setTimeout(() => setEmailStatus("sent"), 1500);
  };

  const initial = brand.name.charAt(0).toUpperCase();

  return (
    <div className="group bg-white border border-zinc-200 rounded-xl shadow-sm transition-all duration-300 hover:shadow-md relative overflow-hidden">


      <div className="p-6 md:p-8">
        <div className="flex flex-col xl:flex-row gap-8">
          {/* LEFT COLUMN: Identity & Main Stats */}
          <div className="xl:w-80 space-y-6">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 w-16 h-16 bg-blue-600 rounded-lg flex items-center justify-center text-2xl font-bold text-white relative">
                <span className="relative z-10">{initial}</span>
                {brand.verified && (
                  <div className="absolute -top-1 -right-1 bg-white p-0.5 rounded-full shadow-sm">
                    <CheckCircle2 className="h-4 w-4 text-blue-600" />
                  </div>
                )}
              </div>
              <div className="min-w-0">
                <h3 className="font-bold text-xl text-zinc-900 mb-1 group-hover:text-blue-600 transition-colors truncate">
                  {brand.name}
                </h3>
                <Badge variant="secondary" className="text-[10px] font-medium tracking-normal rounded-md">
                  {brand.storeCount === 1 ? "SINGLE ATELIER" : `${brand.storeCount} LOCAIS`}
                </Badge>
              </div>
            </div>

            <div className="space-y-4 pt-6 border-t border-zinc-100">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-zinc-500">Preço Médio</span>
                <div className="text-right">
                  <span className="text-xl font-bold text-zinc-900">${brand.averageSuitPriceUSD ? brand.averageSuitPriceUSD.toFixed(0) : "0"}</span>
                  <span className="text-[10px] text-zinc-400 font-medium ml-1">USD</span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-zinc-500">Localização</span>
                <div className="flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5 text-blue-600" />
                  <span className="text-xs font-semibold text-zinc-900">{brand.city || "N/A"}</span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-zinc-500">Posicionamento</span>
                <Badge className="bg-blue-50 text-blue-700 border-blue-100 text-[10px] font-bold rounded-md px-2">
                  {brand.averageSuitPriceUSD && brand.averageSuitPriceUSD > 1500 ? "ULTRA LUXURY" : "PREMIUM"}
                </Badge>
              </div>

              <div className="pt-4">
                <a
                  href={brand.websiteUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 w-full py-3 border border-zinc-200 rounded-lg text-xs font-semibold text-zinc-600 hover:text-blue-600 hover:bg-blue-50 transition-all duration-300"
                >
                  <Globe className="h-4 w-4" />
                  Website oficial
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
          </div>

          {/* RIGHT COLUMN: Insights & Analysis */}
          <div className="xl:flex-1 space-y-8">
            {/* The 4 pillars Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {[
                { label: "Retail", title: "Lojas Físicas", value: brand.storeCount, active: true },
                {
                  label: "Fabric",
                  title: "100% Lã",
                  value: brand.woolPercentage ? (brand.woolPercentage.includes('100%') ? "SIM" : brand.woolPercentage) : "PENDENTE",
                  active: !!brand.woolPercentage
                },
                {
                  label: "Service",
                  title: "À Medida",
                  value: brand.madeToMeasure ? "SIM" : "NÃO",
                  active: !!brand.madeToMeasure
                },
                { label: "Retail", title: "Zona Prestígio", value: brand.locationQuality === 'premium' ? "EXCELENTE" : "STANDARD", active: brand.locationQuality === 'premium' }
              ].map((item, i) => (
                <div key={i} className="p-4 bg-zinc-50 border border-zinc-100 rounded-lg flex flex-col gap-1">
                  <span className="text-[10px] font-bold text-blue-600 uppercase tracking-tight">{item.label}</span>
                  <div>
                    <p className="text-[10px] font-medium text-zinc-500 uppercase">{item.title}</p>
                    <p className={`text-sm font-bold ${item.active ? 'text-zinc-900' : 'text-zinc-400'}`}>{item.value}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Content summary */}
            <div className="space-y-4">
              <div className="relative pl-4 border-l-2 border-blue-200">
                <p className="text-zinc-600 text-base leading-relaxed">
                  {brand.companyOverview}
                </p>
              </div>

              {/* Action Buttons Row */}
              <div className="flex flex-col sm:flex-row gap-3 pt-4">
                <Button
                  onClick={handleSendEmail}
                  disabled={emailStatus !== "idle"}
                  className={`flex-1 h-12 font-bold text-sm rounded-lg transition-all duration-300 ${emailStatus === "sent" ? "bg-green-600 text-white" : "bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
                    }`}
                >
                  {emailStatus === "idle" ? (
                    <span className="flex items-center gap-2"><Mail className="h-4 w-4" /> Enviar Proposta</span>
                  ) : emailStatus === "sending" ? (
                    <span className="flex items-center gap-2"><div className="h-4 w-4 border-2 border-white/20 border-t-white rounded-full animate-spin" /> A PROCESSAR</span>
                  ) : (
                    <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4" /> Enviado</span>
                  )}
                </Button>

                <Button
                  variant="outline"
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="h-12 px-6 border-zinc-200 text-zinc-600 hover:text-zinc-900 font-bold text-sm rounded-lg hover:bg-zinc-50"
                >
                  {isExpanded ? (
                    <span className="flex items-center gap-2"><ChevronUp className="h-4 w-4 text-blue-600" /> Ocultar</span>
                  ) : (
                    <span className="flex items-center gap-2"><ChevronDown className="h-4 w-4 text-blue-600" /> Detalhes</span>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Expandable Section: Detailed Analysis & Locations */}
        {isExpanded && (
          <div className="mt-8 pt-8 border-t border-zinc-100 animate-in fade-in slide-in-from-top-4 duration-500">
            <div className="grid xl:grid-cols-12 gap-10">
              <div className="xl:col-span-8 space-y-8">
                {brand.detailedDescription && brand.detailedDescription.length > 0 && (
                  <section className="bg-zinc-50 p-6 rounded-xl border border-zinc-100 relative">
                    <div className="flex items-center gap-2 mb-4">
                      <Sparkles className="h-4 w-4 text-blue-600" />
                      <h4 className="text-[10px] font-bold tracking-widest uppercase text-blue-600">RELATÓRIO LANÇA AI</h4>
                    </div>
                    <p className="text-sm text-zinc-700 leading-relaxed whitespace-pre-wrap">
                      {brand.detailedDescription}
                    </p>
                  </section>
                )}

                {(() => {
                  const locations = Array.isArray(brand.storeLocations) ? brand.storeLocations : [];
                  if (locations.length === 0) return null;

                  return (
                    <section>
                      <h4 className="text-[10px] font-bold tracking-widest uppercase text-zinc-400 mb-6 flex items-center gap-2">
                        <MapPin className="h-4 w-4 text-blue-600" />
                        Presença Física (@{brand.city})
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {locations.map((loc, i) => (
                          <div key={i} className="flex gap-3 p-4 bg-zinc-50 border border-zinc-100 items-start rounded-lg">
                            <div className="w-1.5 h-1.5 rounded-full bg-blue-600 mt-2" />
                            <span className="text-xs font-medium text-zinc-600">{loc}</span>
                          </div>
                        ))}
                      </div>
                    </section>
                  );
                })()}
              </div>

              <div className="xl:col-span-4 space-y-8">
                <section>
                  <h4 className="text-[10px] font-bold tracking-widest uppercase text-zinc-400 mb-6">ADN TÉCNICO</h4>
                  <div className="space-y-4">
                    {[
                      { l: "Estilo", v: brand.brandStyle || "Premium" },
                      { l: "Modelo", v: brand.businessModel || "Retalho" },
                      { l: "Origem", v: brand.originCountry }
                    ].map((item, i) => (
                      <div key={i} className="flex justify-between items-center">
                        <span className="text-[10px] font-medium text-zinc-400 uppercase tracking-tight">{item.l}</span>
                        <span className="text-xs font-bold text-zinc-900 uppercase">{item.v}</span>
                      </div>
                    ))}
                  </div>
                </section>

                <div className="bg-blue-50/50 p-8 text-center border border-blue-100 rounded-xl">
                  <p className="text-[9px] font-bold tracking-widest text-blue-600 mb-4 uppercase">PARTNERSHIP SCORE</p>
                  <p className="text-6xl font-bold text-blue-900 mb-2">9.8</p>
                  <div className="flex gap-1 justify-center opacity-20">
                    {[1, 2, 3, 4, 5].map(i => <div key={i} className="w-1 h-1 rounded-full bg-blue-900" />)}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
