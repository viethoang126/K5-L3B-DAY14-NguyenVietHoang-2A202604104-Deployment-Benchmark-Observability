"""
Production AI Agent — Part 6 Final Project

Chạy:      uvicorn app.main:app
Kiểm tra:  python check_production_ready.py
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated

import redis
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, estimate_tokens, record_cost, release_budget
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask


# ── Structured logging: mỗi dòng log là một JSON object ──
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
            **getattr(record, "fields", {}),
        }
        return json.dumps(entry, ensure_ascii=False)


logger = logging.getLogger("agent")
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(JsonFormatter())
logger.handlers = [_handler]
logger.setLevel(logging.INFO)
logger.propagate = False  # tránh root logger in thêm một bản dạng text


def log(event: str, level: int = logging.INFO, **fields) -> None:
    logger.log(level, event, extra={"fields": fields})


# ── Vòng đời app ──
# Graceful shutdown: uvicorn nhận SIGTERM, ngừng nhận kết nối mới, chờ request đang chạy
# xong rồi mới chạy phần sau `yield`. Không tự đăng ký signal handler để khỏi ghi đè uvicorn.
@asynccontextmanager
async def lifespan(app: FastAPI):
    log("startup", environment=settings.environment, port=settings.port)
    if not settings.agent_api_key:
        log("config_warning", logging.WARNING,
            detail="AGENT_API_KEY chưa đặt, mọi request /ask sẽ bị 401")
    yield
    r.close()
    log("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def access_log(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        # Lỗi không lường trước: log tên lỗi, client không thấy stack trace
        log("unhandled_error", logging.ERROR, path=request.url.path, error=type(exc).__name__)
        response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    # Không log header và body để không lộ API key và nội dung người dùng
    log("request", method=request.method, path=request.url.path,
        status=response.status_code, ms=round((time.perf_counter() - started) * 1000, 1))
    return response


@app.exception_handler(redis.RedisError)
async def redis_error_handler(request: Request, exc: redis.RedisError):
    # Không kiểm tra được rate limit / budget thì không gọi LLM
    log("redis_error", logging.ERROR, error=type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})


class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True,
                                               min_length=1, max_length=2000)]


@app.get("/health")
def health():
    """Liveness: process còn chạy là 200. Không phụ thuộc Redis."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness: chỉ nhận traffic khi nối được Redis."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"status": "ready"}


# def (không async): FastAPI chạy trong thread pool nên llm_ask không chặn event loop
@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)                       # 429
    input_tokens = estimate_tokens(body.question)
    reservation = check_budget(input_tokens)        # 402
    try:
        answer = llm_ask(body.question)
    except Exception:
        release_budget(reservation)
        raise
    cost = record_cost(reservation, input_tokens, estimate_tokens(answer))
    log("llm_call", input_tokens=input_tokens,
        output_tokens=estimate_tokens(answer), cost_usd=round(cost, 8))
    return {"question": body.question, "answer": answer}
