"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, Loader2, Info, Sparkles, RotateCcw } from "lucide-react";
import { toast } from "sonner";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Message {
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
}

interface CityOption {
    name: string;
    count: number;
}

const QUICK_PROMPTS = [
    "Quais são as marcas com melhor score para abordar primeiro?",
    "Mostra-me as marcas com preços mais acessíveis (abaixo de 800€).",
    "Quais leads são mais parecidos com os nossos clientes atuais?",
    "Há marcas que funcionam só por marcação? Quais são os riscos?",
    "Faz-me um resumo executivo das oportunidades encontradas.",
    "Quais marcas têm contactos de email disponíveis para cold outreach?",
];

export default function ChatDashboard() {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: "assistant",
            content: "Olá! Sou o **Consultor IA** da Confeções Lança.\n\nTenho acesso direto à base de dados de marcas prospetadas pelo nosso motor de IA. Posso ajudar-te a:\n\n• **Analisar leads** — rankings, comparações, filtros inteligentes\n• **Recomendar prioridades** — quais marcas abordar primeiro e porquê\n• **Preparar abordagens** — contexto sobre cada marca para reuniões\n• **Cruzar dados** — comparar leads com os nossos 18 clientes atuais\n\nEscolhe uma cidade no selector acima ou pergunta sobre todas as cidades. Como posso ajudar?",
            timestamp: new Date(),
        },
    ]);
    const [input, setInput] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const [city, setCity] = useState("Todas");
    const [cities, setCities] = useState<CityOption[]>([]);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Fetch available cities from backend
    useEffect(() => {
        const fetchCities = async () => {
            try {
                const res = await fetch(`${API_URL}/api/chat/cities`);
                if (res.ok) {
                    const data = await res.json();
                    setCities(data.cities || []);
                }
            } catch (e) {
                console.error("Failed to fetch cities:", e);
            }
        };
        fetchCities();
    }, []);

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, isTyping, scrollToBottom]);

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
            textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + "px";
        }
    }, [input]);

    const handleSend = async (overrideMessage?: string) => {
        const userMsg = (overrideMessage || input).trim();
        if (!userMsg) return;

        setInput("");
        const newUserMsg: Message = { role: "user", content: userMsg, timestamp: new Date() };
        setMessages((prev) => [...prev, newUserMsg]);
        setIsTyping(true);

        try {
            // Build history (skip the first welcome message)
            const history = messages.slice(1).map((m) => ({ role: m.role, content: m.content }));

            const response = await fetch(`${API_URL}/api/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: userMsg,
                    city: city === "Todas" ? null : city,
                    history: history,
                }),
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || "Erro de comunicação com o servidor");
            }

            const data = await response.json();
            setMessages((prev) => [
                ...prev,
                { role: "assistant", content: data.response, timestamp: new Date() },
            ]);
        } catch (error: any) {
            console.error("Chat Error:", error);
            toast.error("Erro ao processar a resposta da IA");
            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content: "⚠️ Ocorreu um erro de ligação. Verifica se o backend está ativo e tenta novamente.",
                    timestamp: new Date(),
                },
            ]);
        } finally {
            setIsTyping(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleReset = () => {
        setMessages([
            {
                role: "assistant",
                content: "Conversa reiniciada. Como posso ajudar?",
                timestamp: new Date(),
            },
        ]);
    };

    // Simple markdown-like rendering (bold, bullets, links)
    const renderContent = (text: string) => {
        return text.split("\n").map((line, i) => {
            // Bold: **text**
            let rendered = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            // Bullet points
            if (rendered.trim().startsWith("•") || rendered.trim().startsWith("-")) {
                return (
                    <div key={i} className="flex gap-2 ml-1 my-0.5">
                        <span className="text-[#F5C518] flex-shrink-0 mt-0.5">•</span>
                        <span dangerouslySetInnerHTML={{ __html: rendered.replace(/^[•\-]\s*/, "") }} />
                    </div>
                );
            }
            if (rendered.trim() === "") return <br key={i} />;
            return <p key={i} className="my-0.5" dangerouslySetInnerHTML={{ __html: rendered }} />;
        });
    };

    return (
        <div className="min-h-screen bg-[#FAFAFA] flex flex-col relative w-full h-screen overflow-hidden">
            {/* ═══ HEADER ═══ */}
            <div className="bg-white border-b border-black/[0.06] px-6 lg:px-8 py-4 flex items-center justify-between z-10">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-[#111] flex items-center justify-center shadow-md">
                        <Sparkles size={16} className="text-[#F5C518]" />
                    </div>
                    <div>
                        <h1 className="text-[18px] font-serif font-semibold text-[#111] tracking-tight">
                            Consultor IA
                        </h1>
                        <p className="text-[12px] text-gray-400 mt-0">
                            Analista de mercado B2B · Base de dados Lança
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    {/* City Selector */}
                    <div className="flex items-center gap-2">
                        <span className="text-[11px] text-gray-400 font-medium uppercase tracking-wider hidden lg:block">
                            Contexto:
                        </span>
                        <select
                            value={city}
                            onChange={(e) => setCity(e.target.value)}
                            className="bg-gray-50 border border-gray-200 text-[13px] rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#F5C518]/50 focus:border-[#F5C518]/30 transition-all cursor-pointer"
                        >
                            <option value="Todas">🌍 Global (Todas)</option>
                            {cities.map((c) => (
                                <option key={c.name} value={c.name}>
                                    📍 {c.name} ({c.count} marcas)
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Reset Button */}
                    <button
                        onClick={handleReset}
                        className="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-all"
                        title="Reiniciar conversa"
                    >
                        <RotateCcw size={16} />
                    </button>
                </div>
            </div>

            {/* ═══ CHAT AREA ═══ */}
            <div className="flex-1 overflow-y-auto px-4 py-6 lg:px-16">
                <div className="max-w-3xl mx-auto space-y-5">
                    {messages.map((msg, idx) => (
                        <div
                            key={idx}
                            className={`flex gap-3 ${msg.role === "assistant" ? "flex-row" : "flex-row-reverse"}`}
                        >
                            {/* Avatar */}
                            <div className="flex-shrink-0 mt-1">
                                {msg.role === "assistant" ? (
                                    <div className="w-8 h-8 rounded-lg bg-[#111] text-[#F5C518] flex items-center justify-center shadow-md">
                                        <Bot size={15} />
                                    </div>
                                ) : (
                                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-gray-200 to-gray-300 text-gray-600 flex items-center justify-center">
                                        <User size={15} />
                                    </div>
                                )}
                            </div>

                            {/* Bubble */}
                            <div
                                className={`max-w-[85%] rounded-2xl px-5 py-4 text-[14px] leading-relaxed
                                ${
                                    msg.role === "assistant"
                                        ? "bg-white border border-gray-100 text-gray-700 shadow-sm"
                                        : "bg-[#111] text-white shadow-md"
                                }`}
                            >
                                {msg.role === "assistant" ? renderContent(msg.content) : <p>{msg.content}</p>}
                            </div>
                        </div>
                    ))}

                    {/* Typing Indicator */}
                    {isTyping && (
                        <div className="flex gap-3">
                            <div className="w-8 h-8 rounded-lg bg-[#111] text-[#F5C518] flex items-center justify-center shadow-md">
                                <Bot size={15} />
                            </div>
                            <div className="bg-white border border-gray-100 rounded-2xl px-5 py-4 flex items-center gap-3 shadow-sm">
                                <Loader2 size={15} className="text-[#F5C518] animate-spin" />
                                <span className="text-[13px] text-gray-400">
                                    A consultar a base de dados e a formular resposta...
                                </span>
                            </div>
                        </div>
                    )}

                    {/* Quick Prompts (show only if no user messages yet) */}
                    {messages.length <= 1 && !isTyping && (
                        <div className="pt-4">
                            <p className="text-[11px] text-gray-400 uppercase tracking-wider font-medium mb-3 ml-1">
                                Sugestões rápidas
                            </p>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                {QUICK_PROMPTS.map((prompt, i) => (
                                    <button
                                        key={i}
                                        onClick={() => handleSend(prompt)}
                                        className="text-left text-[13px] text-gray-500 bg-white border border-gray-100 rounded-xl px-4 py-3 hover:border-[#F5C518]/30 hover:bg-[#F5C518]/[0.02] hover:text-gray-700 transition-all shadow-sm"
                                    >
                                        {prompt}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* ═══ INPUT BOX ═══ */}
            <div className="p-4 bg-white border-t border-black/[0.04]">
                <div className="max-w-3xl mx-auto relative flex items-end gap-2">
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Pergunta à IA sobre as marcas prospetadas..."
                        className="flex-1 bg-gray-50 border border-gray-200 rounded-xl pl-5 pr-4 py-3.5 text-[14px] resize-none outline-none focus:border-gray-300 focus:bg-white transition-all"
                        rows={1}
                        style={{ minHeight: "52px", maxHeight: "150px" }}
                    />
                    <button
                        onClick={() => handleSend()}
                        disabled={!input.trim() || isTyping}
                        className="flex-shrink-0 p-3 bg-[#111] text-white rounded-xl hover:bg-black disabled:opacity-30 disabled:bg-gray-300 transition-all shadow-md"
                    >
                        <Send size={17} />
                    </button>
                </div>
                <div className="max-w-3xl mx-auto text-center mt-2.5">
                    <p className="text-[11px] text-gray-400 flex items-center justify-center gap-1.5">
                        <Info size={11} />
                        Powered by GPT-5.1 · Dados extraídos da base de dados Lança ·
                        Verifica sempre na página &quot;Cidades Guardadas&quot;
                    </p>
                </div>
            </div>
        </div>
    );
}
