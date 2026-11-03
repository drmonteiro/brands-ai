-- Evidence behind each lead, why brands were rejected, and hiding without deleting.
-- 011_lead_quality.sql

ALTER TABLE prospects ADD COLUMN IF NOT EXISTS price_status TEXT;
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS price_source_url TEXT;
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS price_evidence JSONB DEFAULT '[]'::jsonb;
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS fit_reason TEXT;
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS closest_client TEXT;
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS core_category TEXT;
-- 'hidden' keeps a lead in the database but out of every list. Reversible.
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS quality_status TEXT NOT NULL DEFAULT 'active';
CREATE INDEX IF NOT EXISTS idx_prospects_quality_city ON prospects (quality_status, city);

ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS price_status TEXT;
ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS price_source_url TEXT;
ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS price_evidence JSONB DEFAULT '[]'::jsonb;
ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS core_category TEXT;
ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS suit_evidence_quote TEXT;
ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS suit_evidence_verified BOOLEAN;
ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS target_gender TEXT;
ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS is_chain BOOLEAN;
ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS is_official_site BOOLEAN;

CREATE TABLE IF NOT EXISTS lead_rejections (
    id BIGSERIAL PRIMARY KEY,
    city TEXT NOT NULL,
    domain TEXT,
    name TEXT,
    stage TEXT NOT NULL,
    code TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_lead_rejections_city ON lead_rejections (city, created_at DESC);
