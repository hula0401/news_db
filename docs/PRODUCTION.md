# Production Deployment Guide

## Incremental Fetching System

This system tracks the last fetch timestamp for each symbol+source combination and only fetches new news since the last run.

### How It Works

```
First Run:
  Last fetch: None
  Fetches: Last 7 days
  Stores: 2024-11-18 17:00:00 as last_fetch_to

Second Run (15 minutes later):
  Last fetch: 2024-11-18 17:00:00
  Fetches: From 2024-11-18 16:59:00 to 2024-11-18 17:15:00
  Buffer: -1 minute (16:59 instead of 17:00)
  Stores: 2024-11-18 17:15:00 as last_fetch_to

Third Run:
  Fetches: Only news from 17:14 to now
  And so on...
```

### Setup (One Time)

1. **Run the fetch_state schema:**
```bash
# In Supabase SQL Editor, run:
cat schema_fetch_state.sql
```

This creates:
- `fetch_state` table
- `v_fetch_state_status` view
- Necessary indexes and triggers

2. **Configure symbols in config.py:**
```python
DEFAULT_SYMBOLS = [
    "AAPL", "TSLA", "GOOGL", "MSFT", "NVDA"
]
```

### Daily Usage

#### Option 1: Run Manually
```bash
uv run python fetch_incremental.py
```

#### Option 2: Cron Job (Recommended)
```bash
# Every 15 minutes during market hours (9:30 AM - 4:00 PM ET)
*/15 9-16 * * 1-5 cd /path/to/news_db && /path/to/uv run python fetch_incremental.py >> logs/fetch.log 2>&1

# Every hour after hours
0 * * * * cd /path/to/news_db && /path/to/uv run python fetch_incremental.py >> logs/fetch.log 2>&1
```

#### Option 3: Scheduled Task (Cloud)
- AWS Lambda / EventBridge
- Google Cloud Scheduler
- Azure Functions

### Monitoring

#### Check fetch status:
```sql
-- View all fetch states
SELECT * FROM v_fetch_state_status;

-- Find stale fetches (not updated in 24h)
SELECT
    symbol,
    fetch_source,
    time_since_last_fetch
FROM v_fetch_state_status
WHERE time_since_last_fetch > INTERVAL '24 hours';

-- Stats by source
SELECT
    fetch_source,
    COUNT(*) as symbols,
    AVG(articles_fetched) as avg_articles,
    MAX(last_fetch_to) as latest_fetch
FROM fetch_state
GROUP BY fetch_source;
```

### Troubleshooting

#### Reset fetch state (force full refresh):
```python
from storage.fetch_state_manager import FetchStateManager

# Reset specific symbol
await fetch_state.reset_fetch_state(symbol="AAPL")

# Reset specific source
await fetch_state.reset_fetch_state(fetch_source="polygon")

# Reset symbol+source combo
await fetch_state.reset_fetch_state(symbol="AAPL", fetch_source="finnhub")
```

#### Or via SQL:
```sql
-- Reset AAPL from all sources
DELETE FROM fetch_state WHERE symbol = 'AAPL';

-- Reset all Polygon fetches
DELETE FROM fetch_state WHERE fetch_source = 'polygon';

-- Reset everything (CAUTION!)
TRUNCATE fetch_state;
```

### Configuration Options

Edit `fetch_incremental.py` to customize:

```python
# Buffer window (overlap to prevent missing news)
fetcher = IncrementalFetcher(
    ...
    buffer_minutes=1  # Increase if missing news, decrease if too many dupes
)

# Symbols to fetch
symbols = DEFAULT_SYMBOLS  # Or custom list

# Processing batch size
processor.process_unprocessed_batch(limit=100)
```

### Performance Metrics

| Scenario | First Run | Subsequent Runs |
|----------|-----------|-----------------|
| **Time Range** | 7 days | Last 15-60 min |
| **Articles/Symbol** | ~100-200 | ~5-20 |
| **API Calls** | ~10 per source | ~2 per source |
| **Duration** | ~30-60s | ~10-20s |
| **Duplicates** | High | Very low |

### Best Practices

1. **Run Frequency:**
   - Market hours: Every 15-30 minutes
   - After hours: Every 1-2 hours
   - Weekends: Every 6-12 hours

2. **Buffer Window:**
   - Use 1 minute for high-frequency updates
   - Use 5 minutes if API is slow/unreliable
   - Use 10 minutes if you run infrequently

3. **Monitoring:**
   - Check `v_fetch_state_status` daily
   - Alert if any symbol hasn't updated in 24h
   - Monitor failed processing count

4. **Cleanup:**
   - Keep fetch_state table indefinitely (small)
   - Clean old processed stock_news_raw (>30 days)
   - Archive old stock_news entries

### Integration with Existing Systems

#### With test_today_news.py:
```bash
# Run incremental fetch first
uv run python fetch_incremental.py

# Then process any remaining
uv run python test_today_news.py
```

#### With custom scripts:
```python
from storage.fetch_state_manager import FetchStateManager

# Get last fetch time
from_time, to_time = await fetch_state.get_last_fetch_time(
    symbol="AAPL",
    fetch_source="finnhub",
    buffer_minutes=1
)

# Fetch using that window
items = await fetcher.fetch_for_symbol(...)

# Update state after successful fetch
await fetch_state.update_fetch_state(
    symbol="AAPL",
    fetch_source="finnhub",
    from_time=from_time,
    to_time=to_time,
    articles_fetched=len(items),
    articles_stored=stored_count
)
```

### API Rate Limits

With incremental fetching, you stay well within limits:

| Source | Rate Limit | Incremental Usage |
|--------|------------|-------------------|
| **Finnhub** | 60 req/min | ~10 req/run |
| **Polygon** | 5 req/min | ~10 req/run |

Running every 15 minutes = ~40 Finnhub calls/hour (well under 60/min)

### Cost Savings

Assuming 10 symbols, 2 sources, running every 15 minutes:

**Without incremental fetching:**
- 10 symbols × 2 sources × 4 runs/hour = 80 API calls/hour
- Each call fetches ~100 articles = 8,000 articles/hour
- Duplicate checking: 8,000 × 24 hours = 192,000 checks/day

**With incremental fetching:**
- 10 symbols × 2 sources × 4 runs/hour = 80 API calls/hour (same)
- Each call fetches ~10 articles = 800 articles/hour
- Duplicate checking: 800 × 24 hours = 19,200 checks/day

**Result:** 90% reduction in duplicate checking overhead!

### Backup Strategy

```sql
-- Backup fetch_state before reset
CREATE TABLE fetch_state_backup AS SELECT * FROM fetch_state;

-- Restore if needed
INSERT INTO fetch_state SELECT * FROM fetch_state_backup
ON CONFLICT (symbol, fetch_source) DO NOTHING;
```
