/**
 * Frontend types for Confeções Lança
 * These mirror the Python/PostgreSQL backend response format (snake_case)
 */

export interface BrandLead {
  id: string;
  name: string;
  website_url: string;
  domain?: string;
  city?: string;
  country?: string;
  country_code?: string;
  store_count: number;
  avg_suit_price_eur?: number;
  brand_style?: string;
  business_model?: string;
  company_overview?: string;
  detailed_description?: string;
  store_locations?: string;
  material_composition?: string;
  made_to_measure?: boolean;
  wool_percentage?: string;
  final_score?: number;
  fit_score?: number;
  most_similar_client?: string;
  similarity_explanation?: string;
  status?: string;
  notes?: string;
  price_note?: string;
  headquarters_address?: string;
  headquarters_city?: string;
  headquarters_confidence?: string;
  local_store_address?: string;
  city_presence_type?: string;
  store_count_confidence?: string;
  discovered_at?: string;
  updated_at?: string;
  contact_name?: string;
  contact_role?: string;
  contact_email?: string;
  contact_phone?: string;
  contact_linkedin?: string;
  product_images?: string[];
  feedback_history?: {
    feedback_type: "up" | "down";
    comment: string;
    created_at: string;
    manager_name: string;
  }[];

  // Legacy camelCase aliases (for backward compatibility with old data)
  websiteUrl?: string;
  storeCount?: number;
  averageSuitPriceUSD?: number;
  avgSuitPriceEUR?: number;
  originCountry?: string;
  verified?: boolean;
  detailedDescription?: string;
  companyOverview?: string;
  storeLocations?: string[];
  fitForLanca?: 'high' | 'medium' | 'low';
  contactName?: string;
  contactRole?: string;
  contactEmail?: string;
  contactPhone?: string;
  contactLinkedin?: string;
  fitScore?: number;
  headquartersCity?: string;
  headquartersConfidence?: string;
  localStoreAddress?: string;
  cityPresenceType?: string;
  storeCountConfidence?: string;
}

/**
 * Helper to safely parse JSON string arrays from the backend
 */
export function parseJsonArray(value: string | string[] | undefined | null): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

/**
 * Get a value supporting both snake_case and camelCase field names
 */
export function getBrandField<T>(brand: BrandLead, snakeCase: keyof BrandLead, camelCase: keyof BrandLead): T | undefined {
  return (brand[snakeCase] ?? brand[camelCase]) as T | undefined;
}

/** Normalize for city comparison (Vienna ↔ Wien, accents, etc.) */
export function normalizeCityName(city: string): string {
  return city
    .toLowerCase()
    .trim()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

const CITY_ALIAS_GROUPS: string[][] = [
  ["vienna", "wien", "wiener"],
  ["munich", "munchen", "muenchen"],
  ["cologne", "koln", "koeln"],
  ["zurich", "zuerich"],
  ["rome", "roma"],
  ["milan", "milano"],
  ["lisbon", "lisboa"],
  ["brussels", "bruxelles", "brussel"],
];

function cityTokens(city: string): Set<string> {
  const n = normalizeCityName(city);
  const tokens = new Set<string>([n]);
  for (const group of CITY_ALIAS_GROUPS) {
    if (group.some((g) => n === g || n.includes(g))) {
      group.forEach((g) => tokens.add(g));
    }
  }
  return tokens;
}

/** True when two city labels refer to the same place (e.g. Vienna / Wien). */
export function citiesReferToSamePlace(a: string, b: string): boolean {
  if (!a?.trim() || !b?.trim()) return false;
  const ta = cityTokens(a);
  const tb = cityTokens(b);
  for (const t of ta) {
    if (tb.has(t)) return true;
  }
  const na = normalizeCityName(a);
  const nb = normalizeCityName(b);
  return na === nb || na.includes(nb) || nb.includes(na);
}

/** HQ is in the city being prospected (brand.city), not merely a local store. */
export function isHeadquartersInSearchCity(
  headquartersCity: string | undefined,
  searchCity: string,
  cityPresenceType?: string
): boolean {
  if (cityPresenceType === "hq") return true;
  if (!headquartersCity?.trim() || !searchCity?.trim()) return false;
  return citiesReferToSamePlace(headquartersCity, searchCity);
}
