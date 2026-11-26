"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import redis

from app.config import settings

# from_url chỉ tạo connection pool, chưa kết nối → app vẫn khởi động được khi Redis chết.
# Timeout ngắn để request không treo khi Redis mất kết nối.
r = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


def redis_healthy() -> bool:
    try:
        return bool(r.ping())
    except redis.RedisError:
        return False
