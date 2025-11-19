# News Fetching Backend Implementation

## Overview

This implementation provides a complete backend for fetching, storing, and processing stock news from Finnhub API. The system is designed to be easily extensible for additional news sources in the future.

## Architecture

```
fetch_news/
├── models/                  # Data models
│   ├── __init__.py
│   └── raw_news.py         # RawNewsItem, ProcessingStatus enums
│
├── fetchers/               # News fetchers
│   ├── __init__.py
│   └── finnhub_fetcher.py  # Finnhub API integration
│
├── processors/             # Data processors
│   ├── __init__.py
│   └── news_processor.py   # Convert raw JSON -> structured data
│
├── storage/                # Database operations
│   ├── __init__.py
│   └── raw_news_storage.py # stock_news_raw table operations
│
├── .env                    # Configuration (API keys, Supabase)
├── test_fetch_news.py      # Test/demo script
└── IMPLEMENTATION.md       # This file
```

## Components

### 1. Data Models (`models/raw_news.py`)

**RawNewsItem**
- Pydantic model for raw news data
- Stores both JSON and HTML raw data
- Includes processing status tracking
- Generates content hash for deduplication
- Factory method for Finnhub responses

**ProcessingStatus**
- Enum: `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`
- Tracks processing state for each raw news item

### 2. Storage Layer (`storage/raw_news_storage.py`)

**RawNewsStorage**
- Database operations for `stock_news_raw` table
- Methods:
  - `insert()` - Insert single item with duplicate checking
  - `bulk_insert()` - Insert multiple items efficiently
  - `check_duplicate()` - Check by content hash
  - `get_unprocessed()` - Fetch pending items for processing
  - `get_by_symbol()` - Get all raw news for a symbol
  - `update_processing_status()` - Update processing state
  - `delete_old_processed()` - Cleanup old data
  - `get_stats()` - Storage statistics

### 3. Fetcher (`fetchers/finnhub_fetcher.py`)

**FinnhubNewsFetcher**
- Fetches news from Finnhub API
- Uses existing `backend/app/external/finnhub_client.py`
- Methods:
  - `fetch_for_symbol()` - Fetch news for single symbol
  - `fetch_for_symbols()` - Fetch for multiple symbols
- Returns list of `RawNewsItem` objects
- Rate limit: 60 calls/minute (Finnhub free tier)

### 4. Processor (`processors/news_processor.py`)

**NewsProcessor**
- Converts raw JSON to structured format
- Pushes to `stock_news` table using LIFO stack
- Methods:
  - `_process_finnhub_json()` - Parse Finnhub format
  - `process_raw_item()` - Process single item
  - `process_unprocessed_batch()` - Batch processing
- Updates processing status in `stock_news_raw`

## Database Tables

### `stock_news_raw` (Data Lake)

Stores unprocessed news from all sources.

**Required columns:**
- `id` - UUID primary key
- `symbol` - Stock ticker
- `raw_html` - HTML from web scraping (nullable)
- `raw_json` - JSON from APIs (JSONB, nullable)
- `url` - Source URL
- `fetch_source` - API source (finnhub, polygon, etc.)
- `fetched_at` - Timestamp when fetched
- `is_processed` - Boolean flag
- `processed_at` - Timestamp when processed
- `processing_status` - TEXT (pending/processing/completed/failed)
- `error_log` - Error messages
- `metadata` - Additional data (JSONB)
- `content_hash` - MD5 hash for deduplication
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

**Indexes needed:**
```sql
CREATE INDEX idx_stock_news_raw_symbol ON stock_news_raw(symbol);
CREATE INDEX idx_stock_news_raw_unprocessed ON stock_news_raw(is_processed, created_at DESC) WHERE is_processed = FALSE;
CREATE INDEX idx_stock_news_raw_content_hash ON stock_news_raw(content_hash);
CREATE INDEX idx_stock_news_raw_status ON stock_news_raw(processing_status);
```

### `stock_news` (Production)

Existing table - stores processed news in LIFO stack (managed by `backend/app/db/stock_news.py`).

### `fetch_log` (Tracking)

**Recommended schema:**
```sql
CREATE TABLE fetch_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fetch_source TEXT NOT NULL,
    symbols TEXT[] NOT NULL,
    articles_fetched INT NOT NULL,
    articles_stored INT NOT NULL,
    articles_duplicates INT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL,  -- running/completed/failed
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fetch_log_source ON fetch_log(fetch_source);
CREATE INDEX idx_fetch_log_status ON fetch_log(status);
CREATE INDEX idx_fetch_log_created ON fetch_log(created_at DESC);
```

### `summaries` (AI Summaries)

**Recommended schema:**
```sql
CREATE TABLE summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    news_id UUID REFERENCES stock_news(id) ON DELETE CASCADE,
    summary_type TEXT NOT NULL,  -- brief/detailed/sentiment
    content TEXT NOT NULL,
    model_used TEXT,
    tokens_used INT,
    processing_time_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_summaries_news_id ON summaries(news_id);
CREATE INDEX idx_summaries_type ON summaries(summary_type);
```

## Usage

### Running the Test Script

```bash
cd fetch_news
python test_fetch_news.py
```

This will:
1. Fetch news for AAPL, TSLA, GOOGL from Finnhub (last 7 days)
2. Store raw data in `stock_news_raw` table
3. Process raw data into structured format
4. Push to `stock_news` table (LIFO stack)
5. Display statistics

### Programmatic Usage

```python
import asyncio
from supabase import create_client
from fetch_news import FinnhubNewsFetcher, RawNewsStorage, NewsProcessor
from backend.app.db.stock_news import StockNewsDB

async def fetch_and_process_news():
    # Initialize
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    fetcher = FinnhubNewsFetcher(api_key=FINNHUB_KEY)
    raw_storage = RawNewsStorage(client=supabase_client)
    stock_news_db = StockNewsDB(client=supabase_client)
    processor = NewsProcessor(stock_news_db, raw_storage)

    # Step 1: Fetch news
    raw_items = await fetcher.fetch_for_symbol("AAPL", days_back=7)

    # Step 2: Store raw
    await raw_storage.bulk_insert(raw_items)

    # Step 3: Process
    stats = await processor.process_unprocessed_batch(limit=50)

    # Cleanup
    await fetcher.close()

asyncio.run(fetch_and_process_news())
```

## Data Flow

```
1. Finnhub API
   ↓
2. FinnhubNewsFetcher
   ↓ (RawNewsItem objects)
3. RawNewsStorage.insert()
   ↓ (store in stock_news_raw)
4. NewsProcessor.process_raw_item()
   ↓ (extract & structure data)
5. StockNewsDB.push_news_to_stack()
   ↓ (store in stock_news table)
6. Done!
```

## Deduplication Strategy

### Level 1: Raw Data
- Check `content_hash` (MD5 of URL) before inserting
- Skip duplicates in `stock_news_raw`

### Level 2: Processed Data
- Future: Check URL exists in `stock_news` before pushing
- Skip duplicates in production table

## Error Handling

- Failed fetches: Logged but don't stop pipeline
- Failed processing: Marked with `processing_status='failed'` and `error_log`
- Can retry failed items by setting status back to `pending`

## Extension Points

### Adding New News Sources

1. **Create new fetcher** (`fetchers/polygon_fetcher.py`):
```python
class PolygonNewsFetcher:
    async def fetch_for_symbol(self, symbol, days_back):
        # Fetch from Polygon API
        # Return List[RawNewsItem]
        pass
```

2. **Update processor** (`processors/news_processor.py`):
```python
def _process_polygon_json(self, raw_json, symbol):
    # Parse Polygon format
    pass
```

3. **Use in main flow**:
```python
polygon_fetcher = PolygonNewsFetcher(api_key=KEY)
raw_items = await polygon_fetcher.fetch_for_symbol("AAPL")
await raw_storage.bulk_insert(raw_items)
```

### Adding Web Scraping

1. Create `fetchers/web_scraper.py`
2. Store HTML in `raw_html` field
3. Add HTML parser in processor
4. Extract structured data with BeautifulSoup

### Adding Sentiment Analysis

1. Modify `NewsProcessor._process_finnhub_json()`
2. Add sentiment calculation before pushing to `stock_news`
3. Store in `processed_data['sentiment_score']`

## Performance Considerations

- **Batch inserts**: Use `bulk_insert()` for multiple items
- **Async throughout**: All operations are async
- **Rate limiting**: Respect API limits (60/min for Finnhub)
- **Deduplication**: Fast hash-based duplicate detection
- **Pagination**: Process in batches (e.g., 50 items at a time)

## Future Enhancements

1. **Fetch log tracking**: Record all fetch operations
2. **Scheduled updates**: Daily/hourly fetch jobs
3. **Watchlist integration**: Fetch for user watchlist symbols
4. **Summary generation**: AI summaries stored in `summaries` table
5. **Retry logic**: Automatic retry for failed fetches
6. **Metrics dashboard**: Track fetch success rates, processing times
7. **Multiple sources**: Polygon, NewsAPI, YFinance
8. **Web scraping**: Reuters, Bloomberg, MarketWatch

## Testing Checklist

Before running:
- [ ] Supabase `stock_news_raw` table exists with correct schema
- [ ] Supabase `stock_news` table exists
- [ ] `FINNHUB_API_KEY` in `.env`
- [ ] `SUPABASE_NEWS_URL` and `SUPABASE_NEWS_KEY` in `.env`
- [ ] Dependencies installed: `supabase`, `httpx`, `pydantic`, `python-dotenv`

After running:
- [ ] Check `stock_news_raw` table for raw entries
- [ ] Check processing statuses are updated
- [ ] Check `stock_news` table for processed articles
- [ ] Verify LIFO stack positions (1-5)
- [ ] Check for duplicates (should be skipped)

## Troubleshooting

**No news fetched:**
- Check Finnhub API key is valid
- Verify symbol is correct ticker
- Check date range (default: last 7 days)
- Review Finnhub rate limits

**Insert failed:**
- Check Supabase credentials
- Verify table schema matches model
- Check for missing required fields

**Processing failed:**
- Review `error_log` column in `stock_news_raw`
- Check `stock_news` table schema
- Verify source_id mapping (may be null)

## Dependencies

```bash
pip install supabase httpx pydantic python-dotenv
```

Or use existing project dependencies (already installed in backend).

## Contact

For questions or issues, check the main README.md or review the code comments.
