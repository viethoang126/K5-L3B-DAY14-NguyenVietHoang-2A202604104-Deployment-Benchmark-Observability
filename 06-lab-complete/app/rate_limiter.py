"""
Rate limiting kiểu sliding window, state lưu trong Redis (sorted set).

Mỗi request được chấp nhận là một phần tử có score = thời điểm (ms).
Cả chuỗi "xoá mốc cũ → đếm → thêm" chạy trong một Lua script nên nguyên tử:
nhiều worker / instance gọi cùng lúc cũng không vượt được giới hạn.
"""
import hashlib
import math
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_MS = 60_000

# Trả về 0 nếu được phép; ngược lại trả số ms phải chờ.
# Dùng giờ của Redis (TIME) để mọi instance chung một đồng hồ.
_SLIDING_WINDOW = """
local key, window, limit = KEYS[1], tonumber(ARGV[1]), tonumber(ARGV[2])
local t = redis.call('TIME')
local now = t[1] * 1000 + math.floor(t[2] / 1000)
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
if redis.call('ZCARD', key) >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    if oldest[2] then
        return math.max(1, tonumber(oldest[2]) + window - now)
    end
    return window
end
redis.call('ZADD', key, now, ARGV[3])
redis.call('PEXPIRE', key, window)
return 0
"""


def check_rate_limit(key: str) -> None:
    # Không lưu API key dạng rõ trong Redis
    redis_key = "ratelimit:" + hashlib.sha256(key.encode()).hexdigest()
    wait_ms = r.eval(_SLIDING_WINDOW, 1, redis_key,
                     WINDOW_MS, settings.rate_limit_per_minute, uuid.uuid4().hex)
    if wait_ms:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(math.ceil(wait_ms / 1000))},
        )
