"use client";

import { memo, useState, useCallback } from "react";
import { toast } from "sonner";
import {
  BrandLead,
  parseJsonArray,
  isHeadquartersInSearchCity,
} from "@/lib/types";
import { apiUrl } from "@/lib/apiBase";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Globe,
  Mail,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
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
  AlertTriangle,
  Building2,
} from "lucide-react";
import { FeedbackModal } from "./FeedbackModal";

interface BrandCardProps {
  brand: BrandLead;
  onSendEmail?: (brandName: string, brandData: any) => Promise<boolean>;
  managerName?: string;
}

export const BrandCard = memo(function BrandCard({ brand, onSendEmail, managerName = "Comercial" }: BrandCardProps) {
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
      const response = await fetch(apiUrl(`/api/prospects/${brand.id}/feedback`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feedback_type: feedbackState.type,
          comment,
          manager_name: managerName,
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
      const response = await fetch(apiUrl(`/api/prospects/${brand.id}/status`), {
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
  const rawCity = brand.city || "";
  const city = rawCity.charAt(0).toUpperCase() + rawCity.slice(1);
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
  const headquartersAddress = brand.headquarters_address || "";
  const headquartersCity = brand.headquarters_city || brand.headquartersCity || "";
  const headquartersConfidence = brand.headquarters_confidence || brand.headquartersConfidence || "unknown";
  const localStoreAddress = brand.local_store_address || brand.localStoreAddress || "";
  const cityPresenceType = brand.city_presence_type || brand.cityPresenceType || "unknown";
  const storeCountConfidence = brand.store_count_confidence || brand.storeCountConfidence || "unknown";

  const hqInSearchCity = isHeadquartersInSearchCity(
    headquartersCity,
    rawCity,
    cityPresenceType
  );
  const isStoreOnlyInSearchCity =
    cityPresenceType === "store" ||
    (cityPresenceType === "showroom" && !hqInSearchCity);

  const presenceBadge: Record<
    string,
    { label: string; className: string }
  > = {
    hq: {
      label: "Sede na cidade",
      className: "bg-emerald-100 text-emerald-800 border-emerald-200",
    },
    store: {
      label: "Só loja na cidade",
      className: "bg-amber-100 text-amber-900 border-amber-200",
    },
    showroom: {
      label: "Showroom",
      className: "bg-amber-50 text-amber-800 border-amber-200",
    },
    unknown: { label: "", className: "" },
  };
  const presence = presenceBadge[cityPresenceType];

  const storeConfidenceLabel: Record<string, { text: string; className: string }> = {
    verified: { text: "confirmado", className: "bg-emerald-100 text-emerald-700" },
    estimated: { text: "estimado", className: "bg-amber-100 text-amber-700" },
    uncertain: { text: "aprox.", className: "bg-muted text-muted-foreground" },
    unknown: { text: "", className: "" },
  };

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

  const priceNote = brand.price_note || (brand as any).priceNote || "";
  const productImages = parseJsonArray(brand.product_images as any);

  // Image carousel state
  const [imgIndex, setImgIndex] = useState(0);
  const [imgErrors, setImgErrors] = useState<Set<number>>(new Set());
  const validImages = productImages.filter((_, i) => !imgErrors.has(i));
  const handleImgError = useCallback((idx: number) => {
    setImgErrors(prev => new Set(prev).add(idx));
  }, []);

  // Format price — always show numeric range only
  const linkedinHref = (() => {
    if (!contactLinkedin?.trim()) return "";
    const u = contactLinkedin.trim();
    return u.startsWith("http") ? u : `https://${u}`;
  })();
  const linkedinIsCompany =
    linkedinHref.includes("/company/") && !linkedinHref.includes("/in/");
  const linkedinLabel = linkedinHref
    ? linkedinIsCompany
      ? "LinkedIn empresa"
      : contactName
        ? `Perfil de ${contactName}`
        : "Perfil LinkedIn"
    : "";

  const formatPrice = () => {
    if (priceNote) {
      // If priceNote is already a clean range like "€500 - €1200", show it
      const rangeMatch = priceNote.match(/€?\s*(\d+)\s*[-–]\s*€?\s*(\d+)/);
      if (rangeMatch) return `€${rangeMatch[1]} - €${rangeMatch[2]}`;
      // If priceNote is a single value like "€800"
      const singleMatch = priceNote.match(/€?\s*(\d+)/);
      if (singleMatch) return `€${singleMatch[1]}`;
    }
    if (priceEUR && priceEUR > 0) return `€${Math.round(priceEUR)}`;
    if (priceUSD && priceUSD > 0) return `€${Math.round(priceUSD * 0.93)}`;
    return "N/A";
  };

  return (
    <div className="card-lanca overflow-hidden">
      <div className="p-5 lg:p-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-lg font-semibold text-foreground truncate" title={brand.name}>
                {brand.name}
              </h3>
              {brand.verified && (
                <span title="Verificado pela IA" className="flex items-center flex-shrink-0">
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-1.5 text-muted-foreground">
              <MapPin className="h-3.5 w-3.5 flex-shrink-0" />
              <span className="text-sm">
                {isStoreOnlyInSearchCity
                  ? `Loja em ${city || "N/A"}`
                  : hqInSearchCity
                    ? `Sede em ${city || "N/A"}`
                    : `${city || "N/A"}${country ? `, ${country}` : ""}`}
              </span>
              {presence?.label && (
                <Badge
                  variant="outline"
                  className={`text-[10px] px-1.5 py-0 h-5 border ${presence.className}`}
                >
                  {presence.label}
                </Badge>
              )}
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

        {isStoreOnlyInSearchCity && (
          <div
            className="mb-4 flex gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-amber-950"
            role="status"
          >
            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-amber-600 mt-0.5" />
            <div className="min-w-0">
              <p className="text-sm font-medium leading-snug">
                Sem sede em {city || "esta cidade"} — apenas loja local
              </p>
              <p className="text-xs text-amber-900/85 mt-0.5 leading-relaxed">
                {headquartersCity ? (
                  <>
                    A sede está em <span className="font-medium">{headquartersCity}</span>.
                    Esta marca aparece na pesquisa por ter presença comercial em{" "}
                    {city || "destino"}, não por ser uma marca local.
                  </>
                ) : (
                  <>
                    Não há sede confirmada em {city || "destino"}; a presença é
                    uma loja ou filial na cidade pesquisada.
                  </>
                )}
              </p>
            </div>
          </div>
        )}

        {hqInSearchCity && headquartersCity && !isStoreOnlyInSearchCity && (
          <div className="mb-4 flex items-center gap-2 text-xs text-emerald-800 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2">
            <Building2 className="h-3.5 w-3.5 flex-shrink-0" />
            <span>
              Sede em <span className="font-medium">{headquartersCity}</span>
              {city && !headquartersCity.toLowerCase().includes(city.toLowerCase())
                ? ` (${city})`
                : ""}
            </span>
          </div>
        )}

        {/* Product Images */}
        {validImages.length > 0 && (
          <div className="relative mb-4 rounded-lg overflow-hidden bg-muted/30 group">
            <div className="aspect-[16/9] relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={validImages[imgIndex % validImages.length]}
                alt={`${brand.name} product`}
                className="w-full h-full object-cover"
                onError={() => {
                  const actualIdx = productImages.indexOf(validImages[imgIndex % validImages.length]);
                  if (actualIdx >= 0) handleImgError(actualIdx);
                }}
                loading="lazy"
                referrerPolicy="no-referrer"
              />
              {validImages.length > 1 && (
                <>
                  <button
                    onClick={() => setImgIndex((imgIndex - 1 + validImages.length) % validImages.length)}
                    className="absolute left-2 top-1/2 -translate-y-1/2 p-1 rounded-full bg-black/50 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => setImgIndex((imgIndex + 1) % validImages.length)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-full bg-black/50 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                  <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5">
                    {validImages.map((_, i) => (
                      <button
                        key={i}
                        onClick={() => setImgIndex(i)}
                        className={`w-1.5 h-1.5 rounded-full transition-all ${
                          i === imgIndex % validImages.length
                            ? "bg-white scale-125"
                            : "bg-white/50"
                        }`}
                      />
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="bg-muted/50 rounded-lg p-3 text-center">
            <Store className="h-3.5 w-3.5 text-muted-foreground mx-auto mb-1" />
            <p className="text-xs text-muted-foreground mb-0.5">Lojas</p>
            <div className="flex items-center justify-center gap-1">
              <p className="text-sm font-semibold text-foreground">{storeCount}</p>
              {storeCountConfidence !== "unknown" && storeCountConfidence !== "verified" && (
                <span className={`text-[10px] px-1 py-0.5 rounded ${storeConfidenceLabel[storeCountConfidence]?.className || ""}`}>
                  {storeConfidenceLabel[storeCountConfidence]?.text}
                </span>
              )}
            </div>
          </div>
          <div className="bg-muted/50 rounded-lg p-3 text-center">
            <Tag className="h-3.5 w-3.5 text-muted-foreground mx-auto mb-1" />
            <p className="text-xs text-muted-foreground mb-0.5">Preço</p>
            <p className="text-sm font-semibold text-foreground">{formatPrice()}</p>
          </div>
          <div className="bg-muted/50 rounded-lg p-3 text-center">
            <TrendingUp className="h-3.5 w-3.5 text-muted-foreground mx-auto mb-1" />
            <p className="text-xs text-muted-foreground mb-0.5">Score</p>
            <p className="text-sm font-semibold text-foreground">{finalScore || fitScore}/100</p>
          </div>
        </div>

        {/* Brand Style Tag */}
        {brandStyle && (
          <div className="flex items-center gap-2 mb-3">
            <div className="w-1.5 h-1.5 rounded-full bg-lanca-yellow flex-shrink-0" />
            <p className="text-xs text-muted-foreground line-clamp-1">{brandStyle}</p>
          </div>
        )}

        {/* Contact quick access */}
        {(contactName || contactEmail || contactPhone || contactLinkedin) && (
          <div className="flex flex-wrap items-center gap-2 mb-3">
            {contactName && (
              <span className="text-xs text-foreground font-medium px-2 py-1 bg-muted/60 rounded-md">
                {contactName}
                {contactRole ? (
                  <span className="text-muted-foreground font-normal"> · {contactRole}</span>
                ) : null}
              </span>
            )}
            {contactEmail && (
              <a
                href={`mailto:${contactEmail}`}
                className="flex items-center gap-1.5 px-2.5 py-1.5 bg-blue-50 border border-blue-100 rounded-md hover:bg-blue-100 transition-colors"
              >
                <Mail className="h-3.5 w-3.5 text-blue-600" />
                <span className="text-xs text-blue-700 font-medium">{contactEmail}</span>
              </a>
            )}
            {linkedinHref && (
              <a
                href={linkedinHref}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-2.5 py-1.5 bg-[#0A66C2]/10 border border-[#0A66C2]/20 rounded-md hover:bg-[#0A66C2]/15 transition-colors"
              >
                <Linkedin className="h-3.5 w-3.5 text-[#0A66C2]" />
                <span className="text-xs text-[#0A66C2] font-medium">{linkedinLabel}</span>
              </a>
            )}
            {contactPhone && (
              <a
                href={`tel:${contactPhone}`}
                className="flex items-center gap-1.5 px-2.5 py-1.5 bg-muted/50 border border-border rounded-md hover:bg-muted transition-colors"
              >
                <Phone className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs text-foreground font-medium">{contactPhone}</span>
              </a>
            )}
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
                  {linkedinHref && (
                    <a href={linkedinHref} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-sm text-blue-600 hover:underline">
                      <Linkedin className="h-3.5 w-3.5" />
                      {linkedinLabel}
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

            {/* HQ Address */}
            {headquartersConfidence !== "unknown" && (headquartersAddress || headquartersCity) && (
              <div>
                <p className="text-xs font-semibold text-foreground mb-2 uppercase tracking-wide">
                  Sede
                  {headquartersConfidence === "llm_knowledge" && (
                    <span className="ml-2 text-[10px] font-normal text-muted-foreground normal-case">(conhecimento IA)</span>
                  )}
                </p>
                <div className="flex items-start gap-2 bg-muted/50 rounded-lg p-3">
                  <MapPin className="h-3.5 w-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                  <div>
                    {headquartersCity && (
                      <p className="text-sm font-medium text-foreground">{headquartersCity}</p>
                    )}
                    {headquartersAddress && (
                      <p className="text-sm text-muted-foreground leading-relaxed">{headquartersAddress}</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Local Store in target city */}
            {localStoreAddress && (
              <div>
                <p className="text-xs font-semibold text-foreground mb-2 uppercase tracking-wide">Loja local ({city})</p>
                <div className="flex items-start gap-2 bg-muted/50 rounded-lg p-3">
                  <MapPin className="h-3.5 w-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-muted-foreground leading-relaxed">{localStoreAddress}</p>
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
            disabled={emailStatus !== "idle" || !contactEmail}
            className={`flex-1 h-10 rounded-lg text-sm font-medium transition-all duration-200 ${
              emailStatus === "sent" 
                ? "bg-emerald-600 text-white" 
                : !contactEmail
                ? "bg-muted text-muted-foreground cursor-not-allowed"
                : "bg-lanca-black hover:bg-lanca-charcoal text-white"
            }`}
            onClick={handleSendEmail}
            title={!contactEmail ? "Sem email de contacto disponível" : undefined}
          >
            {emailStatus === "idle" ? (
              <div className="flex items-center gap-2">
                <Send className="h-3.5 w-3.5" />
                <span>{!contactEmail ? "Sem email" : "Enviar proposta"}</span>
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
});
