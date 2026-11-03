-- save_prospect writes price_note, but no earlier migration creates it, so a new
-- database can't save leads. Existing databases already have the column.
-- 010_prospects_price_note.sql

ALTER TABLE prospects ADD COLUMN IF NOT EXISTS price_note TEXT;
