-- Add fields used by the API without dropping existing data or legacy tables.
ALTER TABLE price_candles_daily ADD COLUMN IF NOT EXISTS adjusted_close NUMERIC(12,2);
ALTER TABLE valuation_assumptions ADD COLUMN IF NOT EXISTS is_override BOOLEAN DEFAULT FALSE;
ALTER TABLE valuation_assumptions ADD COLUMN IF NOT EXISTS override_reason TEXT;
ALTER TABLE shareholding_patterns ADD COLUMN IF NOT EXISTS retail_pct NUMERIC(6,3);
ALTER TABLE shareholding_patterns ADD COLUMN IF NOT EXISTS hni_pct NUMERIC(6,3);

CREATE TABLE IF NOT EXISTS ml_cluster_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nse_symbol VARCHAR(30) NOT NULL REFERENCES stocks(nse_symbol),
    run_date DATE NOT NULL,
    cluster_label VARCHAR(50),
    cluster_id INTEGER,
    cluster_description TEXT,
    distance_to_centroid NUMERIC(10,6),
    features_used JSONB DEFAULT '[]',
    feature_values JSONB DEFAULT '{}',
    algorithm VARCHAR(30) DEFAULT 'KMEANS',
    model_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (nse_symbol, run_date)
);
CREATE INDEX IF NOT EXISTS idx_ml_clusters_symbol_date ON ml_cluster_results(nse_symbol, run_date DESC);

-- Retain legacy clustering history and copy its latest observation per IST day.
INSERT INTO ml_cluster_results (nse_symbol, run_date, cluster_label, cluster_id,
                               cluster_description, created_at)
SELECT DISTINCT ON (nse_symbol, (computed_at AT TIME ZONE 'Asia/Kolkata')::date)
    nse_symbol, (computed_at AT TIME ZONE 'Asia/Kolkata')::date,
    cluster_label, cluster_id, explanation, computed_at
FROM cluster_results
WHERE computed_at IS NOT NULL
ORDER BY nse_symbol, (computed_at AT TIME ZONE 'Asia/Kolkata')::date, computed_at DESC, id
ON CONFLICT (nse_symbol, run_date) DO NOTHING;

-- A fallback prevents ingestion failure outside the pre-created 2025/2026 months.
-- Check for older ORM-created, unpartitioned installations before adding it.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_partitioned_table WHERE partrelid = 'price_candles_1m'::regclass) THEN
        CREATE TABLE IF NOT EXISTS price_candles_1m_default PARTITION OF price_candles_1m DEFAULT;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO schema_migrations (filename) VALUES ('003_api_schema_alignment.sql') ON CONFLICT DO NOTHING;
