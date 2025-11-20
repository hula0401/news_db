"""Storage layer for news data."""
from storage.raw_news_storage import RawNewsStorage
from storage.fetch_state_manager import FetchStateManager

__all__ = ["RawNewsStorage", "FetchStateManager"]
