"""Per-IP rate limiting, so one caller cannot spend the whole Gemini quota.

Counts live in Redis, so every worker and container shares the same limit.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)
