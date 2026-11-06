"""
OmniScout-TG: Clients Module
Exports b.ai AI Gateway client and zero-cost Telegram harvester client.
"""

from src.clients.bai_client import (
    BaiAuthenticationError,
    BaiClient,
    BaiClientError,
    BaiRateLimitError,
)
from src.clients.telegram_client import (
    TelegramHarvesterClient,
    parse_abbreviated_number,
)

__all__ = [
    "BaiAuthenticationError",
    "BaiClient",
    "BaiClientError",
    "BaiRateLimitError",
    "TelegramHarvesterClient",
    "parse_abbreviated_number",
]
