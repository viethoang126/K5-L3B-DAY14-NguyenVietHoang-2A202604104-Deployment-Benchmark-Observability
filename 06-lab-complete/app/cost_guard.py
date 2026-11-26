"""
Cost guard: tổng chi phí LLM trong ngày (UTC) lưu ở Redis, vượt DAILY_BUDGET_USD → 402.

Cách làm "giữ chỗ trước, quyết toán sau":
  1. check_budget: ước lượng chi phí và cộng vào tổng TRƯỚC khi gọi LLM
     (kiểm tra + cộng trong một Lua script nên nhiều request đồng thời không cùng lọt qua).
  2. record_cost: sau khi gọi LLM, bù phần chênh giữa chi phí thật và phần đã giữ.
"""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

# Số token output giả định khi chưa biết câu trả lời dài bao nhiêu
ESTIMATED_OUTPUT_TOKENS = 100
KEY_TTL_SECONDS = 2 * 24 * 3600

# Trả về 1 nếu giữ chỗ được, 0 nếu hết ngân sách.
_RESERVE = """
local spent = tonumber(redis.call('GET', KEYS[1]) or '0')
local cost, budget = tonumber(ARGV[1]), tonumber(ARGV[2])
if spent + cost > budget then
    return 0
end
redis.call('INCRBYFLOAT', KEYS[1], ARGV[1])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return 1
"""


def _today_key() -> str:
    # Mỗi ngày một key → ngân sách tự reset
    return f"cost:{datetime.now(timezone.utc):%Y-%m-%d}"


def estimate_tokens(text: str) -> int:
    """Ước lượng thô (mock LLM không trả số token thật)."""
    return len(text.split()) * 2


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000


def check_budget(input_tokens: int) -> tuple[str, float]:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → 402. Trả về (key, số tiền đã giữ)."""
    key = _today_key()
    reserved = calculate_cost(input_tokens, ESTIMATED_OUTPUT_TOKENS)
    if not r.eval(_RESERVE, 1, key, reserved, settings.daily_budget_usd, KEY_TTL_SECONDS):
        raise HTTPException(status_code=402, detail="Daily budget exceeded")
    return key, reserved


def record_cost(reservation: tuple[str, float], input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Quyết toán phần đã giữ, trả về chi phí thật của request."""
    key, reserved = reservation
    cost = calculate_cost(input_tokens, output_tokens)
    r.incrbyfloat(key, cost - reserved)
    return cost


def release_budget(reservation: tuple[str, float]) -> None:
    """Gọi LLM thất bại → hoàn lại phần đã giữ."""
    key, reserved = reservation
    r.incrbyfloat(key, -reserved)
