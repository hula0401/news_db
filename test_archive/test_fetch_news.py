"""Test script for news fetching system."""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

from fetchers.finnhub_fetcher import FinnhubNewsFetcher
from storage.raw_news_storage import RawNewsStorage
from processors.news_processor import NewsProcessor
from db.stock_news import StockNewsDB


async def main():
    """Main test function."""
    print("=" * 60)
    print("📰 NEWS FETCHING SYSTEM TEST")
    print("=" * 60)

    # Load environment variables
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)

    # Get API keys and Supabase credentials
    finnhub_api_key = os.getenv("FINNHUB_API_KEY")
    supabase_url = os.getenv("SUPABASE_NEWS_URL")
    supabase_key = os.getenv("SUPABASE_NEWS_KEY")

    if not finnhub_api_key:
        print("❌ FINNHUB_API_KEY not found in .env file")
        return

    if not supabase_url or not supabase_key:
        print("❌ Supabase credentials not found in .env file")
        return

    print(f"✅ Loaded configuration")
    print(f"   - Finnhub API Key: {finnhub_api_key[:10]}...")
    print(f"   - Supabase URL: {supabase_url}")
    print()

    # Initialize Supabase client
    supabase_client = create_client(supabase_url, supabase_key)
    print("✅ Supabase client initialized")

    # Initialize components
    fetcher = FinnhubNewsFetcher(api_key=finnhub_api_key)
    raw_storage = RawNewsStorage(client=supabase_client)
    stock_news_db = StockNewsDB(client=supabase_client)
    processor = NewsProcessor(stock_news_db=stock_news_db, raw_storage=raw_storage)

    print("✅ Components initialized")
    print()

    # Test symbols
    test_symbols = ["AAPL", "TSLA", "GOOGL"]

    # ========================================
    # STEP 1: Fetch news from Finnhub
    # ========================================
    print("-" * 60)
    print("STEP 1: Fetching news from Finnhub")
    print("-" * 60)

    all_raw_items = []
    for symbol in test_symbols:
        raw_items = await fetcher.fetch_for_symbol(symbol=symbol, days_back=7)
        all_raw_items.extend(raw_items)
        print(f"   {symbol}: {len(raw_items)} articles")

    print(f"\n📊 Total articles fetched: {len(all_raw_items)}")
    print()

    # ========================================
    # STEP 2: Store in stock_news_raw
    # ========================================
    print("-" * 60)
    print("STEP 2: Storing in stock_news_raw table")
    print("-" * 60)

    if all_raw_items:
        insert_stats = await raw_storage.bulk_insert(all_raw_items)
        print(f"\n📊 Insert Statistics:")
        print(f"   Total: {insert_stats['total']}")
        print(f"   Inserted: {insert_stats['inserted']}")
        print(f"   Duplicates: {insert_stats['duplicates']}")
        print(f"   Failed: {insert_stats['failed']}")
    else:
        print("⚠️  No articles to insert")

    print()

    # ========================================
    # STEP 3: Get storage statistics
    # ========================================
    print("-" * 60)
    print("STEP 3: Raw storage statistics")
    print("-" * 60)

    stats = await raw_storage.get_stats()
    print(f"📊 Stock News Raw Table:")
    print(f"   Total: {stats['total']}")
    print(f"   Pending: {stats['pending']}")
    print(f"   Completed: {stats['completed']}")
    print(f"   Failed: {stats['failed']}")
    print()

    # ========================================
    # STEP 4: Process unprocessed news
    # ========================================
    print("-" * 60)
    print("STEP 4: Processing raw news into stock_news table")
    print("-" * 60)

    processing_stats = await processor.process_unprocessed_batch(limit=10)
    print(f"\n📊 Processing Statistics:")
    print(f"   Fetched: {processing_stats['fetched']}")
    print(f"   Processed: {processing_stats['processed']}")
    print(f"   Failed: {processing_stats['failed']}")
    print()

    # ========================================
    # STEP 5: View processed news for each symbol
    # ========================================
    print("-" * 60)
    print("STEP 5: Viewing processed news stacks")
    print("-" * 60)

    for symbol in test_symbols:
        news_stack = await stock_news_db.get_news_stack(symbol=symbol, limit=5)
        print(f"\n{symbol} News Stack ({len(news_stack)} articles):")
        for idx, article in enumerate(news_stack, 1):
            title = article.get('title', 'No title')[:60]
            position = article.get('position_in_stack', '?')
            print(f"   [{position}] {title}...")

    print()

    # ========================================
    # STEP 6: Final statistics
    # ========================================
    print("-" * 60)
    print("STEP 6: Final statistics")
    print("-" * 60)

    final_stats = await raw_storage.get_stats()
    print(f"📊 Final Raw Storage Stats:")
    print(f"   Total: {final_stats['total']}")
    print(f"   Pending: {final_stats['pending']}")
    print(f"   Completed: {final_stats['completed']}")
    print(f"   Failed: {final_stats['failed']}")

    # Cleanup
    await fetcher.close()

    print()
    print("=" * 60)
    print("✅ TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
