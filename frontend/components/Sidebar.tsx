"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
    Search,
    Archive,
    Users,
    Settings,
} from "lucide-react";

const menuItems = [
    { name: "Pesquisa", description: "Encontrar marcas", icon: Search, href: "/" },
    { name: "Cidades Guardadas", description: "Base de dados", icon: Archive, href: "/saved-cities" },
    { name: "Clientes", description: "Rede de parceiros", icon: Users, href: "/clients" },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="w-[72px] lg:w-[260px] bg-[#111111] h-screen flex flex-col sticky top-0 border-r border-white/[0.06] z-50 transition-all duration-300">
            {/* Logo */}
            <div className="py-6 px-4 lg:px-5 flex flex-col justify-center border-b border-white/[0.06]">
                <Link href="/" className="flex flex-col gap-4">
                    <div className="bg-white rounded-md p-2 flex items-center justify-center w-fit shadow-md">
                        <img
                            src="/lanca-logo.png"
                            alt="Confeções Lança"
                            className="h-6 lg:h-12 w-auto object-contain"
                        />
                    </div>
                    <div className="hidden lg:block">
                        <p className="text-[16px] font-bold text-white tracking-tight leading-none">Confeções Lança</p>
                        <p className="text-[9px] font-bold text-[#F5C518] uppercase tracking-[0.1em] mt-2 leading-tight">AI Agent para Pesquisa de Clientes</p>
                    </div>
                </Link>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-3 py-4 space-y-0.5">
                <p className="hidden lg:block px-3 mb-3 text-[9px] font-semibold text-white/25 uppercase tracking-[0.1em]">
                    Navegação
                </p>
                {menuItems.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-md transition-all duration-150 group ${
                                isActive
                                    ? "bg-white/[0.08] text-white"
                                    : "text-white/40 hover:text-white/80 hover:bg-white/[0.04]"
                            }`}
                        >
                            {isActive && (
                                <div className="absolute left-3 w-[2px] h-4 bg-[#F5C518] rounded-full" />
                            )}
                            <item.icon
                                className={`h-[17px] w-[17px] flex-shrink-0 transition-colors ${
                                    isActive ? "text-[#F5C518]" : ""
                                }`}
                            />
                            <div className="hidden lg:block min-w-0">
                                <span className="text-[13px] font-medium block leading-tight">{item.name}</span>
                                <span className="text-[10px] text-white/25 block leading-tight mt-0.5">{item.description}</span>
                            </div>
                        </Link>
                    );
                })}
            </nav>

            {/* Bottom */}
            <div className="px-3 py-4 border-t border-white/[0.06]">
                <Link
                    href="#"
                    className="flex items-center gap-3 px-3 py-2.5 rounded-md text-white/30 hover:text-white/60 hover:bg-white/[0.04] transition-all duration-150"
                >
                    <Settings className="h-[17px] w-[17px] flex-shrink-0" />
                    <span className="hidden lg:block text-[13px]">Definições</span>
                </Link>
            </div>
        </aside>
    );
}
