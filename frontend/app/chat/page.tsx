"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2, Info } from "lucide-react";
import { toast } from "sonner";

interface Message {
    role: "user" | "assistant";
    content: string;
}

export default function ChatDashboard() {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: "assistant",
            content: "Olá! Sou o teu Consultor IA. Podes perguntar-me sobre as marcas guardadas na base de dados (Ex: 'Quais são as boutiques mais adequadas em Londres?' ou 'Mostra as marcas com preços mais baixos')."
        }
    ]);
    const [input, setInput] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const [city, setCity] = useState("Todas");

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isTyping]);

    const handleSend = async () => {
        if (!input.trim()) return;

        const userMsg = input.trim();
        setInput("");
        setMessages(prev => [...prev, { role: "user", content: userMsg }]);
        setIsTyping(true);

        try {
            const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            
            // Format history for API (excluding the first welcome msg if we want)
            const history = messages.map(m => ({ role: m.role, content: m.content }));

            const response = await fetch(`${API_URL}/api/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: userMsg,
                    city: city,
                    history: history
                })
            });

            if (!response.ok) {
                throw new Error("Falha na comunicação com a IA");
            }

            const data = await response.json();
            setMessages(prev => [...prev, { role: "assistant", content: data.response }]);
            
        } catch (error) {
            console.error("Chat Error:", error);
            toast.error("Ocorreu um erro a processar a resposta da IA. Tenta novamente.");
            setMessages(prev => [...prev, { role: "assistant", content: "⚠️ Desculpa, tive um erro de ligação ao cérebro. Podes reformular ou tentar daqui a pouco?" }]);
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

    return (
        <div className="min-h-screen bg-[#FAFAFA] flex flex-col relative w-full h-screen overflow-hidden">
            {/* Minimal Header */}
            <div className="bg-white border-b border-black/[0.04] px-8 py-5 flex items-center justify-between z-10 shadow-sm">
                <div>
                    <h1 className="text-[22px] font-serif font-medium text-[#111] tracking-tight">
                        Consultor IA
                    </h1>
                    <p className="text-[14px] text-gray-500 mt-0.5">Analista de mercado B2B integrado com a base de dados Lança.</p>
                </div>
                
                <div className="flex items-center gap-3">
                    <span className="text-[12px] text-gray-400 font-medium uppercase tracking-wider">Contexto de Análise:</span>
                    <select 
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                        className="bg-gray-50 border border-gray-200 text-sm rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-yellow-500 transition-shadow outline-none"
                    >
                        <option value="Todas">Global (Todas as Cidades)</option>
                        <option value="Londres">Londres</option>
                        <option value="New York">New York</option>
                        <option value="Washington">Washington</option>
                        <option value="Paris">Paris</option>
                    </select>
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto px-4 py-8 lg:px-24">
                <div className="max-w-4xl mx-auto space-y-6">
                    {messages.map((msg, idx) => (
                        <div key={idx} className={`flex gap-4 ${msg.role === "assistant" ? "flex-row" : "flex-row-reverse"}`}>
                            {/* Avatar */}
                            <div className="flex-shrink-0 mt-1">
                                {msg.role === "assistant" ? (
                                    <div className="w-8 h-8 rounded-full bg-[#111] text-[#F5C518] flex items-center justify-center shadow-lg">
                                        <Bot size={16} />
                                    </div>
                                ) : (
                                    <div className="w-8 h-8 rounded-full bg-gray-200 text-gray-500 flex items-center justify-center">
                                        <User size={16} />
                                    </div>
                                )}
                            </div>
                            
                            {/* Bubble */}
                            <div className={`max-w-[80%] rounded-2xl px-5 py-3.5 text-[15px] leading-relaxed shadow-sm
                                ${msg.role === "assistant" 
                                    ? "bg-white border border-gray-100 text-gray-800" 
                                    : "bg-[#111] text-white"}`
                            }>
                                {msg.content.split('\n').map((line, i) => (
                                    <span key={i}>
                                        {line}
                                        <br/>
                                    </span>
                                ))}
                            </div>
                        </div>
                    ))}

                    {isTyping && (
                        <div className="flex gap-4">
                            <div className="w-8 h-8 rounded-full bg-[#111] text-[#F5C518] flex items-center justify-center shadow-lg">
                                <Bot size={16} />
                            </div>
                            <div className="bg-white border border-gray-100 rounded-2xl px-5 py-4 flex items-center gap-2 shadow-sm">
                                <Loader2 size={16} className="text-gray-400 animate-spin" />
                                <span className="text-[13px] text-gray-400">A analisar base de dados...</span>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Input Box */}
            <div className="p-4 bg-white border-t border-black/[0.04]">
                <div className="max-w-4xl mx-auto relative flex items-center">
                    <textarea 
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Pergunta à IA sobre as marcas extraídas..."
                        className="w-full bg-gray-50 border border-gray-200 rounded-xl pl-5 pr-14 py-4 text-[15px] resize-none outline-none focus:border-gray-300 focus:bg-white transition-all shadow-inner"
                        rows={1}
                        style={{ minHeight: "56px", maxHeight: "150px" }}
                    />
                    <button 
                        onClick={handleSend}
                        disabled={!input.trim() || isTyping}
                        className="absolute right-2 p-2.5 bg-[#111] text-white rounded-lg hover:bg-black disabled:opacity-50 disabled:bg-gray-300 transition-colors"
                    >
                        <Send size={18} />
                    </button>
                </div>
                <div className="max-w-4xl mx-auto text-center mt-3">
                    <p className="text-[11px] text-gray-400 flex items-center justify-center gap-1.5">
                        <Info size={12} />
                        Consultor IA pode cometer erros. Verifica sempre os dados na página de "Cidades Guardadas".
                    </p>
                </div>
            </div>
        </div>
    );
}
