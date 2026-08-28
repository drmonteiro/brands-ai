-- Speed up city prospect lists sorted by score
CREATE INDEX IF NOT EXISTS idx_prospects_city_score ON prospects(city, final_score DESC);

-- Speed up batch feedback lookups
CREATE INDEX IF NOT EXISTS idx_prospect_feedback_prospect_id ON prospect_feedback(prospect_id);
