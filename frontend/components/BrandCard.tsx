"use client";

import { memo, useState } from "react";
import { toast } from "sonner";
import { ChevronDown, ChevronUp, Globe, Linkedin, MapPin, RefreshCw, Search, ThumbsDown, ThumbsUp } from "lucide-react";
import { apiFetch } from "@/lib/apiBase";
import { getContacts, getLocation, getPeopleSearchUrl, getWhyItFits } from "@/lib/lead";
import { BrandLead, parseLinkedInContacts } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { FeedbackModal } from "./FeedbackModal";
import { LeadContacts } from "./lead/LeadContacts";
import { LeadDetails } from "./lead/LeadDetails";
import { LeadFacts } from "./lead/LeadFacts";
import { LinkedInMessageModal } from "./LinkedInMessageModal";

interface BrandCardProps {
  brand: BrandLead;
  managerName?: string;
}

type FeedbackType = "up" | "down";

const STATUS_OPTIONS = [
  { value: "new", label: "Novo" },
  { value: "contacted", label: "Contactado" },
  { value: "converted", label: "Convertido" },
  { value: "rejected", label: "Rejeitado" },
];

export const BrandCard = memo(function BrandCard({ brand, managerName = "Comercial" }: BrandCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [status, setStatus] = useState(brand.status || "new");
  const [showLinkedInModal, setShowLinkedInModal] = useState(false);
  const [isFindingContacts, setIsFindingContacts] = useState(false);
  // Result of an on-demand lookup, layered over the lead from the list.
  const [lookupResult, setLookupResult] = useState<Partial<BrandLead> | null>(null);
  const [feedbackModal, setFeedbackModal] = useState<FeedbackType | null>(null);
  const [feedbackSent, setFeedbackSent] = useState<FeedbackType | null>(null);

  const lead: BrandLead = lookupResult ? { ...brand, ...lookupResult } : brand;
  const location = getLocation(lead);
  const why = getWhyItFits(lead);
  const contacts = getContacts(lead);
  const websiteUrl = lead.website_url || lead.websiteUrl || "";

  const handleStatusChange = async (newStatus: string) => {
    const previous = status;
    setStatus(newStatus);
    try {
      const response = await apiFetch(`/api/prospects/${brand.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      toast.success(`Estado: ${STATUS_OPTIONS.find((o) => o.value === newStatus)?.label}`);
    } catch {
      setStatus(previous);
      toast.error("Não foi possível atualizar o estado.");
    }
  };

  const handleFeedbackSubmit = async (comment: string) => {
    if (!feedbackModal) return;
    const response = await apiFetch(`/api/prospects/${brand.id}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feedback_type: feedbackModal, comment, manager_name: managerName }),
    });
    if (!response.ok) {
      toast.error("Não foi possível guardar o feedback.");
      return;
    }
    setFeedbackSent(feedbackModal);
  };

  const handleFindContacts = async () => {
    setIsFindingContacts(true);
    try {
      const response = await apiFetch(`/api/prospects/${brand.id}/linkedin-contacts`, { method: "POST" });
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(error?.detail);
      }
      const updated: BrandLead = await response.json();
      setLookupResult(updated);
      const found = parseLinkedInContacts(updated.linkedin_contacts).length;
      if (found > 0) toast.success(`${found} contacto${found > 1 ? "s" : ""} encontrado${found > 1 ? "s" : ""}.`);
      else toast.info("Sem perfis verificados. Podes pesquisar diretamente no LinkedIn.");
    } catch (error) {
      toast.error(error instanceof Error && error.message ? error.message : "Não foi possível procurar contactos.");
    } finally {
      setIsFindingContacts(false);
    }
  };

  const feedbackButton = (type: FeedbackType, label: string, Icon: typeof ThumbsUp, active: string) => (
    <button
      onClick={() => setFeedbackModal(type)}
      aria-label={label}
      title={label}
      className={`rounded p-1.5 transition-colors hover:bg-muted ${
        feedbackSent === type ? active : "text-muted-foreground hover:text-foreground"
      }`}
    >
      <Icon className="h-4 w-4" />
    </button>
  );

  const iconButton = "h-10 w-10 flex-shrink-0 rounded border-border";

  return (
    <article className="card-lanca flex flex-col gap-4 p-5">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="break-words font-serif text-xl font-semibold leading-tight text-foreground">{lead.name}</h3>
          <p className="mt-1 flex flex-wrap items-center gap-x-1.5 text-[12px] text-muted-foreground">
            <MapPin className="h-3 w-3 flex-shrink-0" aria-hidden />
            {location.city || "N/A"}
            {location.country && !location.hqInCity ? `, ${location.country}` : ""}
            {location.presenceLabel && (
              <span className={location.storeOnly ? "text-amber-800" : "text-emerald-800"}>
                · {location.presenceLabel}
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-shrink-0 flex-col items-end gap-1">
          <select
            value={status}
            onChange={(event) => handleStatusChange(event.target.value)}
            aria-label={`Estado de ${lead.name}`}
            className="rounded border border-border bg-white px-2 py-1 text-[12px] font-medium text-foreground"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <div className="flex">
            {feedbackButton("up", "Boa lead", ThumbsUp, "text-emerald-700")}
            {feedbackButton("down", "Esta marca não serve", ThumbsDown, "text-rose-700")}
          </div>
        </div>
      </header>

      {(why.reason || why.client) && (
        <div className="border-l-2 border-lanca-gold pl-3">
          {why.client && why.client !== "N/A" && (
            <p className="text-[12px] font-medium text-foreground">Semelhante a {why.client}</p>
          )}
          {why.reason && <p className="mt-0.5 text-[13px] leading-relaxed text-muted-foreground">{why.reason}</p>}
        </div>
      )}

      <LeadFacts lead={lead} />
      <LeadContacts lead={lead} />

      {isExpanded && <LeadDetails lead={lead} />}

      <footer className="mt-auto flex items-center gap-2 pt-1">
        {contacts.length > 0 ? (
          <Button
            onClick={() => setShowLinkedInModal(true)}
            className="h-10 min-w-0 flex-1 gap-2 rounded bg-[#0A66C2] text-[13px] font-medium text-white hover:bg-[#004182]"
          >
            <Linkedin className="h-4 w-4 flex-shrink-0" aria-hidden /> Mensagem LinkedIn
          </Button>
        ) : lead.linkedin_contacts_checked_at ? (
          <Button
            variant="outline"
            onClick={() => window.open(getPeopleSearchUrl(lead), "_blank", "noopener,noreferrer")}
            title="Sem perfis verificados para esta marca"
            className="h-10 min-w-0 flex-1 gap-2 rounded text-[13px] font-medium"
          >
            <Linkedin className="h-4 w-4 flex-shrink-0 text-[#0A66C2]" aria-hidden /> Pesquisar no LinkedIn
          </Button>
        ) : (
          <Button
            disabled={isFindingContacts}
            onClick={handleFindContacts}
            className="h-10 min-w-0 flex-1 gap-2 rounded bg-lanca-ink text-[13px] font-medium text-white hover:bg-lanca-charcoal"
          >
            {isFindingContacts
              ? <RefreshCw className="h-4 w-4 flex-shrink-0 animate-spin" aria-hidden />
              : <Search className="h-4 w-4 flex-shrink-0" aria-hidden />}
            {isFindingContacts ? "A procurar..." : "Procurar contactos"}
          </Button>
        )}
        {websiteUrl && (
          <Button
            variant="outline"
            size="icon"
            className={iconButton}
            aria-label={`Abrir site de ${lead.name}`}
            title="Abrir site"
            onClick={() => window.open(websiteUrl, "_blank", "noopener,noreferrer")}
          >
            <Globe className="h-4 w-4 text-muted-foreground" />
          </Button>
        )}
        <Button
          variant="outline"
          size="icon"
          className={iconButton}
          aria-expanded={isExpanded}
          aria-label={isExpanded ? "Mostrar menos" : "Mostrar mais"}
          title={isExpanded ? "Menos" : "Mais"}
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </Button>
      </footer>

      {showLinkedInModal && (
        <LinkedInMessageModal
          brand={lead}
          contacts={contacts}
          onClose={() => setShowLinkedInModal(false)}
          onProfileOpened={() => {
            if (status === "new") void handleStatusChange("contacted");
          }}
        />
      )}
      {feedbackModal && (
        <FeedbackModal
          brandName={lead.name}
          feedbackType={feedbackModal}
          onClose={() => setFeedbackModal(null)}
          onSubmit={handleFeedbackSubmit}
        />
      )}
    </article>
  );
});
