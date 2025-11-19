# News DB Setup Guide

This document explains the changes made to convert this from a submodule of the news_agent project to a standalone repository.

## What Was Changed

### 1. Infrastructure Files Created

- **`.gitignore`**: Standard Python gitignore to exclude virtual environments, cache files, etc.
- **`pyproject.toml`**: UV-based project configuration with all dependencies
- **`schema_stock_news.sql`**: Additional schema for the `stock_news` table (run this if the table doesn't exist in your Supabase)

### 2. New Standalone Modules

- **`db/stock_news.py`**: Standalone implementation of `StockNewsDB` class
  - Replaced import from `backend.app.db.stock_news`
  - Implements LIFO stack for storing processed news
  - Methods: `push_news_to_stack()`, `get_news_stack()`, `check_duplicate_url()`

### 3. Updated Import Structure

All imports were changed from relative imports (e.g., `from ..models.raw_news`) to absolute imports (e.g., `from models.raw_news`) to work as standalone modules.

**Files updated:**
- `fetchers/finnhub_fetcher.py`: Removed backend dependency, uses standalone FinnhubClient
- `processors/news_processor.py`: Updated to use standalone StockNewsDB
- `storage/raw_news_storage.py`: Updated imports
- `test_fetch_news.py`: Updated to use local imports instead of backend imports
- All `__init__.py` files: Updated to use absolute imports

## Installation

### 1. Install UV (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Sync Dependencies

```bash
uv sync
```

This will:
- Create a virtual environment in `.venv/`
- Install all dependencies (supabase, httpx, pydantic, python-dotenv)
- Install dev dependencies (pytest, pytest-asyncio)

## Database Setup

### 1. Run the Main Schema

If you haven't already, run `schema.sql` in your Supabase SQL editor to create:
- `stock_news_raw` table
- `fetch_log` table
- `summaries` table
- Supporting views and functions

### 2. Run the Stock News Schema

Run `schema_stock_news.sql` in your Supabase SQL editor to create:
- `stock_news` table (if it doesn't exist)
- Supporting indexes
- Helper function `increment_news_positions()`

## Environment Variables

Ensure your `.env` file contains:

```env
SUPABASE_NEWS_URL=<your_supabase_url>
SUPABASE_NEWS_KEY=<your_supabase_anon_key>
FINNHUB_API_KEY=<your_finnhub_api_key>
```

## Running the Test

```bash
uv run python test_fetch_news.py
```

This will:
1. Fetch news for AAPL, TSLA, GOOGL from Finnhub (last 7 days)
2. Store raw news in `stock_news_raw` table
3. Process raw news and store in `stock_news` table
4. Display statistics and news stacks

## Project Structure

```
news_db/
├── models/              # Data models (RawNewsItem, ProcessingStatus)
├── fetchers/           # News fetchers (FinnhubNewsFetcher)
├── processors/         # News processors (NewsProcessor)
├── storage/            # Storage layer (RawNewsStorage)
├── db/                 # Database operations (StockNewsDB)
├── test_fetch_news.py  # Test script
├── schema.sql          # Main database schema
├── schema_stock_news.sql  # Stock news table schema
├── pyproject.toml      # Project configuration
├── .env                # Environment variables (not in git)
└── .gitignore          # Git ignore rules
```

## Usage

### Basic Fetch Example

```python
from supabase import create_client
from fetchers.finnhub_fetcher import FinnhubNewsFetcher
from storage.raw_news_storage import RawNewsStorage
import os

# Initialize
supabase = create_client(os.getenv("SUPABASE_NEWS_URL"), os.getenv("SUPABASE_NEWS_KEY"))
fetcher = FinnhubNewsFetcher(api_key=os.getenv("FINNHUB_API_KEY"))
storage = RawNewsStorage(client=supabase)

# Fetch and store
raw_items = await fetcher.fetch_for_symbol("AAPL", days_back=7)
stats = await storage.bulk_insert(raw_items)
print(f"Inserted {stats['inserted']} articles")
```

### Process Raw News

```python
from processors.news_processor import NewsProcessor
from db.stock_news import StockNewsDB

# Initialize
stock_news_db = StockNewsDB(client=supabase)
processor = NewsProcessor(stock_news_db=stock_news_db, raw_storage=storage)

# Process unprocessed news
stats = await processor.process_unprocessed_batch(limit=50)
print(f"Processed {stats['processed']} articles")
```

## Dependencies

### Production
- `supabase>=2.10.0`: Supabase client for database operations
- `httpx>=0.28.1`: HTTP client for API requests
- `pydantic>=2.10.5`: Data validation and models
- `python-dotenv>=1.0.1`: Environment variable management

### Development
- `pytest>=8.3.4`: Testing framework
- `pytest-asyncio>=0.25.2`: Async testing support

## Notes

- The `stock_news` table uses a LIFO stack (positions 1-5)
- Deduplication happens at two levels:
  1. Raw data: by content_hash (MD5 of URL)
  2. Processed data: by URL within each symbol
- The test script is fully functional and fetches real data from Finnhub
- All modules use async/await for better performance

## Next Steps

1. Add more news sources (Polygon, NewsAPI, YFinance)
2. Implement sentiment analysis
3. Add scheduled jobs for automated fetching
4. Create API endpoints for accessing the data

## Troubleshooting

### Import Errors
If you get import errors, make sure you're running commands with `uv run`:
```bash
uv run python your_script.py
```

### Database Connection Issues
- Verify your Supabase URL and key in `.env`
- Check that tables exist by running the schema files
- Ensure your Supabase project is active

### API Rate Limits
- Finnhub free tier: 60 calls/minute
- The fetcher limits to 20 articles per call
- Consider adding delays for large batches
