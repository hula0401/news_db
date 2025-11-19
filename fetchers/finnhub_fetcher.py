"""Finnhub news fetcher."""
import sys
import os
from typing import List, Optional
from datetime import datetime, timedelta

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from backend.app.external.finnhub_client import FinnhubClient
except ImportError:
    # Fallback for direct execution
    import httpx

    class FinnhubClient:
        """Fallback Finnhub client."""
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.base_url = "https://finnhub.io/api/v1"
            self.client = httpx.AsyncClient(timeout=10.0)

        async def get_company_news(self, symbol: str, from_date: str, to_date: str):
            response = await self.client.get(
                f"{self.base_url}/company-news",
                params={
                    "symbol": symbol.upper(),
                    "from": from_date,
                    "to": to_date,
                    "token": self.api_key
                }
            )
            if response.status_code == 200:
                articles = response.json()
                return [
                    {
                        "id": str(article.get("id", "")),
                        "headline": article.get("headline", ""),
                        "summary": article.get("summary", ""),
                        "url": article.get("url", ""),
                        "datetime": article.get("datetime", 0),
                        "source": article.get("source", ""),
                        "category": article.get("category", ""),
                        "image": article.get("image", ""),
                    }
                    for article in articles[:20]
                ]
            return []

        async def close(self):
            await self.client.aclose()

from ..models.raw_news import RawNewsItem


class FinnhubNewsFetcher:
    """Fetcher for Finnhub news API."""

    def __init__(self, api_key: str):
        """
        Initialize Finnhub fetcher.

        Args:
            api_key: Finnhub API key
        """
        self.client = FinnhubClient(api_key=api_key)

    async def fetch_for_symbol(
        self,
        symbol: str,
        days_back: int = 7
    ) -> List[RawNewsItem]:
        """
        Fetch news for a single symbol.

        Args:
            symbol: Stock ticker symbol
            days_back: Number of days to fetch (default 7)

        Returns:
            List of RawNewsItem objects
        """
        try:
            # Calculate date range
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days_back)

            # Format dates for Finnhub API (YYYY-MM-DD)
            from_str = from_date.strftime("%Y-%m-%d")
            to_str = to_date.strftime("%Y-%m-%d")

            print(f"🔍 Fetching Finnhub news for {symbol} ({from_str} to {to_str})...")

            # Fetch from Finnhub
            articles = await self.client.get_company_news(
                symbol=symbol,
                from_date=from_str,
                to_date=to_str
            )

            # Convert to RawNewsItem objects
            raw_items = []
            for article in articles:
                try:
                    raw_item = RawNewsItem.from_finnhub_response(
                        symbol=symbol,
                        article_data=article
                    )
                    raw_items.append(raw_item)
                except Exception as e:
                    print(f"⚠️  Error converting article: {e}")
                    continue

            print(f"✅ Fetched {len(raw_items)} articles for {symbol} from Finnhub")
            return raw_items

        except Exception as e:
            print(f"❌ Error fetching Finnhub news for {symbol}: {e}")
            return []

    async def fetch_for_symbols(
        self,
        symbols: List[str],
        days_back: int = 7
    ) -> List[RawNewsItem]:
        """
        Fetch news for multiple symbols.

        Args:
            symbols: List of stock ticker symbols
            days_back: Number of days to fetch

        Returns:
            List of RawNewsItem objects for all symbols
        """
        all_items = []

        for symbol in symbols:
            items = await self.fetch_for_symbol(symbol, days_back)
            all_items.extend(items)

        print(f"📊 Total fetched: {len(all_items)} articles for {len(symbols)} symbols")
        return all_items

    async def close(self):
        """Close the Finnhub client."""
        await self.client.close()
