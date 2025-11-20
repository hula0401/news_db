# Change Records

## 2025-11-18 15:00: Refactored news_db from news_agent submodule to standalone repository
Created UV-based environment, removed backend dependencies, implemented standalone modules.

## 2025-11-18 15:30: Created migration scripts for existing stock_news table
Analyzed current schema and generated adjustment queries for LIFO stack compatibility.

## 2025-11-18 16:00: Fixed DROP INDEX error in migration script
Changed from DROP INDEX to ALTER TABLE DROP CONSTRAINT for constraint-backed index.

---

## Session 1: Initial Refactoring (2025-11-18)

### Files Created:
- `.gitignore` - Python project ignore rules
- `pyproject.toml` - UV project configuration
- `db/stock_news.py` - Standalone StockNewsDB class
- `schema_stock_news.sql` - Stock news table schema
- `SETUP.md` - Installation and setup guide

### Files Modified:
- `fetchers/finnhub_fetcher.py` - Removed backend imports, standalone FinnhubClient
- `processors/news_processor.py` - Uses local StockNewsDB
- `storage/raw_news_storage.py` - Absolute imports
- `test_fetch_news.py` - Local imports
- All `__init__.py` files - Absolute imports
- `README.md` - Updated usage examples

### Key Changes:
- Replaced `backend.app.*` imports → standalone implementations
- Relative imports → absolute imports
- Created LIFO stack implementation in StockNewsDB
- Set up UV environment with all dependencies

### Test Result:
✅ Successfully fetched 60 articles from Finnhub and stored in Supabase

---

## Session 2: Schema Migration (2025-11-18)

### Files Created:
- `adjust_stock_news_table.sql` - Migration script for existing table
- `check_stock_news_schema.sql` - Schema inspection queries
- `docs/FIX_Database_Docs.md` - Database fix documentation
- `docs/RECORD_Change.md` - This file

### Schema Analysis:
- Current table has 11 columns, needs 4 more
- Has `position_in_stack` (critical for LIFO)
- Missing: source_id, external_id, metadata, updated_at
- Index issue: UNIQUE on url (should be symbol+url)

### Fix Applied:
- Changed `DROP INDEX` → `ALTER TABLE DROP CONSTRAINT` (line 64)
- Properly handles constraint-backed unique index

## 2025-11-18 16:15: Investigated processing limit and failures
Test script only processes 10 items at a time; created test_process_all.py to handle all pending items.

### Issue Identified:
- `test_fetch_news.py` has `limit=10` on line 120
- Only first 10 pending items (all AAPL) were processed
- TSLA and GOOGL remain unprocessed (pending)
- 10 items failed processing (need to check error_log)

### Files Created:
- `check_failed_items.sql` - Query to check failed processing errors
- `test_process_all.py` - Process all pending items in batches

### Next Steps:
1. Run `check_failed_items.sql` to see why 10 items failed
2. Run `test_process_all.py` to process remaining items

## 2025-11-18 16:30: Added Polygon as second news source
Implemented PolygonNewsFetcher with full integration for fetching, storing, and processing news.

### Files Created:
- `fetchers/polygon_fetcher.py` - Polygon.io API client and fetcher
- `test_multi_source.py` - Test script for both Finnhub and Polygon

### Files Modified:
- `models/raw_news.py` - Added `from_polygon_response()` method
- `processors/news_processor.py` - Added `_process_polygon_json()` method
- `fetchers/__init__.py` - Export PolygonNewsFetcher

### Implementation Details:
- Polygon API endpoint: `/v2/reference/news`
- API key env var: `MASSIVE_API_KEY`
- Response format: ISO 8601 timestamps, different field names than Finnhub
- Rate limit handling: 200ms delay between requests (5 req/min free tier)
- Metadata stored: author, publisher, image_url, amp_url, tickers list

### Usage:
```bash
uv run python test_multi_source.py
```

## 2025-11-18 16:45: Created today's news fetcher with configurable symbols
Added dynamic test script that fetches only today's news with configurable symbol list.

### Files Created:
- `test_today_news.py` - Fetch today's news only (dynamic date)
- `config.py` - Centralized configuration for symbols and fetch settings

### Features:
- **Dynamic date:** Always fetches from today (00:00:00 to current time)
- **Configurable symbols:** Edit `config.py` to change which symbols to fetch
- **Both sources:** Fetches from Finnhub and Polygon
- **Auto-process:** Processes all pending items automatically
- **Summary view:** Shows news stacks with source and publisher info

### Configuration:
Edit `config.py` to customize:
- `DEFAULT_SYMBOLS` - List of symbols to fetch
- `FETCH_CONFIG` - Fetch and processing settings
- Predefined lists: `TOP_STOCKS`, `TECH_STOCKS`

### Usage:
```bash
uv run python test_today_news.py
```

Runs daily to fetch latest news for configured symbols.

## 2025-11-18 17:00: Implemented incremental fetching with timestamp tracking
Created production-ready incremental fetching system to avoid re-fetching old news.

### Files Created:
- `schema_fetch_state.sql` - Tracks last fetch timestamp per symbol+source
- `storage/fetch_state_manager.py` - Manages fetch state and incremental windows
- `fetch_incremental.py` - Production incremental fetcher

### How It Works:
1. **First run:** Fetches last 7 days of news, stores timestamp
2. **Subsequent runs:** Fetches only from (last_timestamp - 1min) to now
3. **Buffer window:** 1-minute overlap prevents missing news
4. **Duplicate check:** Still active as safety net

### Key Features:
- **Timestamp tracking:** Per symbol+source combination
- **Automatic incremental:** No manual configuration needed
- **Buffer window:** Configurable overlap (default 1 minute)
- **Stale detection:** Find symbols that haven't been fetched recently
- **Reset capability:** Force full refresh when needed

### Database Schema:
- `fetch_state` table: Tracks last_fetch_from, last_fetch_to
- `v_fetch_state_status` view: Shows time since last fetch
- Unique constraint on (symbol, fetch_source)

### Production Benefits:
- **Efficiency:** Only fetch new news, not entire history
- **API savings:** Reduce API calls dramatically
- **Speed:** Faster execution (fewer items to check)
- **Scalability:** Can run frequently (every 5-15 minutes)

### Usage:
```bash
# Run schema first (one time)
cat schema_fetch_state.sql | supabase sql

# Run incremental fetch
uv run python fetch_incremental.py
```

### Performance:
- First run: ~7 days of news
- Subsequent runs: Only last few minutes/hours
- Duplicate checking: Still active but processes fewer items

## 2025-11-18 17:15: Changed first run to fetch last 24 hours instead of 7 days
Modified default fetch window for first run from 7 days to 1 day (yesterday only).

### Change:
- `fetch_state_manager.py` line 49: Changed from `timedelta(days=7)` to `timedelta(days=1)`
- First run now fetches last 24 hours instead of full week
- Reduces initial fetch volume while still getting recent news
