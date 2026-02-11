"use client";

import {
    Users,
    Globe2,
    Award,
    CheckCircle2,
    MapPin,
    TrendingUp,
    Star,
    ArrowRight
} from "lucide-react";

const LANCA_CLIENTS = [
    {
        name: "Hawes & Curtis",
        country: "Reino Unido",
        city: "Londres",
        years: 10,
        stores: 30,
        price: "500€",
        style: "Heritage / Premium",
        notes: "Melhor cliente em faturação. Referência global em camisaria e alfaiataria técnica.",
        tier: "Elite"
    },
    {
        name: "Carlos Nieto",
        country: "Colômbia",
        city: "Bogotá",
        years: 12,
        stores: 20,
        price: "800€",
        style: "Premium Business",
        notes: "Parceria estratégica de longa data. Domínio absoluto do mercado premium colombiano.",
        tier: "Elite"
    },
    {
        name: "Bayertree Favourbrook",
        country: "Reino Unido",
        city: "Londres",
        years: 10,
        stores: 8,
        price: "1000€",
        style: "Luxo / Bespoke",
        notes: "Foco em vestuário de cerimónia e alfaiataria de altíssimo luxo em Londres.",
        tier: "Elite"
    },
    {
        name: "Wickett Jones",
        country: "Portugal",
        city: "Lisboa",
        years: 10,
        stores: 3,
        price: "600€",
        style: "Premium Moderno",
        notes: "Referência no mercado nacional com presença estratégica em Lisboa e Gaia.",
        tier: "Elite"
    },
    {
        name: "Martin Sturm GMBH",
        country: "Áustria",
        city: "Viena",
        years: 5,
        stores: 1,
        price: "1500€",
        style: "Luxo / Premium",
        notes: "Boutique multimarca de prestígio com o ticket médio mais elevado do portfólio.",
        tier: "Platina"
    },
    {
        name: "Grupo YES",
        country: "Peru",
        city: "Lima",
        years: 7,
        stores: 29,
        price: "N/D",
        style: "Premium Multi-brand",
        notes: "Grande distribuidor da Adolfo Dominguez no Peru, com forte presença de retalho.",
        tier: "Elite"
    },
    {
        name: "Sastrerías Españolas",
        country: "Espanha",
        city: "Madrid",
        years: 7,
        stores: 6,
        price: "375€+",
        style: "Alfaiataria Tradicional",
        notes: "Marca Jajoan. Especialista em alfaiataria tradicional com escala em Espanha.",
        tier: "Platina"
    },
    {
        name: "Walker Slater",
        country: "Reino Unido",
        city: "Edimburgo",
        years: 5,
        stores: 5,
        price: "800€",
        style: "Heritage / Tweed",
        notes: "Referência mundial em Tweed escocês e cortes Heritage tradicionais.",
        tier: "Platina"
    },
    {
        name: "Brigdens",
        country: "Reino Unido",
        city: "Derby",
        years: 10,
        stores: 2,
        price: "800€",
        style: "Premium Business",
        notes: "Retalhista multimarca histórico com uma parceria sólida de uma década.",
        tier: "Platina"
    },
    {
        name: "Gresham Blake",
        country: "Reino Unido",
        city: "Brighton",
        years: 10,
        stores: 1,
        price: "1000€",
        style: "Bespoke Contemporâneo",
        notes: "Alfaiataria bespoke com design irreverente e contemporâneo em Brighton.",
        tier: "Platina"
    },
    {
        name: "Fernando de Carcer",
        country: "Espanha",
        city: "Madrid",
        years: 3,
        stores: 1,
        price: "600€",
        style: "Premium Espanhol",
        notes: "Parceria crescente num dos mercados mais importantes da Europa.",
        tier: "Ouro"
    },
    {
        name: "Original Fivers",
        country: "Reino Unido",
        city: "Londres",
        years: 3,
        stores: 2,
        price: "800€",
        style: "Premium Moderno",
        notes: "Dona da marca Flax London. Foco em materiais naturais e design moderno.",
        tier: "Ouro"
    },
    {
        name: "Trotter & Dean",
        country: "Reino Unido",
        city: "Cambridge",
        years: 2,
        stores: 5,
        price: "1000€",
        style: "Heritage / Premium",
        notes: "Marca de Cambridge com forte crescimento e foco em qualidade premium.",
        tier: "Ouro"
    },
    {
        name: "Garcia Madrid",
        country: "Espanha",
        city: "Madrid",
        years: 10,
        stores: 1,
        price: "1000€",
        style: "Premium Espanhol",
        notes: "Boutique icónica de Madrid com uma década de fidelização absoluta.",
        tier: "Platina"
    },
    {
        name: "Progress Dealer",
        country: "Angola",
        city: "Luanda",
        years: 7,
        stores: 2,
        price: "1000€",
        style: "Premium Angolano",
        notes: "Porta de entrada no mercado angolano com foco no segmento executivo.",
        tier: "Platina"
    },
    {
        name: "Vila Verdi",
        country: "Bélgica",
        city: "Ghent",
        years: 10,
        stores: 1,
        price: "800€",
        style: "Bespoke / Premium",
        notes: "Especialista em Made-to-Measure exclusivo no mercado belga.",
        tier: "Platina"
    },
    {
        name: "Supaman",
        country: "Reino Unido",
        city: "Londres",
        years: 10,
        stores: 5,
        price: "1000€",
        style: "Luxo / Heritage",
        notes: "Marca Oliver Brown. Presença de prestígio em Londres com foco em formal wear.",
        tier: "Platina"
    },
    {
        name: "Coshile",
        country: "República Checa",
        city: "Praga",
        years: 6,
        stores: 8,
        price: "750€",
        style: "Premium Contemporâneo",
        notes: "Dona da Anthony's London. Presença sólida na República Checa.",
        tier: "Platina"
    }
];

export default function ClientsPage() {
    return (
        <div className="min-h-screen bg-zinc-50/30">
            {/* Header */}
            <header className="bg-white border-b border-zinc-200 sticky top-0 z-20 px-8 py-4 flex justify-between items-center shadow-sm">
                <div>
                    <h1 className="text-xl font-bold text-zinc-900">Carteira de Clientes</h1>
                    <p className="text-xs text-zinc-500 font-medium">Confeções Lança • Referências de Produção</p>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-100 rounded-lg">
                        <Award className="h-4 w-4 text-blue-600" />
                        <span className="text-[10px] font-bold text-blue-700 uppercase">18 Clientes Ativos</span>
                    </div>
                </div>
            </header>

            <main className="p-8 max-w-7xl mx-auto">
                {/* Stats Overview */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
                    {[
                        { label: "Anos Médios", value: "8.5", icon: TrendingUp },
                        { label: "Mercados", value: "12", icon: Globe2 },
                        { label: "Retalho Próprio", value: "78%", icon: MapPin },
                        { label: "Fidelização", value: "94%", icon: Star },
                    ].map((stat, i) => (
                        <div key={i} className="bg-white p-6 border border-zinc-200 rounded-2xl shadow-sm relative overflow-hidden group hover:border-blue-300 transition-colors">
                            <stat.icon className="h-4 w-4 text-blue-500 mb-4" />
                            <p className="text-[10px] font-bold text-zinc-400 uppercase mb-1">{stat.label}</p>
                            <p className="text-2xl font-bold text-zinc-900">{stat.value}</p>
                        </div>
                    ))}
                </div>

                {/* Client Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {LANCA_CLIENTS.map((client, idx) => (
                        <div key={idx} className="bg-white border border-zinc-200 rounded-2xl overflow-hidden group hover:border-blue-400 transition-all hover:shadow-md">
                            <div className="p-6 border-b border-zinc-100 flex justify-between items-start">
                                <div className="min-w-0 pr-4">
                                    <h3 className="text-lg font-bold text-zinc-900 mb-1 group-hover:text-blue-600 transition-colors truncate">{client.name}</h3>
                                    <div className="flex items-center gap-1.5 text-[10px] font-bold text-zinc-500 uppercase">
                                        <MapPin className="h-3.5 w-3.5 text-blue-500" />
                                        {client.city}, {client.country}
                                    </div>
                                </div>
                                <span className={`shrink-0 px-2 py-1 text-[10px] font-bold uppercase rounded-md border ${client.tier === 'Elite' ? 'bg-blue-600 text-white border-blue-600' :
                                    client.tier === 'Platina' ? 'bg-blue-50 text-blue-700 border-blue-100' :
                                        'bg-zinc-50 text-zinc-500 border-zinc-200'
                                    }`}>
                                    {client.tier}
                                </span>
                            </div>

                            <div className="p-6 space-y-4">
                                <div className="grid grid-cols-2 gap-3">
                                    <div className="bg-zinc-50 p-3 rounded-xl border border-zinc-100/50">
                                        <p className="text-[9px] font-bold text-zinc-400 uppercase mb-1">Parceria</p>
                                        <p className="text-xs font-bold text-zinc-700">{client.years} Anos</p>
                                    </div>
                                    <div className="bg-zinc-50 p-3 rounded-xl border border-zinc-100/50">
                                        <p className="text-[9px] font-bold text-zinc-400 uppercase mb-1">Lojas</p>
                                        <p className="text-xs font-bold text-zinc-700">{client.stores}</p>
                                    </div>
                                    <div className="bg-zinc-50 p-3 rounded-xl border border-zinc-100/50">
                                        <p className="text-[9px] font-bold text-zinc-400 uppercase mb-1">Preço</p>
                                        <p className="text-xs font-bold text-zinc-700">{client.price}</p>
                                    </div>
                                    <div className="bg-zinc-50 p-3 rounded-xl border border-zinc-100/50">
                                        <p className="text-[9px] font-bold text-zinc-400 uppercase mb-1">Estilo</p>
                                        <p className="text-xs font-bold text-zinc-700 truncate">{client.style}</p>
                                    </div>
                                </div>

                                <div className="relative pl-4 border-l-2 border-blue-200">
                                    <p className="text-xs text-zinc-600 leading-relaxed font-medium">
                                        {client.notes}
                                    </p>
                                </div>

                                <div className="pt-4 border-t border-zinc-50 flex items-center gap-2">
                                    <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                                    <span className="text-[9px] font-bold text-zinc-400 uppercase">Produção Verificada</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Footer Section - Simplified */}
                <div className="mt-16 p-10 bg-white border border-zinc-200 rounded-3xl relative overflow-hidden shadow-sm">
                    <div className="relative z-10 flex flex-col md:flex-row justify-between items-center gap-8">
                        <div className="text-center md:text-left">
                            <h4 className="text-2xl font-bold text-zinc-900 mb-3">Qualidade Confeções Lança</h4>
                            <p className="text-sm text-zinc-500 max-w-2xl leading-relaxed">
                                Estes clientes são a base do nosso padrão de excelência. O sistema de prospecção
                                utiliza estes perfis de sucesso para identificar novos parceiros globais com
                                o mesmo nível de exigência técnica e posicionamento de mercado.
                            </p>
                        </div>
                        <div className="flex flex-col items-center md:items-end gap-1">
                            <span className="text-[10px] font-bold text-zinc-400 uppercase">Última Atualização</span>
                            <span className="text-xl font-bold text-blue-600">Fevereiro 2024</span>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
