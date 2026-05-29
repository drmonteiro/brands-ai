-- Cross-city brand-level facts cache (keyed by domain)
-- 007_brand_facts.sql

CREATE TABLE IF NOT EXISTS brand_facts (
    domain TEXT PRIMARY KEY,
    name TEXT,
    website_url TEXT,
    origin_country TEXT,
    headquarters_city TEXT,
    headquarters_confidence TEXT DEFAULT 'unknown',
    contact_email TEXT,
    avg_suit_price_eur DOUBLE PRECISION,
    price_range_min_eur DOUBLE PRECISION,
    price_range_max_eur DOUBLE PRECISION,
    price_note TEXT,
    store_count INTEGER DEFAULT 0,
    store_count_confidence TEXT DEFAULT 'unknown',
    store_locations JSONB DEFAULT '[]'::jsonb,
    wool_percentage TEXT,
    made_to_measure BOOLEAN,
    brand_style TEXT,
    business_model TEXT,
    company_overview TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_brand_facts_updated_at ON brand_facts (updated_at DESC);
