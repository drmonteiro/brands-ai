/**
 * Frontend types for Confeções Lança
 * These mirror the Python Pydantic models in the backend
 */

export interface BrandLead {
  name: string;
  websiteUrl: string;
  storeCount: number;
  averageSuitPriceUSD: number;
  city?: string;
  originCountry: string;
  verified: boolean;
  verificationLog?: string[];
  passesConstraints: boolean;
  revenue?: string;
  clothingTypes?: string[];
  targetGender?: string;
  brandStyle?: string;
  businessModel?: string;
  companyOverview?: string;
  detailedDescription?: string;
  locationQuality?: string;
  locationScore?: number;
  storeLocations?: string[];
  woolPercentage?: string;
  madeToMeasure?: boolean;
}
