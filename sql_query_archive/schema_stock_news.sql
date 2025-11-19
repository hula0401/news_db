-- ============================================================
-- Stock News Table Schema (if not already exists)
-- ============================================================
-- This table stores processed news articles for stock symbols
-- Implements a LIFO stack (position 1-5)

CREATE TABLE IF NOT EXISTS stock_news (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core fields
    symbol TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    url TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,

    -- Source information
    source_id UUID,  -- Reference to news_sources table if exists
    external_id TEXT,  -- External ID from API

    -- Stack position
    position_in_stack INT NOT NULL DEFAULT 1,

    -- Additional data
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for stock_news
CREATE INDEX IF NOT EXISTS idx_stock_news_symbol
    ON stock_news(symbol);

CREATE INDEX IF NOT EXISTS idx_stock_news_symbol_position
    ON stock_news(symbol, position_in_stack);

CREATE INDEX IF NOT EXISTS idx_stock_news_url
    ON stock_news(url);

CREATE INDEX IF NOT EXISTS idx_stock_news_published
    ON stock_news(published_at DESC);

-- Unique constraint: symbol + url (prevent duplicates)
CREATE UNIQUE INDEX IF NOT EXISTS idx_stock_news_symbol_url
    ON stock_news(symbol, url);

-- Comments
COMMENT ON TABLE stock_news IS 'Processed stock news articles (LIFO stack, top 5 per symbol)';
COMMENT ON COLUMN stock_news.symbol IS 'Stock ticker symbol';
COMMENT ON COLUMN stock_news.position_in_stack IS 'Position in LIFO stack (1=newest, 5=oldest kept)';
COMMENT ON COLUMN stock_news.external_id IS 'External ID from source API';

-- Update trigger for updated_at
CREATE TRIGGER update_stock_news_updated_at
    BEFORE UPDATE ON stock_news
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Optional: Function to increment positions (used by StockNewsDB)
CREATE OR REPLACE FUNCTION increment_news_positions(p_symbol TEXT)
RETURNS VOID AS $$
BEGIN
    UPDATE stock_news
    SET position_in_stack = position_in_stack + 1
    WHERE symbol = p_symbol;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION increment_news_positions IS 'Increment all news positions for a symbol (used when pushing new news to stack)';
