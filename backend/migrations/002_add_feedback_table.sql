-- Migration: Add feedback table for sales team
-- 002_add_feedback_table.sql

CREATE TABLE IF NOT EXISTS prospect_feedback (
    id SERIAL PRIMARY KEY,
    prospect_id VARCHAR(50) NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    manager_name VARCHAR(100) DEFAULT 'Comercial',
    feedback_type VARCHAR(10) NOT NULL, -- 'up' or 'down'
    comment TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_feedback_prospect_id ON prospect_feedback(prospect_id);
