"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    Users,
    Globe,
    Award,
    MapPin,
    Star,
    ArrowLeft,
    Store,
    Calendar,
    TrendingUp,
    Handshake,
} from "lucide-react";

const LANCA_CLIENTS = [
  {
      name: "Hawes & Curtis",
      country: "Reino Unido",
      city: "Londres",
      years: 10,
      stores: 30,
      style: "Heritage / Premium",
      notes: "Líder global em volume de receita. Alfaiataria técnica de excelência.",
      tier: "Elite"
  },
  {
      name: "Carlos Nieto",
      country: "Colômbia",
      city: "Bogotá",
      years: 12,
      stores: 20,
      style: "Premium Business",
      notes: "Parceria estratégica de longo prazo. Domínio do mercado premium colombiano.",
      tier: "Elite"
  },
  {
      name: "Favourbrook",
      country: "Reino Unido",
      city: "Londres",
      years: 10,
      stores: 8,
      style: "Luxo / Bespoke",
      notes: "Foco em cerimónia e luxo no coração de Londres.",
      tier: "Elite"
  },
  {
      name: "Wickett Jones",
      country: "Portugal",
      city: "Lisboa",
      years: 10,
      stores: 3,
      style: "Modern Premium",
      notes: "Referência nacional estratégica nos mercados de Lisboa e Porto.",
      tier: "Elite"
  },
  {
      name: "Sturm (Martin Sturm)",
      country: "Áustria",
      city: "Viena",
      years: 5,
      stores: 1,
      style: "Luxo / Premium",
      notes: "Boutique multimarca com o ticket médio mais alto do portfolio.",
      tier: "Platinum"
  },
  {
      name: "Grupo YES (Adolfo Dominguez PE)",
      country: "Peru",
      city: "Lima",
      years: 7,
      stores: 29,
      style: "Premium Multimarca",
      notes: "Grande presença no retalho e distribuição estratégica no mercado peruano.",
      tier: "Elite"
  },
  {
      name: "Jajoan (Sastrerías Españolas)",
      country: "Espanha",
      city: "Madrid",
      years: 7,
      stores: 6,
      style: "Tradicional / Bespoke",
      notes: "Excelência em alfaiataria tradicional com forte presença no mercado espanhol.",
      tier: "Platinum"
  },
  {
      name: "Walker Slater",
      country: "Reino Unido",
      city: "Edimburgo",
      years: 5,
      stores: 5,
      style: "Heritage / Tweed",
      notes: "Especialista em tweed escocês e estética heritage britânica.",
      tier: "Platinum"
  },
  {
      name: "Brigdens",
      country: "Reino Unido",
      city: "Derby",
      years: 10,
      stores: 2,
      style: "Premium Multimarca",
      notes: "Parceria de década focada em curadoria premium e serviço personalizado.",
      tier: "Platinum"
  },
  {
      name: "Gresham Blake",
      country: "Reino Unido",
      city: "Brighton",
      years: 10,
      stores: 1,
      style: "Bespoke / Contemporâneo",
      notes: "Alfaiataria contemporânea com foco em design exclusivo e bespoke.",
      tier: "Platinum"
  },
  {
      name: "Fernando de Carcer",
      country: "Espanha",
      city: "Madrid",
      years: 3,
      stores: 1,
      style: "Premium / Retail",
      notes: "Marca própria de prestígio no mercado de luxo de Madrid.",
      tier: "Standard"
  },
  {
      name: "Flax London (Original Fivers)",
      country: "Reino Unido",
      city: "Londres",
      years: 3,
      stores: 2,
      style: "Contemporâneo / Premium",
      notes: "Design moderno focado em materiais nobres e cortes contemporâneos.",
      tier: "Standard"
  },
  {
      name: "Trotter & Dean",
      country: "Reino Unido",
      city: "Cambridge",
      years: 2,
      stores: 5,
      style: "Heritage / Premium",
      notes: "Foco acadêmico e clássico com forte presença em Cambridge.",
      tier: "Standard"
  },
  {
      name: "Garcia Madrid",
      country: "Espanha",
      city: "Madrid",
      years: 10,
      stores: 1,
      style: "Premium / Designer",
      notes: "Design de autor espanhol com 10 anos de colaboração contínua.",
      tier: "Standard"
  },
  {
      name: "Progress Dealer (Dealer)",
      country: "Angola",
      city: "Luanda",
      years: 7,
      stores: 2,
      style: "Premium / Business",
      notes: "Líder de mercado no segmento premium em Luanda, Angola.",
      tier: "Platinum"
  },
  {
      name: "Vila Verdi",
      country: "Bélgica",
      city: "Gante",
      years: 10,
      stores: 1,
      style: "Bespoke / Exclusivo",
      notes: "Boutique exclusiva com foco total em alfaiataria por medida.",
      tier: "Platinum"
  },
  {
      name: "Oliver Brown (Supaman)",
      country: "Reino Unido",
      city: "Londres",
      years: 10,
      stores: 5,
      style: "Luxo / Heritage",
      notes: "Referência em vestuário de luxo para eventos e herança britânica.",
      tier: "Platinum"
  },
  {
      name: "Anthony's London (Coshile)",
      country: "Rep. Checa",
      city: "Praga",
      years: 6,
      stores: 8,
      style: "Premium / Contemporâneo",
      notes: "Maior parceiro na Europa Central, com 8 lojas premium.",
      tier: "Platinum"
  },
  {
      name: "Adolfo Dominguez",
      country: "Espanha",
      city: "Madrid",
      years: 2,
      stores: 340,
      style: "Designer Moderno",
      notes: "Design de autor global com alto volume industrial.",
      tier: "Global"
  },
  {
      name: "Hugo Boss",
      country: "Alemanha",
      city: "Metzingen",
      years: 2,
      stores: 1000,
      style: "Modern Business",
      notes: "Referência global na alfaiataria industrial de luxo.",
      tier: "Global"
  },
  {
      name: "Hackett London",
      country: "Reino Unido",
      city: "Londres",
      years: 4,
      stores: 150,
      style: "British Heritage",
      notes: "Estética de gentleman britânico modernizado.",
      tier: "Global"
  }
];

export default function ClientsPage() {
    const totalStores = LANCA_CLIENTS.reduce((acc, c) => acc + c.stores, 0);
    const avgYears = Math.round(LANCA_CLIENTS.reduce((acc, c) => acc + c.years, 0) / LANCA_CLIENTS.length);
    const countries = new Set(LANCA_CLIENTS.map(c => c.country)).size;

    return (
        <div className="min-h-screen bg-background font-sans">
            {/* Header */}
            <header className="bg-white border-b border-border sticky top-0 z-40 px-6 lg:px-10 py-4">
                <div className="max-w-6xl mx-auto flex justify-between items-center">
                    <div className="flex items-center gap-4">
                        <Link href="/">
                            <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground hover:text-foreground rounded-lg">
                                <ArrowLeft className="h-4 w-4" />
                                <span className="text-sm">Voltar</span>
                            </Button>
                        </Link>
                        <div className="h-5 w-px bg-border" />
                        <div>
                            <h1 className="text-lg font-semibold text-foreground">Rede de Clientes</h1>
                            <p className="text-sm text-muted-foreground">Parceiros ativos da Confeções Lança</p>
                        </div>
                    </div>
                </div>
            </header>

            <main className="max-w-6xl mx-auto px-6 lg:px-10 py-10">
                {/* Stats Overview */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10 smooth-entry">
                    <div className="bg-lanca-black p-6 rounded-xl shadow-medium col-span-2 lg:col-span-1">
                        <Handshake className="h-5 w-5 text-lanca-yellow mb-3" />
                        <p className="text-xs text-white/50 font-medium uppercase tracking-wide mb-1">Clientes Ativos</p>
                        <p className="text-3xl font-bold text-white">{LANCA_CLIENTS.length}</p>
                    </div>
                    <div className="bg-white p-6 rounded-xl border border-border shadow-soft">
                        <Globe className="h-5 w-5 text-muted-foreground mb-3" />
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-1">Países</p>
                        <p className="text-3xl font-bold text-foreground">{countries}</p>
                    </div>
                    <div className="bg-white p-6 rounded-xl border border-border shadow-soft">
                        <Store className="h-5 w-5 text-muted-foreground mb-3" />
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-1">Total de Lojas</p>
                        <p className="text-3xl font-bold text-foreground">{totalStores.toLocaleString()}</p>
                    </div>
                    <div className="bg-white p-6 rounded-xl border border-border shadow-soft">
                        <Calendar className="h-5 w-5 text-muted-foreground mb-3" />
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-1">Média de Anos</p>
                        <p className="text-3xl font-bold text-foreground">{avgYears}</p>
                    </div>
                </div>

                {/* Section Header */}
                <div className="flex items-center gap-3 mb-6 smooth-entry" style={{ animationDelay: "0.1s" }}>
                    <div className="w-1 h-6 bg-lanca-yellow rounded-full" />
                    <h2 className="text-sm font-semibold text-foreground uppercase tracking-wide">Parceiros Globais</h2>
                    <div className="flex-1 h-px bg-border" />
                </div>

                {/* Clients Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 smooth-entry" style={{ animationDelay: "0.2s" }}>
                    {LANCA_CLIENTS.map((client, idx) => (
                        <div key={idx} className="card-lanca p-6 flex flex-col h-full group">
                            {/* Card Header */}
                            <div className="flex items-start justify-between mb-4">
                                <div className="w-11 h-11 bg-lanca-yellowLight rounded-lg flex items-center justify-center group-hover:bg-lanca-yellow transition-colors duration-200">
                                    <Award className="h-5 w-5 text-lanca-yellowDark group-hover:text-lanca-black transition-colors" />
                                </div>
                                <Badge className={`text-[11px] font-medium rounded-md px-2 py-0.5 ${
                                    client.tier === "Elite" 
                                        ? "bg-lanca-black text-white" 
                                        : client.tier === "Platinum" 
                                        ? "bg-lanca-yellowLight text-lanca-yellowDark border border-lanca-yellow/20"
                                        : client.tier === "Global"
                                        ? "bg-blue-50 text-blue-700 border border-blue-200"
                                        : "bg-muted text-muted-foreground"
                                }`}>
                                    {client.tier}
                                </Badge>
                            </div>
                            
                            {/* Name & Location */}
                            <h3 className="text-lg font-semibold text-foreground mb-2 group-hover:text-lanca-yellowDark transition-colors">
                                {client.name}
                            </h3>
                            <div className="flex items-center gap-1.5 text-muted-foreground mb-4">
                                <MapPin className="h-3.5 w-3.5" />
                                <span className="text-sm">{client.city}, {client.country}</span>
                            </div>

                            {/* Stats */}
                            <div className="grid grid-cols-2 gap-3 mb-4 mt-auto">
                                <div className="bg-muted/50 rounded-lg p-3">
                                    <p className="text-xs text-muted-foreground mb-0.5">Parceiros há</p>
                                    <p className="text-sm font-semibold text-foreground">{client.years} anos</p>
                                </div>
                                <div className="bg-muted/50 rounded-lg p-3">
                                    <p className="text-xs text-muted-foreground mb-0.5">Lojas</p>
                                    <p className="text-sm font-semibold text-foreground">{client.stores}</p>
                                </div>
                            </div>

                            {/* Style & Notes */}
                            <div className="pt-4 border-t border-border space-y-2">
                                <div className="flex items-center gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-lanca-yellow" />
                                    <span className="text-xs font-medium text-muted-foreground">{client.style}</span>
                                </div>
                                <p className="text-sm text-muted-foreground leading-relaxed">
                                    {client.notes}
                                </p>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Bottom CTA */}
                <div className="mt-16 bg-white rounded-xl border border-border shadow-soft p-10 text-center smooth-entry" style={{ animationDelay: "0.3s" }}>
                    <div className="w-14 h-14 bg-lanca-yellowLight rounded-xl flex items-center justify-center mx-auto mb-5">
                        <TrendingUp className="h-6 w-6 text-lanca-yellowDark" />
                    </div>
                    <h3 className="text-xl font-semibold text-foreground mb-2">Excelência desde 1973</h3>
                    <p className="text-sm text-muted-foreground max-w-lg mx-auto leading-relaxed">
                        Estes parceiros representam o padrão de qualidade da Confeções Lança. 
                        A nossa plataforma de pesquisa por IA replica este rigor na descoberta de novos mercados globais.
                    </p>
                </div>
            </main>

            {/* Footer */}
            <footer className="border-t border-border py-6 text-center bg-white mt-10">
                <p className="text-xs text-muted-foreground">
                    Confeções Lança © 2026 · Desde 1973 · Plataforma Comercial
                </p>
            </footer>
        </div>
    );
}
