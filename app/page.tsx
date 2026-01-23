"use client";

import { useState } from "react";
import { BrandLead } from "@/lib/types";
import { BrandCard } from "@/components/BrandCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, Sparkles, Globe2, Target, Users, ArrowRight, MapPin } from "lucide-react";

export default function Home() {
  const [city, setCity] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [verifiedBrands, setVerifiedBrands] = useState<BrandLead[]>([]);
  const [exchangeRate, setExchangeRate] = useState<number>(1.08);
  
  const handleSearch = async () => {
    if (!city.trim()) {
      alert("Please enter a city name");
      return;
    }
    
    setIsSearching(true);
    setVerifiedBrands([]);
    
    try {
      const response = await fetch("http://127.0.0.1:8000/api/prospect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city: city.trim() }),
      });
      
      if (!response.ok) {
        throw new Error("Failed to start search");
      }
      
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      
      if (!reader) {
        throw new Error("No response stream");
      }
      
      let buffer = "";
      
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          console.log("[SSE] Stream ended");
          break;
        }
        
        buffer += decoder.decode(value, { stream: true });
        const messages = buffer.split("\n\n");
        buffer = messages.pop() || "";
        
        for (const message of messages) {
          if (message.startsWith("data: ")) {
            try {
              const jsonStr = message.slice(6);
              const data = JSON.parse(jsonStr);
              console.log("[SSE] Received event:", data.type);
              
              if (data.type === "complete") {
                console.log("[SSE] Complete! Brands:", data.verifiedBrands?.length);
                setVerifiedBrands(data.verifiedBrands || []);
                setExchangeRate(data.exchangeRate || 1.08);
              } else if (data.type === "error") {
                console.error("[SSE] Error from server:", data.message);
              } else if (data.type === "progress") {
                console.log("[SSE] Progress:", data.message);
              }
            } catch (parseError) {
              console.warn("[SSE] Failed to parse:", message.slice(0, 200));
            }
          }
        }
      }
      
      if (buffer.startsWith("data: ")) {
        try {
          const data = JSON.parse(buffer.slice(6));
          if (data.type === "complete") {
            console.log("[SSE] Final complete event! Brands:", data.verifiedBrands?.length);
            setVerifiedBrands(data.verifiedBrands || []);
            setExchangeRate(data.exchangeRate || 1.08);
          }
        } catch {
          console.warn("[SSE] Could not parse final buffer");
        }
      }
    } catch (error) {
      console.error("Search error:", error);
    } finally {
      setIsSearching(false);
    }
  };
  
  const handleSendEmail = async (brand: BrandLead) => {
    try {
      const response = await fetch("http://127.0.0.1:8000/api/approve-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          brandName: brand.name,
          brandData: brand,
        }),
      });
      
      const result = await response.json();
      
      if (!response.ok) {
        throw new Error(result.error || "Failed to send email");
      }
    } catch (error) {
      console.error("Email error:", error);
      throw error;
    }
  };

  const suggestedCities = ["Boston", "Austin", "Portland", "Charleston", "San Francisco"];
  
  return (
    <div className="min-h-screen bg-gradient-warm">
      {/* Subtle background pattern */}
      <div className="fixed inset-0 pattern-dots pointer-events-none" />
      
      {/* Header */}
      <header className="relative border-b border-lanca-black/5 bg-white/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex items-center justify-between h-20">
            {/* Logo */}
            <div className="flex items-center gap-4">
              <img 
                src="/lanca-logo.png" 
                alt="Confeções Lança" 
                className="h-12 w-auto object-contain"
              />
              <div className="hidden md:block h-8 w-px bg-lanca-black/10" />
              <span className="hidden md:block text-sm text-lanca-warmGray font-medium">
                Lead Generation
              </span>
            </div>
            
            {/* Status Badge */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-4 py-2 bg-lanca-black rounded-full">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-lanca-yellow opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-lanca-yellow" />
                </span>
                <span className="text-xs font-medium text-white">AI Active</span>
              </div>
            </div>
          </div>
        </div>
      </header>
      
      <main className="relative">
        {/* Hero Section */}
        <section className="relative pt-16 pb-12 md:pt-24 md:pb-16 overflow-hidden">
          {/* Decorative elements */}
          <div className="absolute top-0 right-0 w-96 h-96 bg-lanca-yellow/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-lanca-yellow/10 rounded-full blur-3xl translate-y-1/2 -translate-x-1/2" />
          
          <div className="max-w-6xl mx-auto px-6 relative">
            <div className="max-w-3xl">
              {/* Badge */}
              <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-lanca-yellow/10 border border-lanca-yellow/20 rounded-full mb-6 animate-fade-in">
                <Sparkles className="h-3.5 w-3.5 text-lanca-yellow" />
                <span className="text-xs font-medium text-lanca-black">Powered by AI Agents</span>
              </div>
              
              {/* Headline */}
              <h1 className="font-serif text-4xl md:text-5xl lg:text-6xl text-lanca-black leading-[1.1] mb-6 animate-slide-up">
                Discover Premium
                <span className="block text-lanca-yellow">Retail Partners</span>
              </h1>
              
              {/* Subheadline */}
              <p className="text-lg md:text-xl text-lanca-warmGray leading-relaxed mb-10 animate-slide-up stagger-1">
                AI-powered prospecting finds boutique menswear retailers in the US 
                that align with Confeções Lança&apos;s quality standards.
              </p>
              
              {/* Stats Row */}
              <div className="flex flex-wrap gap-8 mb-12 animate-slide-up stagger-2">
                {[
                  { icon: Globe2, label: "Since 1973", value: "50+ anos" },
                  { icon: Users, label: "Artisans", value: "200+" },
                  { icon: Target, label: "Continents", value: "5" },
                ].map((stat, idx) => (
                  <div key={idx} className="flex items-center gap-3">
                    <div className="p-2 bg-lanca-cream rounded-lg">
                      <stat.icon className="h-4 w-4 text-lanca-black" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-lanca-black">{stat.value}</p>
                      <p className="text-xs text-lanca-warmGray">{stat.label}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Search Box */}
            <div className="max-w-2xl animate-slide-up stagger-3">
              <div className="bg-white rounded-2xl shadow-elevated p-2 border border-lanca-black/5">
                <div className="flex gap-2">
                  <div className="flex-1 relative">
                    <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-lanca-warmGray" />
                    <Input
                      type="text"
                      placeholder="Enter a US city (e.g. Boston, Austin, Portland)"
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                      className="h-14 pl-12 pr-4 border-0 bg-transparent text-base placeholder:text-lanca-warmGray/60 focus-visible:ring-0 focus-visible:ring-offset-0"
                      disabled={isSearching}
                    />
                  </div>
                  <Button 
                    onClick={handleSearch} 
                    disabled={isSearching}
                    className="h-14 px-8 bg-lanca-black hover:bg-lanca-charcoal text-white font-medium rounded-xl transition-all duration-300 hover:shadow-lg"
                  >
                    {isSearching ? (
                      <>
                        <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                        Searching...
                      </>
                    ) : (
                      <>
                        <Search className="h-4 w-4 mr-2" />
                        Find Brands
                      </>
                    )}
                  </Button>
                </div>
              </div>
              
              {/* Quick suggestions */}
              {!isSearching && verifiedBrands.length === 0 && (
                <div className="flex items-center gap-3 mt-4 flex-wrap">
                  <span className="text-xs text-lanca-warmGray">Popular:</span>
                  {suggestedCities.map((suggestedCity) => (
                    <button
                      key={suggestedCity}
                      onClick={() => setCity(suggestedCity)}
                      className="text-xs px-3 py-1.5 bg-white hover:bg-lanca-cream text-lanca-black rounded-full transition-colors border border-lanca-black/10 hover:border-lanca-yellow/50"
                    >
                      {suggestedCity}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
        
        {/* Results Section */}
        <section className="py-12 md:py-16">
          <div className="max-w-6xl mx-auto px-6">
            {/* Loading State */}
            {isSearching && (
              <div className="animate-fade-in">
                <div className="rounded-3xl overflow-hidden shadow-elevated">
                  {/* Top Section - Connection Visualization */}
                  <div className="relative bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 pt-16 pb-20 px-6">
                    {/* Animated gradient orbs */}
                    <div className="absolute inset-0 overflow-hidden">
                      <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-lanca-yellow/10 rounded-full blur-3xl animate-pulse" />
                      <div className="absolute bottom-1/4 right-1/4 w-48 h-48 bg-red-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
                    </div>
                    
                    {/* Grid lines */}
                    <div className="absolute inset-0 opacity-[0.03]">
                      <div className="absolute inset-0" style={{
                        backgroundImage: `linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)`,
                        backgroundSize: '64px 64px'
                      }} />
                    </div>
                    
                    {/* Connection visual */}
                    <div className="relative z-10 flex items-center justify-center gap-4 md:gap-8 lg:gap-12">
                      {/* Portugal */}
                      <div className="flex flex-col items-center group">
                        <div className="relative">
                          {/* Outer glow ring */}
                          <div className="absolute -inset-4 bg-gradient-to-r from-lanca-yellow/20 to-lanca-yellow/5 rounded-full blur-xl animate-pulse" />
                          {/* Decorative ring */}
                          <div className="absolute -inset-2 border border-lanca-yellow/20 rounded-full" />
                          {/* Main circle */}
                          <div className="relative w-24 h-24 md:w-32 md:h-32 bg-gradient-to-br from-lanca-yellow via-amber-400 to-lanca-yellowDark rounded-full flex items-center justify-center shadow-2xl shadow-lanca-yellow/30 group-hover:scale-105 transition-transform duration-500">
                            {/* Inner shadow overlay */}
                            <div className="absolute inset-2 rounded-full bg-gradient-to-b from-white/20 to-transparent" />
                            {/* Text */}
                            <span className="font-serif text-4xl md:text-5xl font-bold text-lanca-black/90 tracking-tight relative">
                              PT
                            </span>
                          </div>
                        </div>
                        <div className="mt-6 text-center">
                          <p className="text-lanca-yellow font-semibold text-lg tracking-wide">Covilhã</p>
                          <p className="text-slate-500 text-xs tracking-widest uppercase">Portugal</p>
                        </div>
                      </div>
                      
                      {/* Connection line */}
                      <div className="flex-1 max-w-[220px] relative py-8">
                        {/* SVG Path */}
                        <svg className="w-full h-16" viewBox="0 0 220 64" fill="none">
                          {/* Background path */}
                          <path 
                            d="M0 32 Q55 12, 110 32 Q165 52, 220 32" 
                            stroke="rgba(255,255,255,0.08)" 
                            strokeWidth="2" 
                            fill="none"
                          />
                          {/* Animated path */}
                          <path 
                            d="M0 32 Q55 12, 110 32 Q165 52, 220 32" 
                            stroke="url(#connectionGradient)" 
                            strokeWidth="2" 
                            fill="none"
                            strokeDasharray="8 4"
                            className="animate-dash"
                          />
                          <defs>
                            <linearGradient id="connectionGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                              <stop offset="0%" stopColor="#F5C518" />
                              <stop offset="50%" stopColor="#FFFFFF" />
                              <stop offset="100%" stopColor="#DC2626" />
                            </linearGradient>
                          </defs>
                        </svg>
                        
                        {/* Flying icon */}
                        <div className="absolute top-1 left-0 w-full animate-fly-across">
                          <div className="bg-white/10 backdrop-blur-md rounded-full p-2.5 shadow-xl border border-white/10 inline-flex items-center justify-center">
                            <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          </div>
                        </div>
                        
                        {/* Connection dots */}
                        <div className="absolute bottom-1 left-0 w-full flex justify-between px-6">
                          {[...Array(5)].map((_, i) => (
                            <div 
                              key={i} 
                              className="w-1 h-1 rounded-full bg-white/40 animate-pulse"
                              style={{ animationDelay: `${i * 0.2}s` }}
                            />
                          ))}
                        </div>
                      </div>
                      
                      {/* USA */}
                      <div className="flex flex-col items-center group">
                        <div className="relative">
                          {/* Outer glow ring */}
                          <div className="absolute -inset-4 bg-gradient-to-r from-red-500/20 to-red-500/5 rounded-full blur-xl animate-pulse" style={{ animationDelay: '0.5s' }} />
                          {/* Decorative ring */}
                          <div className="absolute -inset-2 border border-red-500/20 rounded-full" />
                          {/* Main circle */}
                          <div className="relative w-24 h-24 md:w-32 md:h-32 bg-gradient-to-br from-red-500 via-red-600 to-red-700 rounded-full flex items-center justify-center shadow-2xl shadow-red-500/30 group-hover:scale-105 transition-transform duration-500">
                            {/* Inner shadow overlay */}
                            <div className="absolute inset-2 rounded-full bg-gradient-to-b from-white/20 to-transparent" />
                            {/* Text */}
                            <span className="font-serif text-4xl md:text-5xl font-bold text-white/95 tracking-tight relative">
                              US
                            </span>
                          </div>
                        </div>
                        <div className="mt-6 text-center">
                          <p className="text-red-400 font-semibold text-lg tracking-wide">{city || "USA"}</p>
                          <p className="text-slate-500 text-xs tracking-widest uppercase">Estados Unidos</p>
                        </div>
                      </div>
                    </div>
                    
                    {/* Title */}
                    <div className="relative z-10 text-center mt-12">
                      <h3 className="text-2xl md:text-3xl font-serif text-white mb-2">
                        A procurar clientes em <span className="text-lanca-yellow">{city}</span>
                      </h3>
                      <p className="text-slate-500 text-sm">
                        Confeções Lança • Prospeção internacional
                      </p>
                    </div>
                  </div>
                  
                  {/* Bottom Section - Progress Steps */}
                  <div className="bg-white p-8 md:p-10">
                    <div className="max-w-xl mx-auto">
                      {/* Steps */}
                      <div className="space-y-4">
                        {[
                          { 
                            icon: Search, 
                            text: "Pesquisando lojas de vestuário premium...", 
                            color: "from-amber-500 to-orange-500",
                            bgColor: "bg-amber-50",
                            borderColor: "border-amber-200"
                          },
                          { 
                            icon: Globe2, 
                            text: "Analisando websites e catálogos...", 
                            color: "from-blue-500 to-cyan-500",
                            bgColor: "bg-blue-50",
                            borderColor: "border-blue-200"
                          },
                          { 
                            icon: Target, 
                            text: "Filtrando por critérios de qualidade...", 
                            color: "from-emerald-500 to-green-500",
                            bgColor: "bg-emerald-50",
                            borderColor: "border-emerald-200"
                          },
                          { 
                            icon: Sparkles, 
                            text: "Selecionando melhores candidatos...", 
                            color: "from-violet-500 to-purple-500",
                            bgColor: "bg-violet-50",
                            borderColor: "border-violet-200"
                          },
                        ].map((step, idx) => (
                          <div 
                            key={idx}
                            className={`flex items-center gap-4 p-4 rounded-2xl border ${step.bgColor} ${step.borderColor} animate-fade-in-up`}
                            style={{ animationDelay: `${idx * 0.1}s` }}
                          >
                            {/* Icon with gradient background */}
                            <div className={`p-2.5 rounded-xl bg-gradient-to-br ${step.color} shadow-lg`}>
                              <step.icon className="h-5 w-5 text-white" />
                            </div>
                            
                            {/* Text */}
                            <span className="text-sm text-slate-700 font-medium flex-1">{step.text}</span>
                            
                            {/* Animated indicator */}
                            <div className="flex items-center gap-1">
                              {[...Array(3)].map((_, i) => (
                                <div 
                                  key={i}
                                  className={`w-1.5 h-1.5 rounded-full bg-gradient-to-r ${step.color} animate-bounce`}
                                  style={{ animationDelay: `${i * 0.15}s` }}
                                />
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                      
                      {/* Progress bar */}
                      <div className="mt-8">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-xs font-medium text-slate-500">Progresso</span>
                          <span className="text-xs text-slate-400">~30-60 segundos</span>
                        </div>
                        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-lanca-yellow via-amber-400 to-lanca-yellowDark rounded-full animate-progress shadow-sm" />
                        </div>
                        <p className="text-xs text-slate-400 mt-3 text-center">
                          A nossa IA está a encontrar as melhores oportunidades para si
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            {/* Empty State */}
            {verifiedBrands.length === 0 && !isSearching && (
              <div className="animate-fade-in">
                <div className="bg-white rounded-3xl shadow-soft border border-lanca-black/5 p-12 md:p-16 text-center">
                  <div className="max-w-md mx-auto">
                    <div className="w-20 h-20 bg-lanca-cream rounded-2xl flex items-center justify-center mx-auto mb-6">
                      <Search className="h-10 w-10 text-lanca-warmGray" />
                    </div>
                    <h3 className="font-serif text-2xl md:text-3xl text-lanca-black mb-4">
                      Ready to Discover
                    </h3>
                    <p className="text-lanca-warmGray leading-relaxed mb-8">
                      Enter a US city above to find boutique menswear retailers 
                      that match Confeções Lança&apos;s premium quality standards.
                    </p>
                    <div className="flex justify-center gap-3">
                      <div className="px-4 py-2 bg-lanca-yellow/10 rounded-full border border-lanca-yellow/20">
                        <span className="text-xs font-medium text-lanca-black">Premium Quality</span>
                      </div>
                      <div className="px-4 py-2 bg-lanca-cream rounded-full border border-lanca-black/5">
                        <span className="text-xs font-medium text-lanca-black">Boutique Scale</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            {/* Results */}
            {verifiedBrands.length > 0 && (
              <div className="animate-fade-in">
                {/* Results Header */}
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-1.5 h-1.5 bg-lanca-yellow rounded-full" />
                      <span className="text-xs font-medium text-lanca-warmGray uppercase tracking-wider">
                        Search Results
                      </span>
                    </div>
                    <h2 className="font-serif text-3xl md:text-4xl text-lanca-black">
                      {verifiedBrands.length} Qualified Brands
                    </h2>
                    <p className="text-lanca-warmGray mt-1">
                      Verified boutique retailers ready for partnership outreach
                    </p>
                  </div>
                  
                  <div className="flex items-center gap-2 text-sm text-lanca-warmGray">
                    <MapPin className="h-4 w-4" />
                    <span>Results for <strong className="text-lanca-black">{city}</strong></span>
                  </div>
                </div>
                
                {/* Brand Cards Grid */}
                <div className="space-y-6">
                  {verifiedBrands.map((brand, idx) => (
                    <div 
                      key={idx} 
                      className="animate-slide-up"
                      style={{ animationDelay: `${idx * 0.08}s` }}
                    >
                      <BrandCard 
                        brand={brand} 
                        onSendEmail={handleSendEmail}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
      
      {/* Footer */}
      <footer className="relative bg-lanca-black text-white mt-20">
        <div className="absolute inset-0 pattern-dots opacity-5" />
        
        <div className="max-w-6xl mx-auto px-6 py-16 relative">
          <div className="grid md:grid-cols-4 gap-12 mb-12">
            {/* Brand */}
            <div className="md:col-span-2">
              <img 
                src="/lanca-logo.png" 
                alt="Confeções Lança" 
                className="h-10 w-auto object-contain brightness-0 invert mb-4"
              />
              <p className="text-white/60 text-sm leading-relaxed max-w-sm">
                Since 1973, producing superior quality clothing with excellence in 
                Portuguese manufacturing. Serving premium brands across 5 continents.
              </p>
            </div>
            
            {/* Values */}
            <div>
              <h4 className="text-sm font-semibold mb-4 text-lanca-yellow">Our Values</h4>
              <ul className="space-y-2">
                {["Excellence", "Precision", "Rigor", "Consistency"].map((value) => (
                  <li key={value} className="flex items-center gap-2 text-sm text-white/60">
                    <ArrowRight className="h-3 w-3 text-lanca-yellow" />
                    {value}
                  </li>
                ))}
              </ul>
            </div>
            
            {/* Location */}
            <div>
              <h4 className="text-sm font-semibold mb-4 text-lanca-yellow">Location</h4>
              <p className="text-sm text-white/60">
                Covilhã, Portugal
              </p>
              <p className="text-xs text-white/40 mt-1">
                Serving 5 continents worldwide
              </p>
            </div>
          </div>
          
          <div className="border-t border-white/10 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-xs text-white/40">
              © 2024 Confeções Lança • All rights reserved
            </p>
            <div className="flex items-center gap-2 text-xs text-white/40">
              <Sparkles className="h-3 w-3 text-lanca-yellow" />
              <span>Powered by AI</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
