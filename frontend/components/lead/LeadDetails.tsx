import { useState } from "react";
import { ChevronLeft, ChevronRight, MapPin, MessageSquare, ThumbsDown, ThumbsUp } from "lucide-react";
import { getImages, getLocation, getMaterials, getStoreLocations } from "@/lib/lead";
import { BrandLead } from "@/lib/types";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h4 className="section-label mb-2">{title}</h4>
      {children}
    </section>
  );
}

function ProductImages({ lead }: { lead: BrandLead }) {
  const images = getImages(lead);
  const [index, setIndex] = useState(0);
  const [failed, setFailed] = useState<Set<string>>(new Set());
  const valid = images.filter((image) => !failed.has(image));
  if (valid.length === 0) return null;
  const current = valid[index % valid.length];
  const move = (step: number) => setIndex((index + step + valid.length) % valid.length);
  const arrow = "absolute top-1/2 -translate-y-1/2 rounded-full bg-black/60 p-1.5 text-white hover:bg-black/80";

  return (
    <div className="relative aspect-[16/9] overflow-hidden rounded bg-muted">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={current}
        alt={`Produto de ${lead.name}`}
        className="h-full w-full object-cover"
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setFailed((previous) => new Set(previous).add(current))}
      />
      {valid.length > 1 && (
        <>
          <button onClick={() => move(-1)} aria-label="Imagem anterior" className={`${arrow} left-2`}>
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button onClick={() => move(1)} aria-label="Imagem seguinte" className={`${arrow} right-2`}>
            <ChevronRight className="h-4 w-4" />
          </button>
        </>
      )}
    </div>
  );
}

export function LeadDetails({ lead }: { lead: BrandLead }) {
  const location = getLocation(lead);
  const description = lead.detailed_description || lead.detailedDescription || lead.company_overview || lead.companyOverview || "";
  const stores = getStoreLocations(lead);
  const materials = getMaterials(lead);
  const hqConfidence = lead.headquarters_confidence || lead.headquartersConfidence || "unknown";
  const localStore = lead.local_store_address || lead.localStoreAddress || "";
  const feedback = lead.feedback_history || [];

  return (
    <div className="space-y-5 border-t border-border pt-4 animate-fade-in">
      <ProductImages lead={lead} />

      {description && (
        <Section title="Sobre a marca">
          <p className="text-[13px] leading-relaxed text-muted-foreground">{description}</p>
        </Section>
      )}

      {hqConfidence !== "unknown" && (location.hqCity || lead.headquarters_address) && (
        <Section title={hqConfidence === "llm_knowledge" ? "Sede (conhecimento IA)" : "Sede"}>
          <p className="flex gap-2 text-[13px] text-muted-foreground">
            <MapPin className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden />
            <span>{[location.hqCity, lead.headquarters_address].filter(Boolean).join(" · ")}</span>
          </p>
        </Section>
      )}

      {localStore && (
        <Section title={`Loja em ${location.city}`}>
          <p className="flex gap-2 text-[13px] text-muted-foreground">
            <MapPin className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden />
            {localStore}
          </p>
        </Section>
      )}

      {(lead.business_model || lead.brand_style) && (
        <Section title="Negócio">
          <p className="text-[13px] text-muted-foreground">
            {[lead.brand_style, lead.business_model, lead.made_to_measure && "Made to Measure"].filter(Boolean).join(" · ")}
          </p>
        </Section>
      )}

      {stores.length > 0 && (
        <Section title="Localizações">
          <ul className="space-y-1 text-[13px] text-muted-foreground">
            {stores.map((store) => <li key={store}>{store}</li>)}
          </ul>
        </Section>
      )}

      {materials.length > 0 && (
        <Section title="Materiais">
          <p className="text-[13px] text-muted-foreground">{materials.join(", ")}</p>
        </Section>
      )}

      {feedback.length > 0 && (
        <Section title="Histórico de feedback">
          <ul className="space-y-2">
            {feedback.map((item, index) => (
              <li key={index} className="rounded border border-border p-3 text-[13px]">
                <p className="mb-1 flex items-center gap-1.5 text-[12px] text-muted-foreground">
                  {item.feedback_type === "up"
                    ? <ThumbsUp className="h-3 w-3 text-emerald-700" aria-label="Positivo" />
                    : <ThumbsDown className="h-3 w-3 text-rose-700" aria-label="Negativo" />}
                  <span className="font-medium text-foreground">{item.manager_name}</span>
                  · {new Date(item.created_at).toLocaleDateString("pt-PT")}
                  <MessageSquare className="ml-auto h-3 w-3" aria-hidden />
                </p>
                <p className="text-muted-foreground">{item.comment}</p>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}
