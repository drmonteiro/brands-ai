import { ExternalLink } from "lucide-react";
import { getPriceState, PriceState } from "@/lib/lead";
import { BrandLead } from "@/lib/types";

function PriceValue({ price }: { price: PriceState }) {
  if (price.kind === "unconfirmed") {
    return <p className="text-[13px] font-medium text-amber-800">Preço não confirmado</p>;
  }
  return (
    <>
      <p className="text-[15px] font-semibold tabular-nums text-foreground">{price.label}</p>
      {price.kind === "unverified" && (
        <p className="text-[11px] text-amber-800" title="Encontrado antes de os preços exigirem prova">
          Não verificado
        </p>
      )}
      {price.kind === "confirmed" && price.sourceUrl && (
        <a
          href={price.sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          title={price.quote}
          className="inline-flex items-center gap-1 text-[11px] text-lanca-goldDeep hover:underline"
        >
          Ver fonte <ExternalLink className="h-3 w-3" aria-hidden />
        </a>
      )}
    </>
  );
}

const STORE_CONFIDENCE: Record<string, string> = { estimated: "estimado", uncertain: "aprox." };

export function LeadFacts({ lead }: { lead: BrandLead }) {
  const stores = lead.store_count ?? lead.storeCount ?? 0;
  const confidence = lead.store_count_confidence || lead.storeCountConfidence || "unknown";
  const score = lead.final_score ?? lead.fit_score ?? lead.fitScore ?? 0;

  return (
    <dl className="grid grid-cols-[1fr_auto_auto] gap-x-6 border-y border-border py-3">
      <div className="min-w-0">
        <dt className="section-label mb-1">Fato completo</dt>
        <dd><PriceValue price={getPriceState(lead)} /></dd>
      </div>
      <div>
        <dt className="section-label mb-1">Lojas</dt>
        <dd className="text-[15px] font-semibold tabular-nums text-foreground">
          {stores || "–"}
          {STORE_CONFIDENCE[confidence] && (
            <span className="ml-1 text-[11px] font-normal text-muted-foreground">{STORE_CONFIDENCE[confidence]}</span>
          )}
        </dd>
      </div>
      <div>
        <dt className="section-label mb-1">Encaixe</dt>
        <dd className="text-[15px] font-semibold tabular-nums text-foreground">
          {Math.round(score)}<span className="text-[11px] font-normal text-muted-foreground">/100</span>
        </dd>
      </div>
    </dl>
  );
}
