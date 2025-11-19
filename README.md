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
backend/app/news_engine/
├── __init__.py              # Main exports
├── engine.py                # NewsEngine orchestrator
├── README.md                # This file
│
├── models/                  # Data models
│   ├── __init__.py
│   ├── raw_news.py         # RawNewsItem, ProcessingStatus
│   └── processed_news.py   # ProcessedNewsItem
│
├── fetchers/               # News fetching
│   ├── __init__.py
│   ├── api_fetcher.py      # APINewsFetcher (Finnhub, Polygon, etc.)
│   └── watchlist_fetcher.py # WatchlistNewsFetcher (user watchlists + top 10)
│
├── processors/             # Data processing
│   ├── __init__.py
│   └── news_processor.py   # NewsProcessor (HTML/JSON → structured)
│
└── storage/                # Database operations
    ├── __init__.py
    ├── raw_news_storage.py       # RawNewsStorage (stock_news_raw table)
    └── processed_news_storage.py # ProcessedNewsStorage (stock_news table)
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

## Usage

### Basic Usage

```python
from app.database import db_manager
from app.news_engine import NewsEngine

# Initialize
await db_manager.initialize()
engine = NewsEngine(db_manager.client)

# Run daily update (all watchlists + top 10 companies)
stats = await engine.run_daily_update(
    days_back=1,                    # Last 24 hours
    include_top_companies=True,     # Include top 10
    process_immediately=True        # Process right away
)

# Stats:
# {
#     'symbols_fetched': 25,
#     'raw_news_fetched': 150,
#     'raw_news_stored': 120,      # 30 duplicates skipped
#     'raw_news_processed': 120,
#     'processed_news_stored': 115, # 5 duplicates in stock_news
#     'errors': [],
#     'duration_seconds': 45.2
# }
```

### Fetch for Single Symbol

```python
# Fetch news for AAPL (last 7 days)
result = await engine.fetch_news_for_symbol(
    symbol="AAPL",
    days_back=7,
    store_raw=True,
    process_immediately=True
)
# Returns: {'symbol': 'AAPL', 'fetched': 15, 'stored': 12, 'processed': 10}
```

### Process Unprocessed News

```python
# Process up to 100 unprocessed raw news items
stats = await engine.process_unprocessed_news(limit=100)
# Returns: {'fetched': 50, 'processed': 45, 'stored': 40, 'failed': 5}
```

### Get Statistics

```python
stats = engine.get_stats()
# Returns:
# {
#     'raw_storage': {
#         'total': 500,
#         'pending': 10,
#         'processing': 0,
#         'completed': 480,
#         'failed': 10
#     },
#     'watchlist': {
#         'total_users': 50,
#         'users_with_watchlist': 35,
#         'unique_symbols': 25,
#         'symbols': ['AAPL', 'TSLA', ...],
#         'top_companies': ['AAPL', 'MSFT', ...]
#     }
# }
```

## Components

### 1. NewsEngine (engine.py)

Main orchestrator that coordinates all components.

**Key Methods:**
- `run_daily_update()` - Main scheduled job entry point
- `fetch_news_for_symbol()` - Fetch for single symbol
- `process_unprocessed_news()` - Process raw data
- `get_stats()` - Get comprehensive statistics

### 2. APINewsFetcher (fetchers/api_fetcher.py)

Fetches news from external APIs.

**Supported APIs:**
- **Finnhub**: 60 calls/min, company news
- **Polygon**: 5 calls/min, ticker news
- **NewsAPI**: 100 calls/day, market news
- **YFinance**: Unlimited, stock news

**Key Methods:**
- `fetch_for_symbol()` - Fetch from all APIs for one symbol
- `fetch_for_symbols()` - Concurrent fetch for multiple symbols
- `fetch_market_news()` - General market news (NewsAPI)

### 3. WatchlistNewsFetcher (fetchers/watchlist_fetcher.py)

Fetches news for user watchlists + top companies.

**Top 10 Companies:**
AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META, BRK.B, V, JPM

**Key Methods:**
- `get_all_watchlist_symbols()` - Get symbols from all users
- `get_target_symbols()` - Watchlist + top 10
- `fetch_news_for_watchlists()` - Fetch for all symbols
- `fetch_news_for_user()` - Fetch for single user
- `get_stats()` - Watchlist statistics

### 4. NewsProcessor (processors/news_processor.py)

Converts raw HTML/JSON to structured format.

**Capabilities:**
- Parse Finnhub, Polygon, YFinance, NewsAPI JSON formats
- Extract structured data from HTML (BeautifulSoup)
- Extract title, summary, publish date, source
- Fallback to metadata tags (og:title, twitter:card, etc.)

**Key Methods:**
- `process_raw_item()` - Process single RawNewsItem
- `process_batch()` - Process multiple items

### 5. RawNewsStorage (storage/raw_news_storage.py)

Database operations for stock_news_raw table.

**Key Methods:**
- `insert()` - Insert single raw news item
- `bulk_insert()` - Insert multiple items
- `get_unprocessed()` - Get pending items
- `get_by_status()` - Filter by processing status
- `get_by_symbol()` - Get all raw news for symbol
- `update_processing_status()` - Update status
- `check_duplicate()` - Check if content_hash exists
- `delete_old_processed()` - Cleanup old data
- `get_stats()` - Storage statistics

### 6. ProcessedNewsStorage (storage/processed_news_storage.py)

Database operations for stock_news table (wraps existing StockNewsDB).

**Key Methods:**
- `push_to_stack()` - Push to LIFO stack (position 1)
- `get_news_stack()` - Get news stack (positions 1-5)
- `check_duplicate_url()` - Check if URL exists

## Scheduler Integration

The data engine is integrated with the existing scheduler in `backend/app/scheduler/scheduler_manager.py`.

**Job Configuration:**
```python
# Runs daily at midnight (00:00)
scheduler.add_job(
    _news_engine_daily_update,
    trigger=CronTrigger(hour=0, minute=0),
    id='news_engine_daily_update',
    name='Data Engine Daily Update',
    max_instances=1
)
```

**What it does:**
1. Fetches news for all user watchlists
2. Includes top 10 popular companies
3. Stores raw data in stock_news_raw
4. Processes immediately
5. Stores in stock_news table
6. Logs statistics

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
