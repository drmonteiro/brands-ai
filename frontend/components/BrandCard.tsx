"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { toast } from "sonner";
import { BrandLead, parseJsonArray } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Globe,
  Mail,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  MapPin,
  Phone,
  RefreshCw,
  Send,
  Store,
  TrendingUp,
  Tag,
  Linkedin,
  Star,
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
} from "lucide-react";
import { FeedbackModal } from "./FeedbackModal";

interface BrandCardProps {
  brand: BrandLead;
  onSendEmail?: (brandName: string, brandData: any) => Promise<boolean>;
}

export function BrandCard({ brand, onSendEmail }: BrandCardProps) {
  const { data: session } = useSession();
  const [isExpanded, setIsExpanded] = useState(false);
  const [currentStatus, setCurrentStatus] = useState(brand.status || "new");
  const [emailStatus, setEmailStatus] = useState<"idle" | "sending" | "sent">("idle");
  const [feedbackState, setFeedbackState] = useState<{
    showModal: boolean;
    type: "up" | "down" | null;
    status: "idle" | "success";
  }>({
    showModal: false,
    type: null,
    status: "idle",
  });

  const handleFeedbackSubmit = async (comment: string) => {
    if (!feedbackState.type) return;

    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${API_URL}/api/prospects/${brand.id}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feedback_type: feedbackState.type,
          comment,
          manager_name: session?.user?.name || "Comercial", // Dynamic from NextAuth
        }),
      });

      if (response.ok) {
        setFeedbackState(prev => ({ ...prev, status: "success", showModal: false }));
        // Close modal is handled by the component's onClose calling setIsOpen(false) 
        // but we manage it here since we are calling setIsSubmitting(false) inside onSubmit
      }
    } catch (error) {
      console.error("Error submitting feedback:", error);
    }
  };

  const handleSendEmail = async () => {
    setEmailStatus("sending");
    if (onSendEmail) {
      const success = await onSendEmail(brand.name, brand);
      if (success) {
        setEmailStatus("sent");
        if (currentStatus === "new") {
          setCurrentStatus("contacted");
        }
        return;
      }
    }
    setEmailStatus("idle");
  };

  const handleStatusChange = async (newStatus: string) => {
    const previousStatus = currentStatus;
    setCurrentStatus(newStatus);
    
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${API_URL}/api/prospects/${brand.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      
      if (!response.ok) throw new Error("Failed to update status");
      toast.success(`Estado atualizado para ${newStatus}`);
    } catch (error) {
      setCurrentStatus(previousStatus);
      toast.error("Erro ao atualizar estado da marca");
    }
  };

  // Support both snake_case (API) and camelCase (legacy) field names
  const websiteUrl = brand.website_url || brand.websiteUrl || "";
  const storeCount = brand.store_count ?? brand.storeCount ?? 0;
  const priceEUR = brand.avg_suit_price_eur ?? brand.avgSuitPriceEUR;
  const priceUSD = brand.averageSuitPriceUSD;
  const city = brand.city || "";
  const country = brand.country || brand.originCountry || "";
  const description = brand.detailed_description || brand.detailedDescription || brand.company_overview || brand.companyOverview || "";
  const fitScore = brand.fit_score ?? brand.fitScore ?? 0;
  const finalScore = brand.final_score ?? 0;
  const contactName = brand.contact_name || brand.contactName || "";
  const contactRole = brand.contact_role || brand.contactRole || "";
  const contactEmail = brand.contact_email || brand.contactEmail || "";
  const contactPhone = brand.contact_phone || brand.contactPhone || "";
  const contactLinkedin = brand.contact_linkedin || brand.contactLinkedin || "";
  const brandStyle = brand.brand_style || "";
  const businessModel = brand.business_model || "";
  const mostSimilarClient = brand.most_similar_client || "";
  const similarityExplanation = brand.similarity_explanation || "";
  const storeLocations = parseJsonArray(brand.store_locations || brand.storeLocations);
  const materialComposition = parseJsonArray(brand.material_composition);
  const madeToMeasure = brand.made_to_measure ?? false;

  // Determine fit level from fit_score
  const getFitLevel = () => {
    if (brand.fitForLanca) return brand.fitForLanca;
    if (fitScore >= 8) return 'high';
    if (fitScore >= 5) return 'medium';
    return 'low';
  };
  const fitLevel = getFitLevel();

  const fitColor = fitLevel === 'high' 
    ? 'status-high' 
    : fitLevel === 'medium' 
    ? 'status-medium' 
    : 'status-low';

  const fitLabel = fitLevel === 'high' 
    ? 'Alto' 
    : fitLevel === 'medium' 
    ? 'Médio' 
    : 'Baixo';

  // Format price
  const formatPrice = () => {
    if (priceEUR && priceEUR > 0) return `${Math.round(priceEUR)}€`;
    if (priceUSD && priceUSD > 0) return `${Math.round(priceUSD)}$`;
    return "N/A";
  };

  return (
    <div className="card-lanca overflow-hidden">
      <div className="p-5 lg:p-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-lg font-semibold text-foreground truncate">
                {brand.name}
              </h3>
              {brand.verified && (
                <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0" title="Verificado pela IA" />
              )}
            </div>
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <MapPin className="h-3.5 w-3.5" />
              <span className="text-sm">{city || "N/A"}, {country}</span>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <select 
              value={currentStatus}
              onChange={(e) => handleStatusChange(e.target.value)}
              className="text-xs font-medium rounded-md px-2 py-1 bg-muted border border-border outline-none text-foreground focus:ring-2 focus:ring-lanca-yellow"
            >
              <option value="new">Novo</option>
              <option value="contacted">Contactado</option>
              <option value="converted">Convertido</option>
              <option value="rejected">Rejeitado</option>
            </select>
            
            {/* Feedback Mini-buttons */}
            <div className="flex gap-1">
              <button 
                onClick={() => setFeedbackState({ showModal: true, type: "up", status: "idle" })}
                className={`p-1.5 rounded-md transition-all hover:scale-110 ${
                  feedbackState.status === "success" && feedbackState.type === "up"
                  ? "bg-emerald-100 text-emerald-600 scale-105"
                  : "bg-muted/30 text-muted-foreground/60 hover:text-emerald-500 hover:bg-emerald-50"
                 }`}
                title="Gostei desta marca"
              >
                <ThumbsUp className="h-4 w-4" />
              </button>
              <button 
                onClick={() => setFeedbackState({ showModal: true, type: "down", status: "idle" })}
                className={`p-1.5 rounded-md transition-all hover:scale-110 ${
                   feedbackState.status === "success" && feedbackState.type === "down"
                   ? "bg-rose-100 text-rose-600 scale-105"
                   : "bg-muted/30 text-muted-foreground/60 hover:text-rose-500 hover:bg-rose-50"
                 }`}
                title="Esta marca não serve"
              >
                <ThumbsDown className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="bg-muted/50 rounded-lg p-3 text-center">
            <Store className="h-3.5 w-3.5 text-muted-foreground mx-auto mb-1" />
            <p className="text-xs text-muted-foreground mb-0.5">Lojas</p>
            <p className="text-sm font-semibold text-foreground">{storeCount}</p>
          </div>
          <div className="bg-muted/50 rounded-lg p-3 text-center">
            <Tag className="h-3.5 w-3.5 text-muted-foreground mx-auto mb-1" />
            <p className="text-xs text-muted-foreground mb-0.5">Preço</p>
            <p className="text-sm font-semibold text-foreground">{formatPrice()}</p>
          </div>
          <div className="bg-muted/50 rounded-lg p-3 text-center">
            <TrendingUp className="h-3.5 w-3.5 text-muted-foreground mx-auto mb-1" />
            <p className="text-xs text-muted-foreground mb-0.5">Score</p>
            <p className="text-sm font-semibold text-foreground">{finalScore || fitScore}/10</p>
          </div>
        </div>

        {/* Brand Style Tag */}
        {brandStyle && (
          <div className="flex items-center gap-2 mb-3">
            <div className="w-1.5 h-1.5 rounded-full bg-lanca-yellow flex-shrink-0" />
            <p className="text-xs text-muted-foreground line-clamp-1">{brandStyle}</p>
          </div>
        )}

        {/* Description */}
        <p className={`text-sm text-muted-foreground leading-relaxed mb-4 ${!isExpanded ? 'line-clamp-2' : ''}`}>
          {description || "Sem descrição disponível."}
        </p>

        {/* Made to Measure badge */}
        {madeToMeasure && (
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-lanca-yellowLight border border-lanca-yellow/15 rounded-md mb-4">
            <Star className="h-3 w-3 text-lanca-yellowDark" />
            <span className="text-xs font-medium text-lanca-yellowDark">Made to Measure</span>
          </div>
        )}

        {/* Expanded Content */}
        {isExpanded && (
          <div className="space-y-4 mb-4 pt-4 border-t border-border animate-fade-in">
            {/* Contact Info */}
            {(contactName || contactEmail || contactPhone || contactLinkedin) && (
              <div className="bg-lanca-yellowLight/50 rounded-lg p-4 border border-lanca-yellow/10">
                <p className="text-xs font-semibold text-foreground mb-3 uppercase tracking-wide">Contacto</p>
                <div className="space-y-2">
                  {contactName && (
                    <p className="text-sm text-foreground">
                      <span className="font-medium">{contactName}</span>
                      {contactRole && <span className="text-muted-foreground"> · {contactRole}</span>}
                    </p>
                  )}
                  {contactEmail && (
                    <a href={`mailto:${contactEmail}`} className="flex items-center gap-2 text-sm text-lanca-yellowDark hover:underline">
                      <Mail className="h-3.5 w-3.5" />
                      {contactEmail}
                    </a>
                  )}
                  {contactPhone && (
                    <a href={`tel:${contactPhone}`} className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
                      <Phone className="h-3.5 w-3.5" />
                      {contactPhone}
                    </a>
                  )}
                  {contactLinkedin && (
                    <a href={contactLinkedin} target="_blank" rel="noopener" className="flex items-center gap-2 text-sm text-blue-600 hover:underline">
                      <Linkedin className="h-3.5 w-3.5" />
                      LinkedIn
                    </a>
                  )}
                </div>
              </div>
            )}

            {/* Most Similar Client */}
            {mostSimilarClient && (
              <div>
                <p className="text-xs font-semibold text-foreground mb-2 uppercase tracking-wide">Cliente Mais Semelhante</p>
                <div className="bg-muted/50 rounded-lg p-3">
                  <p className="text-sm font-medium text-foreground mb-1">{mostSimilarClient}</p>
                  {similarityExplanation && (
                    <p className="text-xs text-muted-foreground leading-relaxed">{similarityExplanation}</p>
                  )}
                </div>
              </div>
            )}

            {/* Business Model */}
            {businessModel && (
              <div>
                <p className="text-xs font-semibold text-foreground mb-2 uppercase tracking-wide">Modelo de Negócio</p>
                <p className="text-sm text-muted-foreground leading-relaxed">{businessModel}</p>
              </div>
            )}

            {/* Store Locations */}
            {storeLocations.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-foreground mb-2 uppercase tracking-wide">Localizações</p>
                <div className="flex flex-wrap gap-1.5">
                  {storeLocations.map((loc, i) => (
                    <span key={i} className="px-2.5 py-1 bg-muted text-xs text-muted-foreground rounded-md border border-border flex items-center gap-1.5">
                      <div className="h-1.5 w-1.5 bg-emerald-400 rounded-full" />
                      {loc}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Material Composition */}
            {materialComposition.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-foreground mb-2 uppercase tracking-wide">Materiais</p>
                <div className="space-y-1">
                  {materialComposition.map((mat, i) => (
                    <p key={i} className="text-sm text-muted-foreground leading-relaxed">{mat}</p>
                  ))}
                </div>
              </div>
            )}

            {/* Feedback History */}
            {brand.feedback_history && brand.feedback_history.length > 0 && (
              <div className="pt-4 border-t border-border/50">
                <p className="text-xs font-semibold text-foreground mb-3 uppercase tracking-wide flex items-center gap-2">
                  <MessageSquare className="h-3.5 w-3.5 text-lanca-yellowDark" />
                  Histórico de Feedback
                </p>
                <div className="space-y-3">
                  {brand.feedback_history.map((fb, idx) => (
                    <div key={idx} className="bg-muted/30 rounded-xl p-3 border border-border/50">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <div className={`p-1 rounded-md ${fb.feedback_type === 'up' ? 'bg-emerald-100 text-emerald-600' : 'bg-rose-100 text-rose-600'}`}>
                            {fb.feedback_type === 'up' ? <ThumbsUp className="h-3 w-3" /> : <ThumbsDown className="h-3 w-3" />}
                          </div>
                          <span className="text-xs font-medium text-foreground">{fb.manager_name}</span>
                        </div>
                        <span className="text-[10px] text-muted-foreground">
                          {new Date(fb.created_at).toLocaleDateString('pt-PT')}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground italic leading-relaxed">
                        "{fb.comment}"
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2 pt-3 border-t border-border">
          <Button
            disabled={emailStatus !== "idle"}
            className={`flex-1 h-10 rounded-lg text-sm font-medium transition-all duration-200 ${
              emailStatus === "sent" 
                ? "bg-emerald-600 text-white" 
                : "bg-lanca-black hover:bg-lanca-charcoal text-white"
            }`}
            onClick={handleSendEmail}
          >
            {emailStatus === "idle" ? (
              <div className="flex items-center gap-2">
                <Send className="h-3.5 w-3.5" />
                <span>Enviar Proposta</span>
              </div>
            ) : emailStatus === "sending" ? (
              <div className="flex items-center gap-2">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                <span>A enviar...</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>Enviado!</span>
              </div>
            )}
          </Button>

          <Button
            variant="outline"
            size="icon"
            className="h-10 w-10 rounded-lg border-border"
            onClick={() => window.open(`https://www.google.com/maps/search/${encodeURIComponent(brand.name + " " + city)}`, '_blank')}
            title="Ver no Maps"
          >
            <MapPin className="h-4 w-4 text-muted-foreground" />
          </Button>

          <Button
            variant="outline"
            size="icon"
            className="h-10 w-10 rounded-lg border-border"
            onClick={() => window.open(websiteUrl, '_blank')}
            title="Abrir website"
          >
            <Globe className="h-4 w-4 text-muted-foreground" />
          </Button>

          <Button
            variant="outline"
            onClick={() => setIsExpanded(!isExpanded)}
            className="h-10 px-3 rounded-lg border-border text-sm gap-1.5"
          >
            {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {isExpanded ? "Menos" : "Mais"}
          </Button>
        </div>
      </div>

      {feedbackState.showModal && (
        <FeedbackModal
          brandName={brand.name}
          feedbackType={feedbackState.type as "up" | "down"}
          onClose={() => setFeedbackState(prev => ({ ...prev, showModal: false }))}
          onSubmit={handleFeedbackSubmit}
        />
      )}
    </div>
  );
}
