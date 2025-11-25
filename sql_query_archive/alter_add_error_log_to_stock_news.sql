-- ============================================================
-- Add error_log column to stock_news table
-- ============================================================
-- This column stores error information when LLM categorization fails
-- Used to prevent infinite retry loops for permanently failed items

-- Add error_log column
ALTER TABLE stock_news
ADD COLUMN IF NOT EXISTS error_log TEXT;

-- Add index for error tracking
CREATE INDEX IF NOT EXISTS idx_stock_news_category_error
    ON stock_news(category) WHERE category IN ('UNCATEGORIZED', 'ERROR');

-- Comment
COMMENT ON COLUMN stock_news.error_log IS 'Error details when LLM categorization fails (API error code, message, etc.)';

-- Note: Items with category='ERROR' should not be re-processed to avoid infinite loops
