"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signIn, signOut, useSession } from "next-auth/react";
import {
    Search,
    Archive,
    Users,
    LogOut,
    LogIn,
    Bot,
    Globe,
    Building2,
    Loader2,
} from "lucide-react";

const menuItems = [
    { name: "Pesquisa", description: "Encontrar marcas", icon: Search, href: "/" },
    { name: "Cidades guardadas", description: "Base de dados", icon: Archive, href: "/saved-cities" },
    { name: "Clientes", description: "Rede de parceiros", icon: Users, href: "/clients" },
    { name: "Consultor IA", description: "Analisar dados", icon: Bot, href: "/chat" },
];

export function Sidebar() {
    const pathname = usePathname();
    const { data: session, status } = useSession();

    // No chrome on auth screens (login is full-screen).
    if (pathname?.startsWith("/auth")) {
        return null;
    }

    const user = session?.user as
        | { name?: string | null; email?: string | null; role?: string; region?: string }
        | undefined;
    const isExternal = user?.role === "external_agent";
    const displayName = user?.name || user?.email || "Utilizador";
    const initials = displayName
        .split(/\s+/)
        .map((p) => p[0])
        .filter(Boolean)
        .slice(0, 2)
        .join("")
        .toUpperCase();

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

            {/* Bottom — account */}
            <div className="px-3 py-4 border-t border-white/[0.06] flex flex-col gap-2">
                {status === "loading" ? (
                    <div className="flex items-center gap-3 px-3 py-2.5 text-white/40">
                        <Loader2 className="h-[17px] w-[17px] flex-shrink-0 animate-spin" />
                        <span className="hidden lg:block text-[13px]">A carregar…</span>
                    </div>
                ) : session ? (
                    <>
                        {/* User card */}
                        <div className="flex items-center gap-3 px-2 py-2 rounded-md bg-white/[0.04]">
                            <div
                                className={`h-8 w-8 flex-shrink-0 rounded-full flex items-center justify-center text-[11px] font-bold ${
                                    isExternal
                                        ? "bg-[#0A66C2]/20 text-[#7ab6ff]"
                                        : "bg-[#F5C518]/20 text-[#F5C518]"
                                }`}
                                title={displayName}
                            >
                                {initials || "U"}
                            </div>
                            <div className="hidden lg:block min-w-0">
                                <p className="text-[12px] font-medium text-white/90 truncate leading-tight">
                                    {displayName}
                                </p>
                                <span className="flex items-center gap-1 text-[10px] text-white/40 mt-0.5">
                                    {isExternal ? (
                                        <>
                                            <Globe className="h-3 w-3" />
                                            Agente externo{user?.region ? ` · ${user.region}` : ""}
                                        </>
                                    ) : (
                                        <>
                                            <Building2 className="h-3 w-3" />
                                            Equipa Lança
                                        </>
                                    )}
                                </span>
                            </div>
                        </div>
                        <button
                            onClick={() => signOut({ callbackUrl: "/auth/signin" })}
                            className="flex items-center gap-3 px-3 py-2.5 rounded-md text-red-500/50 hover:text-red-500 hover:bg-red-500/10 transition-all duration-150"
                        >
                            <LogOut className="h-[17px] w-[17px] flex-shrink-0" />
                            <span className="hidden lg:block text-[13px]">Terminar sessão</span>
                        </button>
                    </>
                ) : (
                    <button
                        onClick={() => signIn(undefined, { callbackUrl: "/" })}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-md text-white/70 hover:text-white hover:bg-white/[0.06] transition-all duration-150"
                    >
                        <LogIn className="h-[17px] w-[17px] flex-shrink-0" />
                        <span className="hidden lg:block text-[13px]">Iniciar sessão</span>
                    </button>
                )}
            </div>
        </aside>
    );
}
