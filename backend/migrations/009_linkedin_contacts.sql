-- Ranked LinkedIn decision-makers per lead (max 3): {name, role, tier, linkedin_url, evidence}
-- 009_linkedin_contacts.sql

ALTER TABLE prospects
    ADD COLUMN IF NOT EXISTS linkedin_contacts JSONB DEFAULT '[]'::jsonb;

-- NULL on prospects means "never looked up"; drives the "Procurar contactos" button.
ALTER TABLE prospects
    ADD COLUMN IF NOT EXISTS linkedin_contacts_checked_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE brand_facts
    ADD COLUMN IF NOT EXISTS linkedin_contacts JSONB DEFAULT '[]'::jsonb;

ALTER TABLE brand_facts
    ADD COLUMN IF NOT EXISTS linkedin_contacts_checked_at TIMESTAMP WITH TIME ZONE;

-- Person contact fields: cached so cross-city cache hits keep them.
ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS contact_name TEXT;
ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS contact_role TEXT;
ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS contact_phone TEXT;
ALTER TABLE brand_facts ADD COLUMN IF NOT EXISTS contact_linkedin TEXT;
