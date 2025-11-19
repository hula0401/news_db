"""Database operations for stock_news table."""
from typing import List, Dict, Any, Optional
from datetime import datetime
from supabase import Client
import asyncio


class StockNewsDB:
    """Database operations for stock_news table."""

    def __init__(self, client: Client):
        """
        Initialize with Supabase client.

        Args:
            client: Supabase client instance
        """
        self.client = client
        self.table_name = "stock_news"

    async def push_news_to_stack(
        self,
        symbol: str,
        news_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Push news to the top of the stack for a symbol.

        This implements a LIFO (Last In First Out) stack where:
        - New news is inserted at position 1
        - Existing news positions are incremented
        - News beyond position 5 is archived/deleted

        Args:
            symbol: Stock ticker symbol
            news_data: News data to insert (title, summary, url, etc.)

        Returns:
            Inserted news item or None if failed
        """
        try:
            # Check for duplicate URL
            url = news_data.get("url")
            if url and await self.check_duplicate_url(symbol, url):
                print(f"⚠️  Duplicate URL detected for {symbol}, skipping: {url[:50]}...")
                return None

            # Prepare news item
            news_item = {
                "symbol": symbol.upper(),
                "title": news_data.get("title", ""),
                "summary": news_data.get("summary", ""),
                "url": url,
                "published_at": news_data.get("published_at"),
                "source_id": news_data.get("source_id"),
                "external_id": news_data.get("external_id"),
                "metadata": news_data.get("metadata", {}),
                "position_in_stack": 1,  # New news always goes to position 1
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            # First, increment positions of existing news
            def _increment_positions():
                return (
                    self.client
                    .rpc("increment_news_positions", {"p_symbol": symbol.upper()})
                    .execute()
                )

            # Try to call stored procedure, if it doesn't exist, do manual update
            try:
                await asyncio.to_thread(_increment_positions)
            except Exception:
                # Fallback: manually update positions
                def _get_existing():
                    return (
                        self.client
                        .table(self.table_name)
                        .select("id, position_in_stack")
                        .eq("symbol", symbol.upper())
                        .order("position_in_stack")
                        .execute()
                    )

                existing = await asyncio.to_thread(_get_existing)

                # Update each position
                for item in existing.data:
                    new_pos = item["position_in_stack"] + 1

                    def _update_pos():
                        return (
                            self.client
                            .table(self.table_name)
                            .update({"position_in_stack": new_pos})
                            .eq("id", item["id"])
                            .execute()
                        )

                    await asyncio.to_thread(_update_pos)

            # Insert new news at position 1
            def _insert():
                return self.client.table(self.table_name).insert(news_item).execute()

            result = await asyncio.to_thread(_insert)

            if result.data:
                print(f"✅ Pushed news to {symbol} stack: {news_item['title'][:50]}...")

                # Archive news beyond position 5
                await self._archive_old_news(symbol, max_position=5)

                return result.data[0]

            return None

        except Exception as e:
            print(f"❌ Error pushing news to stack for {symbol}: {e}")
            return None

    async def get_news_stack(
        self,
        symbol: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get news stack for a symbol (ordered by position).

        Args:
            symbol: Stock ticker symbol
            limit: Maximum number of news items to return

        Returns:
            List of news items ordered by position
        """
        try:
            def _fetch():
                return (
                    self.client
                    .table(self.table_name)
                    .select("*")
                    .eq("symbol", symbol.upper())
                    .order("position_in_stack")
                    .limit(limit)
                    .execute()
                )

            result = await asyncio.to_thread(_fetch)
            return result.data or []

        except Exception as e:
            print(f"❌ Error getting news stack for {symbol}: {e}")
            return []

    async def check_duplicate_url(self, symbol: str, url: str) -> bool:
        """
        Check if URL already exists for this symbol.

        Args:
            symbol: Stock ticker symbol
            url: News URL

        Returns:
            True if duplicate exists
        """
        try:
            def _check():
                return (
                    self.client
                    .table(self.table_name)
                    .select("id")
                    .eq("symbol", symbol.upper())
                    .eq("url", url)
                    .limit(1)
                    .execute()
                )

            result = await asyncio.to_thread(_check)
            return len(result.data) > 0

        except Exception as e:
            print(f"❌ Error checking duplicate URL: {e}")
            return False

    async def _archive_old_news(self, symbol: str, max_position: int = 5) -> int:
        """
        Archive or delete news items beyond max_position.

        Args:
            symbol: Stock ticker symbol
            max_position: Maximum position to keep (default 5)

        Returns:
            Number of archived/deleted items
        """
        try:
            def _delete():
                return (
                    self.client
                    .table(self.table_name)
                    .delete()
                    .eq("symbol", symbol.upper())
                    .gt("position_in_stack", max_position)
                    .execute()
                )

            result = await asyncio.to_thread(_delete)
            deleted_count = len(result.data) if result.data else 0

            if deleted_count > 0:
                print(f"🗑️  Archived {deleted_count} old news items for {symbol}")

            return deleted_count

        except Exception as e:
            print(f"❌ Error archiving old news: {e}")
            return 0

    async def get_stats(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics for stock news.

        Args:
            symbol: Optional symbol to filter by

        Returns:
            Statistics dictionary
        """
        try:
            def _get_count():
                query = self.client.table(self.table_name).select("id", count="exact")
                if symbol:
                    query = query.eq("symbol", symbol.upper())
                return query.execute()

            result = await asyncio.to_thread(_get_count)

            stats = {
                "total": result.count or 0,
            }

            if symbol:
                stats["symbol"] = symbol.upper()

            return stats

        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return {"total": 0}
