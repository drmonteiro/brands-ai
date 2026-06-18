-- Add location confidence and presence fields to prospects
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS headquarters_city TEXT;
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS headquarters_confidence TEXT DEFAULT 'unknown';
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS local_store_address TEXT;
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS city_presence_type TEXT DEFAULT 'unknown';
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS store_count_confidence TEXT DEFAULT 'unknown';
