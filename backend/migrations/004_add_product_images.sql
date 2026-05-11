-- Add product_images column to store scraped product image URLs per prospect
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS product_images JSONB DEFAULT '[]'::jsonb;
