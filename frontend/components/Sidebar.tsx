"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    BarChart3,
    Search,
    Map,
    Settings,
    LogOut,
    Users,
    Building2,
    FolderOpen
} from "lucide-react";

const menuItems = [
    { name: "Pesquisar", icon: Search, href: "/" },
    { name: "Cidades Guardadas", icon: Map, href: "/saved-cities" },
    { name: "Clientes Lança", icon: Users, href: "/clients" },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="w-64 bg-white text-zinc-900 h-screen flex flex-col sticky top-0 overflow-hidden border-r border-zinc-200 shadow-sm">
            {/* Logo */}
            <div className="p-8">
                <img
                    src="/lanca-logo.png"
                    alt="Confeções Lança"
                    className="h-12 w-auto object-contain opacity-90"
                />
                <div className="mt-3 flex items-center gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-blue-600" />
                    <span className="text-[10px] font-bold text-zinc-400 uppercase">Lança AI • v2.5</span>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-4 py-6 space-y-1">
                {menuItems.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex items-center gap-4 px-4 py-3.5 rounded-xl transition-all group ${isActive
                                ? "bg-blue-50 text-blue-600 font-bold"
                                : "text-zinc-500 hover:text-blue-600 hover:bg-zinc-50"
                                }`}
                        >
                            <item.icon className={`h-5 w-5 ${isActive ? "text-blue-600" : "text-zinc-400 group-hover:text-blue-600"}`} />
                            <span className="text-[11px] font-bold uppercase">{item.name}</span>
                        </Link>
                    );
                })}
            </nav>

            {/* Profile / Stats */}
            <div className="p-6 border-t border-zinc-100">
                <div className="bg-zinc-50 p-4 rounded-2xl border border-zinc-100/50 space-y-3">
                    <div className="flex justify-between items-center text-[10px] font-bold text-blue-600 uppercase">
                        <span>Status</span>
                        <span className="flex items-center gap-1.5">
                            <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                            <span className="text-zinc-600">Conectado</span>
                        </span>
                    </div>
                    <div className="w-full h-1.5 bg-zinc-200 rounded-full overflow-hidden">
                        <div className="w-3/4 h-full bg-blue-600 rounded-full" />
                    </div>
                    <p className="text-[9px] text-zinc-400 font-bold uppercase">Prospecção Diária • 75%</p>
                </div>

                <button className="w-full mt-6 flex items-center justify-between text-zinc-400 hover:text-red-500 transition-colors group px-2">
                    <span className="text-[10px] font-bold uppercase">Sair do Sistema</span>
                    <LogOut className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                </button>
            </div>
        </div>
    );
}
