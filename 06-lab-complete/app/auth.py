"""
API Key authentication: header X-API-Key phải trùng AGENT_API_KEY, thiếu hoặc sai → 401.
"""
import hmac

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

# auto_error=False: để tự trả 401 (mặc định FastAPI trả 403 khi thiếu header)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Dependency cho FastAPI — dùng trong /ask: Depends(verify_api_key)."""
    expected = settings.agent_api_key
    # Server chưa cấu hình key → từ chối tất cả (fail closed).
    # compare_digest: thời gian so sánh không phụ thuộc vị trí ký tự sai.
    if not expected or not api_key or not hmac.compare_digest(
        api_key.encode(), expected.encode()
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
