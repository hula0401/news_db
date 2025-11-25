"""Configuration for LLM-based news categorization system."""

# LLM Model Configuration
LLM_MODELS = {
    "categorization": {
        "model": "glm-4-flash",           # Zhipu AI model for categorization
        "temperature": 0.3,               # Lower = more consistent
        "timeout": 60.0,                  # Request timeout in seconds
        "max_retries": 2,                 # Retry on failure
        "concurrency_limit": 1,           # Max concurrent API calls (glm-4-flash limit: 2, use 1 for safety)
        "delay_between_batches": 2.0,     # Seconds to wait between batches
    },
    "summarization": {
        "model": "glm-4-flash",           # Zhipu AI model for daily summaries
        "temperature": 0.3,               # Lower = more consistent
        "timeout": 120.0,                 # Longer timeout for summaries
        "max_retries": 2,                 # Retry on failure
    }
}

# LLM Processing Configuration
LLM_CONFIG = {
    "batch_size": 5,               # Items per LLM API call (reduced from 10 to avoid rate limits)
    "processing_limit": 20,        # Max items to process per incremental run
    "temperature": 0.3,            # LLM temperature (lower = more consistent) - DEPRECATED, use LLM_MODELS
}

# News Fetching Configuration
FETCH_CONFIG = {
    # Finnhub categories to fetch (will fetch from all listed categories)
    "finnhub_categories": ['general', 'merger'],
    "polygon_limit": 200,          # Max articles from Polygon per fetch
    "buffer_minutes": 1,           # Overlap window for incremental fetching (avoid gaps)
}

# Categories to exclude from daily summaries and analysis
EXCLUDED_CATEGORIES = [
    "MACRO_NOBODY",      # Geopolitical commentary without specific leaders
    "UNCATEGORIZED",     # Failed to categorize (will be retried)
    "ERROR",             # Permanent categorization errors (won't retry)
    "NON_FINANCIAL",     # Non-market news (filtered during processing)
]

# Action Priority Configuration (for distributed processing)
# Lower number = higher priority (processed first)
ACTION_PRIORITY = {
    "process_pending_raw": 1,          # Highest priority: Process pending items in stock_news_raw
    "recategorize_uncategorized": 2,   # High priority: Re-process UNCATEGORIZED in stock_news
    "fetch_and_process": 3,            # Normal priority: Regular incremental fetch + process
    "generate_summary": 4,             # Lower priority: Daily summary generation
}

# Legacy config (deprecated, use ACTION_PRIORITY instead)
PROCESSING_CONFIG = {
    "FETCH_NEWS": 1,
    "PROCESS_NEWS": 2,
    "SUMMARIZE_NEWS": 3,
}