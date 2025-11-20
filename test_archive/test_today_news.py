"""Fetch news for today only - dynamic date."""
import asyncio
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client

from fetchers.finnhub_fetcher import FinnhubNewsFetcher
from fetchers.polygon_fetcher import PolygonNewsFetcher
from storage.raw_news_storage import RawNewsStorage
from processors.news_processor import NewsProcessor
from db.stock_news import StockNewsDB
from config import DEFAULT_SYMBOLS, FETCH_CONFIG


async def main():
    """Fetch today's news for configured symbols."""
    print("=" * 60)
    print("📰 TODAY'S NEWS FETCHER")
    print("=" * 60)

    # Calculate today's date range
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now

    print(f"📅 Date Range:")
    print(f"   Start: {today_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   End:   {today_end.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load environment variables
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)

    # Get API keys and Supabase credentials
    finnhub_api_key = os.getenv("FINNHUB_API_KEY")
    polygon_api_key = os.getenv("MASSIVE_API_KEY")
    supabase_url = os.getenv("SUPABASE_NEWS_URL")
    supabase_key = os.getenv("SUPABASE_NEWS_KEY")

    # Validate credentials
    missing = []
    if not finnhub_api_key:
        missing.append("FINNHUB_API_KEY")
    if not polygon_api_key:
        missing.append("MASSIVE_API_KEY")
    if not supabase_url:
        missing.append("SUPABASE_NEWS_URL")
    if not supabase_key:
        missing.append("SUPABASE_NEWS_KEY")

    if missing:
        print(f"❌ Missing credentials: {', '.join(missing)}")
        return

    print(f"✅ Loaded configuration")
    print()

    # Initialize Supabase client
    supabase_client = create_client(supabase_url, supabase_key)

    # Initialize components
    finnhub_fetcher = FinnhubNewsFetcher(api_key=finnhub_api_key)
    polygon_fetcher = PolygonNewsFetcher(api_key=polygon_api_key)
    raw_storage = RawNewsStorage(client=supabase_client)
    stock_news_db = StockNewsDB(client=supabase_client)
    processor = NewsProcessor(stock_news_db=stock_news_db, raw_storage=raw_storage)

    print("✅ Components initialized")
    print()

    # Symbols to fetch (configured in config.py)
    symbols = DEFAULT_SYMBOLS

    print(f"📊 Fetching news for {len(symbols)} symbols:")
    print(f"   {', '.join(symbols)}")
    print()
    print(f"💡 Tip: Edit config.py to change symbols")
    print()

    # ========================================
    # STEP 1: Fetch from Finnhub (today only)
    # ========================================
    print("-" * 60)
    print("STEP 1: Fetching today's news from Finnhub")
    print("-" * 60)

    finnhub_items = []
    for symbol in symbols:
        # Finnhub API uses days_back, so we use 1 to get last 24 hours
        items = await finnhub_fetcher.fetch_for_symbol(symbol=symbol, days_back=1)

        # Filter to only today's articles (published today)
        today_items = [
            item for item in items
            if item.fetched_at.date() == today_start.date()
        ]

        finnhub_items.extend(items)  # Keep all from last 24h for now
        print(f"   {symbol}: {len(items)} articles (last 24h)")

    print(f"\n📊 Finnhub: {len(finnhub_items)} articles")
    print()

    # ========================================
    # STEP 2: Fetch from Polygon (today only)
    # ========================================
    print("-" * 60)
    print("STEP 2: Fetching today's news from Polygon")
    print("-" * 60)

    polygon_items = []
    for symbol in symbols:
        # Polygon API uses exact dates, so we use today's date
        items = await polygon_fetcher.fetch_for_symbol(
            symbol=symbol,
            days_back=1,  # Last 24 hours
            limit=30
        )
        polygon_items.extend(items)
        print(f"   {symbol}: {len(items)} articles")

    print(f"\n📊 Polygon: {len(polygon_items)} articles")
    print()

    # ========================================
    # STEP 3: Store all items
    # ========================================
    print("-" * 60)
    print("STEP 3: Storing in stock_news_raw")
    print("-" * 60)

    all_items = finnhub_items + polygon_items
    print(f"Total items: {len(all_items)}")
    print(f"  - Finnhub: {len(finnhub_items)}")
    print(f"  - Polygon: {len(polygon_items)}")
    print()

    if all_items:
        stats = await raw_storage.bulk_insert(all_items)
        print(f"📊 Storage Results:")
        print(f"   Total: {stats['total']}")
        print(f"   Inserted: {stats['inserted']}")
        print(f"   Duplicates: {stats['duplicates']}")
        print(f"   Failed: {stats['failed']}")
    else:
        print("⚠️  No articles fetched")

    print()

    # ========================================
    # STEP 4: Process all pending items
    # ========================================
    print("-" * 60)
    print("STEP 4: Processing news into stock_news table")
    print("-" * 60)

    total_processed = 0
    total_failed = 0
    batch_size = FETCH_CONFIG["batch_size"]

    while True:
        batch_stats = await processor.process_unprocessed_batch(limit=batch_size)

        if batch_stats['fetched'] == 0:
            break

        total_processed += batch_stats['processed']
        total_failed += batch_stats['failed']

        print(f"Batch: {batch_stats['processed']} processed, {batch_stats['failed']} failed")

        if batch_stats['processed'] == 0:
            break

    print(f"\n📊 Processing Results:")
    print(f"   Processed: {total_processed}")
    print(f"   Failed: {total_failed}")
    print()

    # ========================================
    # STEP 5: Show news stacks by symbol
    # ========================================
    print("-" * 60)
    print("STEP 5: Today's News Stacks")
    print("-" * 60)

    for symbol in symbols:
        news_stack = await stock_news_db.get_news_stack(symbol=symbol, limit=5)

        if news_stack:
            print(f"\n{symbol} - {len(news_stack)} articles:")
            for article in news_stack:
                title = article.get('title', 'No title')[:65]
                position = article.get('position_in_stack', '?')
                metadata = article.get('metadata', {})
                source = metadata.get('fetch_source', 'unknown')
                publisher = metadata.get('publisher') or metadata.get('source_name', '')

                # Format publisher
                pub_str = f" [{publisher[:15]}]" if publisher else ""

                print(f"   [{position}] ({source}) {title}{pub_str}")
        else:
            print(f"\n{symbol} - No news in stack")

    print()

    # ========================================
    # STEP 6: Summary statistics
    # ========================================
    print("-" * 60)
    print("STEP 6: Summary")
    print("-" * 60)

    raw_stats = await raw_storage.get_stats()

    print(f"📊 Raw Storage:")
    print(f"   Total: {raw_stats['total']}")
    print(f"   Pending: {raw_stats['pending']}")
    print(f"   Completed: {raw_stats['completed']}")
    print(f"   Failed: {raw_stats['failed']}")
    print()

    print(f"📊 Today's Fetch:")
    print(f"   Symbols: {len(symbols)}")
    print(f"   Articles fetched: {len(all_items)}")
    print(f"   Articles stored: {stats['inserted'] if all_items else 0}")
    print(f"   Articles processed: {total_processed}")
    print()

    # Cleanup
    await finnhub_fetcher.close()
    await polygon_fetcher.close()

    print("=" * 60)
    print("✅ TODAY'S NEWS FETCH COMPLETE")
    print("=" * 60)
    print()
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())
