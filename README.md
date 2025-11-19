# Data Engine

Automated news fetching, processing, and storage system for the Talkative stock news platform.

## Overview

The Data Engine provides a complete pipeline for:
1. **Fetching news** from multiple sources (APIs + web scraping)
2. **Storing raw data** in a data lake (stock_news_raw table)
3. **Processing** raw HTML/JSON into structured format
4. **Storing processed data** in the stock_news table
5. **Scheduled updates** running daily for all user watchlists

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Data Engine Flow                        │
└─────────────────────────────────────────────────────────────┘

1. FETCH (APIs/Web Scraping)
   ├─ Finnhub API (60 calls/min)
   ├─ Polygon API (5 calls/min)
   ├─ NewsAPI (100 calls/day)
   ├─ YFinance (unlimited)
   └─ Future: Reuters, Bloomberg scraping

2. STORE RAW (Data Lake)
   └─ stock_news_raw table
      ├─ raw_html (web scraping)
      ├─ raw_json (API responses)
      ├─ metadata (API limits, versions)
      └─ processing_status (pending/processing/completed/failed)

3. PROCESS (HTML/JSON → Structured)
   ├─ Extract title, summary, date, source
   ├─ Parse different API response formats
   ├─ Parse HTML with BeautifulSoup
   └─ Deduplicate by URL hash

4. STORE PROCESSED (Production Data)
   └─ stock_news table (LIFO stack)
      ├─ Top 5 news per symbol
      ├─ Auto-archive position 6+
      └─ Sentiment analysis ready

5. SCHEDULE
   └─ Daily at midnight
      ├─ Fetch news for all watchlists
      ├─ Include top 10 popular companies
      └─ Process immediately
```

## Directory Structure

```
news_db/
├── __init__.py              # Main exports
├── README.md                # This file
├── SETUP.md                 # Setup and installation guide
├── test_fetch_news.py       # Test script
├── schema.sql               # Main database schema
├── schema_stock_news.sql    # Stock news table schema
├── pyproject.toml           # UV project configuration
├── .env                     # Environment variables (not in git)
│
├── models/                  # Data models
│   ├── __init__.py
│   └── raw_news.py         # RawNewsItem, ProcessingStatus
│
├── fetchers/               # News fetching
│   ├── __init__.py
│   └── finnhub_fetcher.py  # FinnhubNewsFetcher (Finnhub API)
│
├── processors/             # Data processing
│   ├── __init__.py
│   └── news_processor.py   # NewsProcessor (HTML/JSON → structured)
│
├── storage/                # Database operations
│   ├── __init__.py
│   └── raw_news_storage.py # RawNewsStorage (stock_news_raw table)
│
└── db/                     # Database layer
    ├── __init__.py
    └── stock_news.py       # StockNewsDB (stock_news table)
```

## Database Schema

### stock_news_raw (Data Lake)

Stores unprocessed news data from all sources.

```sql
CREATE TABLE stock_news_raw (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,                    -- Stock ticker
    raw_html TEXT,                           -- HTML from web scraping
    raw_json JSONB,                          -- JSON from APIs
    url TEXT NOT NULL,                       -- Source URL
    fetch_source TEXT NOT NULL,              -- finnhub, polygon, reuters, etc.
    fetched_at TIMESTAMPTZ NOT NULL,         -- When fetched
    is_processed BOOLEAN DEFAULT FALSE,      -- Processing flag
    processed_at TIMESTAMPTZ,                -- When processed
    processing_status TEXT DEFAULT 'pending', -- pending/processing/completed/failed
    error_log TEXT,                          -- Error messages
    metadata JSONB DEFAULT '{}'::jsonb,      -- Additional metadata
    content_hash TEXT,                       -- Deduplication hash
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Key indexes
CREATE INDEX idx_stock_news_raw_symbol ON stock_news_raw(symbol);
CREATE INDEX idx_stock_news_raw_unprocessed ON stock_news_raw(is_processed, created_at DESC) WHERE is_processed = FALSE;
CREATE INDEX idx_stock_news_raw_content_hash ON stock_news_raw(content_hash);
```

### stock_news (Production)

Stores processed, structured news (existing table, LIFO stack).

## Installation

### Quick Start

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync

# Run the schema files in your Supabase SQL editor
# 1. schema.sql
# 2. schema_stock_news.sql

# Configure .env file with your credentials
SUPABASE_NEWS_URL=<your_url>
SUPABASE_NEWS_KEY=<your_key>
FINNHUB_API_KEY=<your_key>

# Run test
uv run python test_fetch_news.py
```

See [SETUP.md](SETUP.md) for detailed installation and configuration instructions.

## Usage

### Basic Usage

```python
import os
from supabase import create_client
from fetchers.finnhub_fetcher import FinnhubNewsFetcher
from storage.raw_news_storage import RawNewsStorage
from processors.news_processor import NewsProcessor
from db.stock_news import StockNewsDB

# Initialize Supabase client
supabase = create_client(
    os.getenv("SUPABASE_NEWS_URL"),
    os.getenv("SUPABASE_NEWS_KEY")
)

# Initialize components
fetcher = FinnhubNewsFetcher(api_key=os.getenv("FINNHUB_API_KEY"))
raw_storage = RawNewsStorage(client=supabase)
stock_news_db = StockNewsDB(client=supabase)
processor = NewsProcessor(stock_news_db=stock_news_db, raw_storage=raw_storage)
```

### Fetch for Single Symbol

```python
# Fetch news for AAPL (last 7 days)
raw_items = await fetcher.fetch_for_symbol(symbol="AAPL", days_back=7)
stats = await raw_storage.bulk_insert(raw_items)
print(f"Fetched: {len(raw_items)}, Stored: {stats['inserted']}")
```

### Process Unprocessed News

```python
# Process up to 100 unprocessed raw news items
stats = await processor.process_unprocessed_batch(limit=100)
print(f"Processed: {stats['processed']}, Failed: {stats['failed']}")
```

### Get Statistics

```python
# Get raw storage statistics
stats = await raw_storage.get_stats()
print(f"Total: {stats['total']}, Pending: {stats['pending']}")

# Get stock news statistics
news_stats = await stock_news_db.get_stats()
print(f"Total processed news: {news_stats['total']}")
```

## Components

### 1. FinnhubNewsFetcher (fetchers/finnhub_fetcher.py)

Fetches news from Finnhub API.

**Supported API:**
- **Finnhub**: 60 calls/min, company news

**Key Methods:**
- `fetch_for_symbol()` - Fetch news for one symbol
- `fetch_for_symbols()` - Fetch for multiple symbols

### 2. NewsProcessor (processors/news_processor.py)

Converts raw HTML/JSON to structured format.

**Capabilities:**
- Parse Finnhub JSON format
- Extract structured data (title, summary, date, source)
- Convert raw data to processed format

**Key Methods:**
- `process_raw_item()` - Process single raw news item
- `process_unprocessed_batch()` - Process multiple items

### 3. RawNewsStorage (storage/raw_news_storage.py)

Database operations for stock_news_raw table.

**Key Methods:**
- `insert()` - Insert single raw news item
- `bulk_insert()` - Insert multiple items
- `get_unprocessed()` - Get pending items
- `get_by_symbol()` - Get all raw news for symbol
- `update_processing_status()` - Update status
- `check_duplicate()` - Check if content_hash exists
- `delete_old_processed()` - Cleanup old data
- `get_stats()` - Storage statistics

### 4. StockNewsDB (db/stock_news.py)

Database operations for stock_news table.

**Key Methods:**
- `push_news_to_stack()` - Push to LIFO stack (position 1)
- `get_news_stack()` - Get news stack (positions 1-5)
- `check_duplicate_url()` - Check if URL exists
- `get_stats()` - Get storage statistics

## Testing

### Manual Test Script

```bash
# Run manual test
uv run python test_news_engine.py
```

This tests:
1. Watchlist statistics
2. Single symbol fetch (AAPL)
3. Raw storage stats
4. Processing unprocessed news
5. Mini daily update (2 symbols)
6. Final statistics

### Unit Tests

```bash
# Run unit tests
uv run python -m pytest tests/backend/news_engine/ -v
```

Tests include:
- NewsProcessor for all API formats
- RawNewsItem model validation
- Content hash generation
- Processing state management
- Batch processing

## Deduplication Strategy

### Level 1: Raw Data (stock_news_raw)

Deduplication by `content_hash` (MD5 of URL):
- Check before insert
- Skip if hash exists
- Prevents duplicate fetches

### Level 2: Processed Data (stock_news)

Deduplication by URL:
- Check before pushing to stack
- Skip if URL exists
- Prevents duplicate articles in production

## Error Handling

### Processing Failures

Items that fail processing are marked with:
- `processing_status = 'failed'`
- `error_log` contains error message
- Can be retried or inspected manually

### Fetch Failures

API fetch failures:
- Logged but don't stop the pipeline
- Other sources continue
- Partial results are still stored

## Data Retention

### Raw Data Cleanup

```python
# Delete processed raw news older than 30 days
deleted_count = engine.raw_storage.delete_old_processed(days=30)
```

Keeps the data lake clean while preserving recent data for inspection.

## Performance Considerations

### Concurrent Fetching

The engine fetches news concurrently:
- Multiple symbols in parallel
- Multiple APIs per symbol in parallel
- Async/await throughout

### Rate Limiting

Respects API rate limits:
- Finnhub: 60 calls/min
- Polygon: 5 calls/min
- NewsAPI: 100 calls/day
- YFinance: No limit

### Caching

Processed news is cached in Redis (2-minute TTL) by the existing stock news service.

## Future Enhancements

1. **Web Scraping**
   - Add Reuters scraper
   - Add Bloomberg scraper
   - Add MarketWatch scraper

2. **Sentiment Analysis**
   - Process sentiment scores during processing
   - Store in stock_news table
   - Use for filtering and ranking

3. **Category Classification**
   - Auto-categorize news (earnings, product launch, etc.)
   - Machine learning classification
   - Tag with topics

4. **Smart Scheduling**
   - Fetch more frequently for active trading hours
   - Reduce frequency after hours
   - Prioritize high-volume watchlist symbols

5. **News Trends**
   - Detect trending topics
   - Alert on breaking news
   - Cross-symbol correlation

## Troubleshooting

### "No news fetched"

Check:
1. API keys are configured (env_files/)
2. Network connectivity
3. API rate limits not exceeded
4. Symbols are valid tickers

### "Processing failed"

Check:
1. Raw data format matches expected schema
2. Required fields (title, URL) are present
3. Date parsing succeeded
4. Error log in stock_news_raw table

### "Duplicates not being skipped"

Check:
1. content_hash is being generated
2. Index on content_hash exists
3. URL format is consistent (http vs https, trailing slash)

## Support

For issues or questions:
1. Check logs in scheduler output
2. Query stock_news_raw table for error_log
3. Run test_news_engine.py for diagnostics
4. Check API client documentation

## License

Internal use only.
