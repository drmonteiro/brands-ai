-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Table for prospects (replaces SQLite table)
CREATE TABLE IF NOT EXISTS prospects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    website_url TEXT NOT NULL,
    domain TEXT NOT NULL,
    city TEXT NOT NULL,
    country TEXT,
    country_code TEXT,
    store_count INTEGER DEFAULT 0,
    avg_suit_price_eur FLOAT,
    brand_style TEXT,
    business_model TEXT,
    company_overview TEXT,
    detailed_description TEXT,
    store_locations JSONB,
    material_composition JSONB,
    sustainability_certs JSONB,
    made_to_measure BOOLEAN DEFAULT FALSE,
    heritage_brand BOOLEAN DEFAULT FALSE,
    quality_score INTEGER DEFAULT 0,
    similarity_score INTEGER DEFAULT 0,
    location_score INTEGER DEFAULT 0,
    location_quality TEXT DEFAULT 'standard',
    final_score INTEGER DEFAULT 0,
    fit_score INTEGER DEFAULT 0,
    most_similar_client TEXT,
    similarity_explanation TEXT,
    status TEXT DEFAULT 'new',
    notes TEXT,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for Lança's top clients (replaces vector_db.py CURRENT_CLIENTS and ChromaDB)
CREATE TABLE IF NOT EXISTS lanca_clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT,
    country_code TEXT,
    city TEXT,
    store_count INTEGER DEFAULT 0,
    brand_style TEXT,
    business_model TEXT,
    description TEXT,
    characteristics JSONB,
    profile_text TEXT,
    embedding vector(1536), -- For OpenAI text-embedding-3-small
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for LangGraph/Agent checkpoints
CREATE TABLE IF NOT EXISTS agent_checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    parent_id TEXT,
    checkpoint BYTEA NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (thread_id, checkpoint_id)
);

-- Table for email logs
CREATE TABLE IF NOT EXISTS email_logs (
    id SERIAL PRIMARY KEY,
    brand_name TEXT NOT NULL,
    website_url TEXT,
    status TEXT NOT NULL,
    error_message TEXT,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_prospects_city ON prospects(city);
CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);
CREATE INDEX IF NOT EXISTS idx_prospects_domain ON prospects(domain);
CREATE INDEX IF NOT EXISTS idx_lanca_clients_embedding ON lanca_clients USING hnsw (embedding vector_cosine_ops);
