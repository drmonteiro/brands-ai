/**
 * Frontend types for Confeções Lança
 * These mirror the Python/SQLite backend response format (snake_case)
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
  store_locations?: string;  // JSON string from backend
  material_composition?: string;
  sustainability_certs?: string;
  made_to_measure?: boolean;
  heritage_brand?: boolean;
  quality_score?: number;
  similarity_score?: number;
  location_score?: number;
  location_quality?: string;
  final_score?: number;
  fit_score?: number;
  most_similar_client?: string;
  similarity_explanation?: string;
  status?: string;
  notes?: string;
  price_note?: string;
  discovered_at?: string;
  updated_at?: string;
  contact_name?: string;
  contact_role?: string;
  contact_email?: string;
  contact_phone?: string;
  contact_linkedin?: string;
  feedback_history?: {
    feedback_type: "up" | "down";
    comment: string;
    created_at: string;
    manager_name: string;
  }[];

  // Legacy camelCase aliases (for backward compatibility)
  websiteUrl?: string;
  storeCount?: number;
  averageSuitPriceUSD?: number;
  avgSuitPriceEUR?: number;
  originCountry?: string;
  verified?: boolean;
  clothingTypes?: string[];
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
