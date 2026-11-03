import { BrandLead, isHeadquartersInSearchCity, LinkedInContact, parseJsonArray, parseLinkedInContacts } from "@/lib/types";

export type PriceState =
  | { kind: "confirmed"; label: string; sourceUrl?: string; quote?: string }
  | { kind: "unverified"; label: string }
  | { kind: "unconfirmed" };

const PRESENCE_LABELS: Record<string, string> = {
  hq: "Sede na cidade",
  store: "Só loja na cidade",
  showroom: "Showroom",
};

const formatEur = (value: number) => `€${Math.round(value).toLocaleString("pt-PT")}`;

function priceLabel(lead: BrandLead): string | null {
  const range = lead.price_note?.match(/€?\s*(\d+)\s*[-–]\s*€?\s*(\d+)/);
  if (range) return `${formatEur(Number(range[1]))} – ${formatEur(Number(range[2]))}`;
  const price = lead.avg_suit_price_eur ?? lead.avgSuitPriceEUR;
  return price && price > 0 ? formatEur(price) : null;
}

/** Older leads have a price with no proof, so it's labelled rather than presented as fact. */
export function getPriceState(lead: BrandLead): PriceState {
  const label = priceLabel(lead);
  if (!label || lead.price_status === "unconfirmed") return { kind: "unconfirmed" };
  if (lead.price_status === "confirmed") {
    const evidence = Array.isArray(lead.price_evidence) ? lead.price_evidence[0] : undefined;
    return {
      kind: "confirmed",
      label,
      sourceUrl: lead.price_source_url || undefined,
      quote: evidence?.quote,
    };
  }
  return { kind: "unverified", label };
}

export function getLinkedInHref(lead: BrandLead): string {
  const value = (lead.contact_linkedin || lead.contactLinkedin || "").trim();
  if (!value) return "";
  return value.startsWith("http") ? value : `https://${value}`;
}

/** Older leads may hold one personal profile from the brand's website and no list. */
export function getContacts(lead: BrandLead): LinkedInContact[] {
  const contacts = parseLinkedInContacts(lead.linkedin_contacts);
  if (contacts.length > 0) return contacts;
  const href = getLinkedInHref(lead);
  if (!href.includes("/in/")) return [];
  return [{
    name: lead.contact_name || lead.contactName || "Perfil LinkedIn",
    role: lead.contact_role || lead.contactRole,
    linkedin_url: href,
  }];
}

export function getCompanyLinkedIn(lead: BrandLead): string {
  const href = getLinkedInHref(lead);
  return href.includes("/company/") && !href.includes("/in/") ? href : "";
}

export function getPeopleSearchUrl(lead: BrandLead): string {
  const keywords = `${lead.name} ${lead.city || ""}`.trim();
  return `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(keywords)}`;
}

export function getLocation(lead: BrandLead) {
  const rawCity = lead.city || "";
  const city = rawCity.charAt(0).toUpperCase() + rawCity.slice(1);
  const hqCity = lead.headquarters_city || lead.headquartersCity || "";
  const presence = lead.city_presence_type || lead.cityPresenceType || "unknown";
  const hqInCity = isHeadquartersInSearchCity(hqCity, rawCity, presence);
  const storeOnly = presence === "store" || (presence === "showroom" && !hqInCity);
  return {
    city,
    hqCity,
    hqInCity,
    storeOnly,
    country: lead.country || lead.originCountry || "",
    presenceLabel: PRESENCE_LABELS[presence] || "",
  };
}

export function getWhyItFits(lead: BrandLead) {
  return {
    client: lead.closest_client || lead.most_similar_client || "",
    reason: lead.fit_reason || lead.similarity_explanation || "",
  };
}

export const getStoreLocations = (lead: BrandLead) => parseJsonArray(lead.store_locations || lead.storeLocations);
export const getMaterials = (lead: BrandLead) => parseJsonArray(lead.material_composition);
export const getImages = (lead: BrandLead) => parseJsonArray(lead.product_images as string[] | string | undefined);
