"""Configuration for news fetching."""

# Symbols to fetch news for
# Add or remove symbols as needed
DEFAULT_SYMBOLS = [
    "AAPL",   # Apple
    "TSLA",   # Tesla
    #"GOOGL",  # Google
    #"MSFT",   # Microsoft
    "NVDA",   # NVIDIA
    #"META",   # Meta
    #"AMZN",   # Amazon
]

# Top market cap stocks (optional additional list)
TOP_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "BRK.B", "V", "JPM"
]

# Tech stocks
TECH_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "AMD", "INTC", "ORCL"
]

# Fetch settings
FETCH_CONFIG = {
    "days_back": 1,          # How many days back to fetch
    "polygon_limit": 30,     # Max articles per symbol from Polygon
    "finnhub_limit": 20,     # Finnhub auto-limits to 20
    "batch_size": 100,       # Processing batch size
}
