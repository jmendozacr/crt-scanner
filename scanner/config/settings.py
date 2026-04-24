import os
from dotenv import load_dotenv

load_dotenv()

TWELVE_DATA_API_KEY: str = os.environ["TWELVE_DATA_API_KEY"]
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID: str = os.environ["TELEGRAM_CHAT_ID"]

SCAN_INTERVAL_SECONDS: int = 900  # 15 minutes

HTF_TIMEFRAMES: list[str] = ["1day", "2day", "3day"]
H4_TIMEFRAME: str = "4h"
M15_TIMEFRAME: str = "15min"

STOP_LOSS_PIPS: int = 12

API_RATE_LIMIT_PER_MINUTE: int = 8
API_RATE_LIMIT_PER_DAY: int = 800

CACHE_DIR: str = "cache"
