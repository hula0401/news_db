"""Production incremental news fetcher with timestamp tracking."""
import asyncio
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client

from fetchers.finnhub_fetcher import FinnhubNewsFetcher, FinnhubClient
from fetchers.polygon_fetcher import PolygonNewsFetcher, PolygonClient
from storage.raw_news_storage import RawNewsStorage
from storage.fetch_state_manager import FetchStateManager
from processors.news_processor import NewsProcessor
from db.stock_news import StockNewsDB
from config import DEFAULT_SYMBOLS, FETCH_CONFIG


class IncrementalFetcher:
    """Intelligent incremental news fetcher."""

    def __init__(
        self,
        finnhub_client: FinnhubClient,
        polygon_client: PolygonClient,
        raw_storage: RawNewsStorage,
        fetch_state: FetchStateManager,
        processor: NewsProcessor,
        buffer_minutes: int = 1
    ):
        """
        Initialize incremental fetcher.

        Args:
            finnhub_client: Finnhub API client
            polygon_client: Polygon API client
            raw_storage: Raw news storage
            fetch_state: Fetch state manager
            processor: News processor
            buffer_minutes: Overlap window in minutes (default 1)
        """
        self.finnhub_client = finnhub_client
        self.polygon_client = polygon_client
        self.raw_storage = raw_storage
        self.fetch_state = fetch_state
        self.processor = processor
        self.buffer_minutes = buffer_minutes

    async def fetch_symbol_from_source(
        self,
        symbol: str,
        source: str,
        from_time: datetime,
        to_time: datetime
    ):
        """
        Fetch news for a symbol from a specific source.

        Args:
            symbol: Stock ticker
            source: 'finnhub' or 'polygon'
            from_time: Start time
            to_time: End time

        Returns:
            List of RawNewsItem objects
        """
        try:
            # Calculate days back
            days_back = max(1, (to_time - from_time).days + 1)

            if source == "finnhub":
                # Finnhub uses days_back parameter
                from models.raw_news import RawNewsItem

                from_str = from_time.strftime("%Y-%m-%d")
                to_str = to_time.strftime("%Y-%m-%d")

                articles = await self.finnhub_client.get_company_news(
                    symbol=symbol,
                    from_date=from_str,
                    to_date=to_str
                )

                items = []
                for article in articles:
                    try:
                        item = RawNewsItem.from_finnhub_response(symbol, article)
                        items.append(item)
                    except Exception as e:
                        print(f"⚠️  Error converting article: {e}")
                        continue

                return items

            elif source == "polygon":
                from models.raw_news import RawNewsItem

                from_str = from_time.strftime("%Y-%m-%d")
                to_str = to_time.strftime("%Y-%m-%d")

                articles = await self.polygon_client.get_ticker_news(
                    ticker=symbol,
                    published_utc_gte=from_str,
                    published_utc_lte=to_str,
                    limit=50
                )

                items = []
                for article in articles:
                    try:
                        item = RawNewsItem.from_polygon_response(symbol, article)
                        items.append(item)
                    except Exception as e:
                        print(f"⚠️  Error converting article: {e}")
                        continue

                return items

        except Exception as e:
            print(f"❌ Error fetching from {source}: {e}")
            return []

    async def fetch_symbol(self, symbol: str, sources: list[str] = None):
        """
        Fetch news incrementally for a symbol from all sources.

        Args:
            symbol: Stock ticker
            sources: List of sources to fetch from (default: ['finnhub', 'polygon'])

        Returns:
            Dictionary with statistics
        """
        if sources is None:
            sources = ["finnhub", "polygon"]

        stats = {
            "symbol": symbol,
            "sources": {},
            "total_fetched": 0,
            "total_stored": 0,
        }

        for source in sources:
            # Get incremental fetch window
            from_time, to_time = await self.fetch_state.get_last_fetch_time(
                symbol, source, self.buffer_minutes
            )

            # Fetch news
            items = await self.fetch_symbol_from_source(
                symbol, source, from_time, to_time
            )

            # Store in raw storage
            if items:
                storage_stats = await self.raw_storage.bulk_insert(items)
                stored = storage_stats["inserted"]
            else:
                stored = 0

            # Update fetch state
            await self.fetch_state.update_fetch_state(
                symbol=symbol,
                fetch_source=source,
                from_time=from_time,
                to_time=to_time,
                articles_fetched=len(items),
                articles_stored=stored,
                status="success"
            )

            stats["sources"][source] = {
                "fetched": len(items),
                "stored": stored,
                "duplicates": len(items) - stored,
            }

            stats["total_fetched"] += len(items)
            stats["total_stored"] += stored

        return stats

    async def fetch_all_symbols(self, symbols: list[str]):
        """
        Fetch news incrementally for all symbols.

        Args:
            symbols: List of stock tickers

        Returns:
            Dictionary with overall statistics
        """
        print(f"🚀 Starting incremental fetch for {len(symbols)} symbols")
        print(f"   Buffer window: {self.buffer_minutes} minute(s)")
        print()

        all_stats = {
            "symbols": {},
            "total_fetched": 0,
            "total_stored": 0,
            "start_time": datetime.now(),
        }

        for symbol in symbols:
            print(f"\n📊 Fetching {symbol}...")
            symbol_stats = await self.fetch_symbol(symbol)

            all_stats["symbols"][symbol] = symbol_stats
            all_stats["total_fetched"] += symbol_stats["total_fetched"]
            all_stats["total_stored"] += symbol_stats["total_stored"]

            # Small delay to respect rate limits
            await asyncio.sleep(0.3)

        all_stats["end_time"] = datetime.now()
        all_stats["duration"] = (all_stats["end_time"] - all_stats["start_time"]).total_seconds()

        return all_stats


async def main():
    """Run incremental news fetch."""
    print("=" * 70)
    print("📰 INCREMENTAL NEWS FETCHER (Production)")
    print("=" * 70)
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load environment
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)

    finnhub_api_key = os.getenv("FINNHUB_API_KEY")
    polygon_api_key = os.getenv("MASSIVE_API_KEY")
    supabase_url = os.getenv("SUPABASE_NEWS_URL")
    supabase_key = os.getenv("SUPABASE_NEWS_KEY")

    # Validate
    if not all([finnhub_api_key, polygon_api_key, supabase_url, supabase_key]):
        print("❌ Missing required environment variables")
        return

    print("✅ Configuration loaded")
    print()

    # Initialize clients
    supabase = create_client(supabase_url, supabase_key)
    finnhub_client = FinnhubClient(api_key=finnhub_api_key)
    polygon_client = PolygonClient(api_key=polygon_api_key)

    # Initialize storage and managers
    raw_storage = RawNewsStorage(client=supabase)
    fetch_state = FetchStateManager(client=supabase)
    stock_news_db = StockNewsDB(client=supabase)
    processor = NewsProcessor(stock_news_db=stock_news_db, raw_storage=raw_storage)

    # Initialize incremental fetcher
    fetcher = IncrementalFetcher(
        finnhub_client=finnhub_client,
        polygon_client=polygon_client,
        raw_storage=raw_storage,
        fetch_state=fetch_state,
        processor=processor,
        buffer_minutes=1  # 1-minute overlap window
    )

    # Get symbols from config
    symbols = DEFAULT_SYMBOLS

    print(f"📋 Symbols: {', '.join(symbols)}")
    print()

    # STEP 1: Fetch incrementally
    print("-" * 70)
    print("STEP 1: Incremental Fetch")
    print("-" * 70)

    fetch_stats = await fetcher.fetch_all_symbols(symbols)

    print()
    print(f"📊 Fetch Summary:")
    print(f"   Total articles fetched: {fetch_stats['total_fetched']}")
    print(f"   Total articles stored: {fetch_stats['total_stored']}")
    print(f"   Duplicates skipped: {fetch_stats['total_fetched'] - fetch_stats['total_stored']}")
    print(f"   Duration: {fetch_stats['duration']:.2f}s")
    print()

    # STEP 2: Process all pending
    print("-" * 70)
    print("STEP 2: Process Pending News")
    print("-" * 70)

    total_processed = 0
    total_failed = 0

    while True:
        batch_stats = await processor.process_unprocessed_batch(limit=100)

        if batch_stats['fetched'] == 0:
            break

        total_processed += batch_stats['processed']
        total_failed += batch_stats['failed']

        if batch_stats['processed'] > 0:
            print(f"   Batch: {batch_stats['processed']} processed, {batch_stats['failed']} failed")

        if batch_stats['processed'] == 0:
            break

    print()
    print(f"📊 Processing Summary:")
    print(f"   Processed: {total_processed}")
    print(f"   Failed: {total_failed}")
    print()

    # STEP 3: Show news stacks
    print("-" * 70)
    print("STEP 3: News Stacks (Top 3 per symbol)")
    print("-" * 70)

    for symbol in symbols[:5]:  # Show first 5 symbols
        news_stack = await stock_news_db.get_news_stack(symbol, limit=3)

        if news_stack:
            print(f"\n{symbol}:")
            for article in news_stack:
                title = article.get('title', '')[:55]
                pos = article.get('position_in_stack', '?')
                source = article.get('metadata', {}).get('fetch_source', '?')
                print(f"   [{pos}] ({source}) {title}...")

    print()

    # Cleanup
    await finnhub_client.close()
    await polygon_client.close()

    print("=" * 70)
    print("✅ INCREMENTAL FETCH COMPLETE")
    print("=" * 70)
    print(f"💡 Next run will only fetch news since {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
