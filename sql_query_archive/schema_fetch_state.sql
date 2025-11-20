-- ============================================================
-- Fetch State Tracking Table
-- ============================================================
-- Tracks the last successful fetch timestamp for each symbol+source
-- Enables incremental fetching (only new news since last fetch)

CREATE TABLE IF NOT EXISTS fetch_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What was fetched
    symbol TEXT NOT NULL,
    fetch_source TEXT NOT NULL,  -- 'finnhub', 'polygon', etc.

    -- Timestamp tracking
    last_fetch_from TIMESTAMPTZ NOT NULL,  -- Start of last fetch window
    last_fetch_to TIMESTAMPTZ NOT NULL,    -- End of last fetch window (usually NOW())

    -- Statistics
    articles_fetched INT DEFAULT 0,
    articles_stored INT DEFAULT 0,

    -- Status
    status TEXT DEFAULT 'success',  -- success/failed/partial
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint: one record per symbol+source combination
CREATE UNIQUE INDEX IF NOT EXISTS idx_fetch_state_symbol_source
    ON fetch_state(symbol, fetch_source);

-- Index for querying by source
CREATE INDEX IF NOT EXISTS idx_fetch_state_source
    ON fetch_state(fetch_source);

-- Index for finding stale fetches
CREATE INDEX IF NOT EXISTS idx_fetch_state_last_fetch
    ON fetch_state(last_fetch_to DESC);

-- Update trigger
DROP TRIGGER IF EXISTS update_fetch_state_updated_at ON fetch_state;

CREATE TRIGGER update_fetch_state_updated_at
    BEFORE UPDATE ON fetch_state
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments
COMMENT ON TABLE fetch_state IS 'Tracks last fetch timestamp per symbol+source for incremental fetching';
COMMENT ON COLUMN fetch_state.last_fetch_from IS 'Start timestamp of last successful fetch';
COMMENT ON COLUMN fetch_state.last_fetch_to IS 'End timestamp of last successful fetch (usually NOW())';
COMMENT ON COLUMN fetch_state.articles_fetched IS 'Number of articles fetched in last run';
COMMENT ON COLUMN fetch_state.articles_stored IS 'Number of articles stored (after dedup)';

-- Helper view: Show fetch state with time since last fetch
CREATE OR REPLACE VIEW v_fetch_state_status AS
SELECT
    symbol,
    fetch_source,
    last_fetch_to,
    NOW() - last_fetch_to as time_since_last_fetch,
    articles_fetched,
    articles_stored,
    status,
    updated_at
FROM fetch_state
ORDER BY last_fetch_to DESC;

COMMENT ON VIEW v_fetch_state_status IS 'Shows fetch state with calculated time since last fetch';
