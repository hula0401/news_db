-- ============================================================
-- Supabase Schema for News Fetching System
-- ============================================================

-- ============================================================
-- 1. stock_news_raw (Data Lake)
-- ============================================================
-- Stores raw unprocessed news from all sources

CREATE TABLE IF NOT EXISTS stock_news_raw (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core fields
    symbol TEXT NOT NULL,
    raw_html TEXT,                          -- HTML from web scraping
    raw_json JSONB,                         -- JSON from APIs
    url TEXT NOT NULL,
    fetch_source TEXT NOT NULL,             -- finnhub, polygon, newsapi, yfinance, etc.
    fetched_at TIMESTAMPTZ NOT NULL,

    -- Processing state
    is_processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    processing_status TEXT DEFAULT 'pending',  -- pending/processing/completed/failed
    error_log TEXT,

    -- Additional data
    metadata JSONB DEFAULT '{}'::jsonb,
    content_hash TEXT,                      -- MD5 hash for deduplication

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for stock_news_raw
CREATE INDEX IF NOT EXISTS idx_stock_news_raw_symbol
    ON stock_news_raw(symbol);

CREATE INDEX IF NOT EXISTS idx_stock_news_raw_unprocessed
    ON stock_news_raw(is_processed, created_at DESC)
    WHERE is_processed = FALSE;

CREATE INDEX IF NOT EXISTS idx_stock_news_raw_content_hash
    ON stock_news_raw(content_hash);

CREATE INDEX IF NOT EXISTS idx_stock_news_raw_status
    ON stock_news_raw(processing_status);

CREATE INDEX IF NOT EXISTS idx_stock_news_raw_source
    ON stock_news_raw(fetch_source);

-- Comments
COMMENT ON TABLE stock_news_raw IS 'Data lake for raw unprocessed news from all sources';
COMMENT ON COLUMN stock_news_raw.symbol IS 'Stock ticker symbol (e.g., AAPL, TSLA)';
COMMENT ON COLUMN stock_news_raw.raw_html IS 'Raw HTML content from web scraping';
COMMENT ON COLUMN stock_news_raw.raw_json IS 'Raw JSON response from APIs';
COMMENT ON COLUMN stock_news_raw.fetch_source IS 'Source API (finnhub, polygon, newsapi, yfinance)';
COMMENT ON COLUMN stock_news_raw.processing_status IS 'Processing status (pending/processing/completed/failed)';
COMMENT ON COLUMN stock_news_raw.content_hash IS 'MD5 hash of URL for deduplication';


-- ============================================================
-- 2. fetch_log (Tracking)
-- ============================================================
-- Tracks all fetch operations for monitoring

CREATE TABLE IF NOT EXISTS fetch_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Fetch metadata
    fetch_source TEXT NOT NULL,             -- finnhub, polygon, etc.
    symbols TEXT[] NOT NULL,                -- Symbols fetched

    -- Statistics
    articles_fetched INT NOT NULL DEFAULT 0,
    articles_stored INT NOT NULL DEFAULT 0,
    articles_duplicates INT NOT NULL DEFAULT 0,
    articles_failed INT NOT NULL DEFAULT 0,

    -- Timing
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_seconds NUMERIC,

    -- Status
    status TEXT NOT NULL DEFAULT 'running',  -- running/completed/failed
    error_message TEXT,

    -- Additional data
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fetch_log
CREATE INDEX IF NOT EXISTS idx_fetch_log_source
    ON fetch_log(fetch_source);

CREATE INDEX IF NOT EXISTS idx_fetch_log_status
    ON fetch_log(status);

CREATE INDEX IF NOT EXISTS idx_fetch_log_created
    ON fetch_log(created_at DESC);

-- Comments
COMMENT ON TABLE fetch_log IS 'Tracks all news fetch operations for monitoring';
COMMENT ON COLUMN fetch_log.fetch_source IS 'Source of the fetch operation';
COMMENT ON COLUMN fetch_log.articles_fetched IS 'Total articles fetched from API';
COMMENT ON COLUMN fetch_log.articles_stored IS 'Articles successfully stored';
COMMENT ON COLUMN fetch_log.articles_duplicates IS 'Duplicate articles skipped';


-- ============================================================
-- 3. summaries (AI-Generated Summaries)
-- ============================================================
-- Stores AI-generated summaries for news articles

CREATE TABLE IF NOT EXISTS summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Reference to news article
    news_id UUID REFERENCES stock_news(id) ON DELETE CASCADE,

    -- Summary content
    summary_type TEXT NOT NULL,             -- brief/detailed/sentiment/key_points
    content TEXT NOT NULL,

    -- Generation metadata
    model_used TEXT,                        -- gpt-4, claude-3, etc.
    tokens_used INT,
    processing_time_ms INT,
    confidence_score NUMERIC,               -- 0-1 confidence in summary quality

    -- Additional data
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for summaries
CREATE INDEX IF NOT EXISTS idx_summaries_news_id
    ON summaries(news_id);

CREATE INDEX IF NOT EXISTS idx_summaries_type
    ON summaries(summary_type);

CREATE INDEX IF NOT EXISTS idx_summaries_created
    ON summaries(created_at DESC);

-- Comments
COMMENT ON TABLE summaries IS 'AI-generated summaries for news articles';
COMMENT ON COLUMN summaries.news_id IS 'Reference to stock_news table';
COMMENT ON COLUMN summaries.summary_type IS 'Type of summary (brief/detailed/sentiment/key_points)';
COMMENT ON COLUMN summaries.model_used IS 'AI model used for generation (e.g., gpt-4, claude-3)';


-- ============================================================
-- 4. Update trigger for updated_at
-- ============================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for stock_news_raw
CREATE TRIGGER update_stock_news_raw_updated_at
    BEFORE UPDATE ON stock_news_raw
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for summaries
CREATE TRIGGER update_summaries_updated_at
    BEFORE UPDATE ON summaries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- 5. Helpful Views
-- ============================================================

-- View: Unprocessed news count by symbol
CREATE OR REPLACE VIEW v_unprocessed_news_by_symbol AS
SELECT
    symbol,
    COUNT(*) as pending_count,
    MIN(created_at) as oldest_pending,
    MAX(created_at) as newest_pending
FROM stock_news_raw
WHERE is_processed = FALSE AND processing_status = 'pending'
GROUP BY symbol
ORDER BY pending_count DESC;

-- View: Processing statistics
CREATE OR REPLACE VIEW v_processing_stats AS
SELECT
    processing_status,
    COUNT(*) as count,
    COUNT(DISTINCT symbol) as symbols,
    COUNT(DISTINCT fetch_source) as sources
FROM stock_news_raw
GROUP BY processing_status;

-- View: Recent fetch operations
CREATE OR REPLACE VIEW v_recent_fetches AS
SELECT
    id,
    fetch_source,
    array_length(symbols, 1) as symbol_count,
    articles_fetched,
    articles_stored,
    articles_duplicates,
    duration_seconds,
    status,
    started_at
FROM fetch_log
ORDER BY started_at DESC
LIMIT 100;


-- ============================================================
-- 6. Example Queries
-- ============================================================

-- Check unprocessed news
-- SELECT * FROM stock_news_raw WHERE is_processed = FALSE LIMIT 10;

-- Get processing statistics
-- SELECT * FROM v_processing_stats;

-- Get pending news by symbol
-- SELECT * FROM v_unprocessed_news_by_symbol;

-- Find failed processing attempts
-- SELECT id, symbol, url, error_log
-- FROM stock_news_raw
-- WHERE processing_status = 'failed';

-- Recent fetch operations
-- SELECT * FROM v_recent_fetches;

-- Cleanup old processed news (older than 30 days)
-- DELETE FROM stock_news_raw
-- WHERE is_processed = TRUE
-- AND processed_at < NOW() - INTERVAL '30 days';
