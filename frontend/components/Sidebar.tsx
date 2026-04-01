"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
    Search,
    Archive,
    Users,
    Settings,
    ChevronRight,
} from "lucide-react";

const menuItems = [
    { name: "Prospeção", description: "Pesquisar marcas", icon: Search, href: "/" },
    { name: "Cidades Guardadas", description: "Base de dados", icon: Archive, href: "/saved-cities" },
    { name: "Clientes", description: "Rede de parceiros", icon: Users, href: "/clients" },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="w-[72px] lg:w-[260px] bg-lanca-black h-screen flex flex-col sticky top-0 overflow-hidden z-50 transition-all duration-300">
            {/* Logo Area */}
            <div className="p-4 lg:p-6 pb-6 border-b border-white/10">
                <Link href="/" className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-lanca-yellow flex items-center justify-center flex-shrink-0 shadow-gold-sm">
                        <Image 
                            src="/lanca-logo.png" 
                            alt="Confeções Lança" 
                            width={28} 
                            height={28}
                            className="object-contain"
                        />
                    </div>
                    <div className="hidden lg:block">
                        <h1 className="text-sm font-bold text-white leading-tight">Confeções Lança</h1>
                        <p className="text-[11px] text-white/40">Desde 1973</p>
                    </div>
                </Link>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-3 lg:p-4 space-y-1">
                <p className="hidden lg:block px-3 mb-3 text-[10px] font-semibold text-white/30 uppercase tracking-wider">
                    Menu
                </p>
                {menuItems.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 group relative ${
                                isActive
                                    ? "bg-white/10 text-white"
                                    : "text-white/50 hover:text-white hover:bg-white/5"
                            }`}
                        >
                            {isActive && (
                                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-lanca-yellow rounded-r-full" />
                            )}
                            <item.icon className={`h-[18px] w-[18px] flex-shrink-0 ${isActive ? "text-lanca-yellow" : ""}`} />
                            <div className="hidden lg:block min-w-0">
                                <span className="text-sm font-medium block leading-tight">{item.name}</span>
                                <span className="text-[11px] text-white/30 block leading-tight">{item.description}</span>
                            </div>
                            {isActive && (
                                <ChevronRight className="h-3.5 w-3.5 text-white/30 ml-auto hidden lg:block" />
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* Bottom Section */}
            <div className="p-3 lg:p-4 border-t border-white/10">
                {/* Quick Stats */}
                <div className="hidden lg:block mb-4 px-3 py-3 bg-white/5 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-medium text-white/40 uppercase tracking-wide">Estado do Sistema</span>
                        <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                    </div>
                    <p className="text-xs text-white/60">Motor IA <span className="text-emerald-400 font-medium">Ativo</span></p>
                </div>

                {/* Settings */}
                <Link
                    href="#"
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-white/40 hover:text-white hover:bg-white/5 transition-all duration-200"
                >
                    <Settings className="h-[18px] w-[18px] flex-shrink-0" />
                    <span className="hidden lg:block text-sm">Definições</span>
                </Link>
            </div>
        </aside>
    );
}
