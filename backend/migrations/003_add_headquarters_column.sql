-- Add headquarters_address column to prospects table
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS headquarters_address TEXT;
