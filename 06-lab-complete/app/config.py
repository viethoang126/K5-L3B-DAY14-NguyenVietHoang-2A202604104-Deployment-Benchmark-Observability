"""
Config — 12-Factor: mọi cấu hình đọc từ biến môi trường.

Giá trị mặc định chỉ dành cho chạy local. Secret (AGENT_API_KEY) không có mặc định.
"""
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # default_factory: đọc env lúc tạo Settings(), không phải lúc định nghĩa class
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")))
    daily_budget_usd: float = field(
        default_factory=lambda: float(os.getenv("DAILY_BUDGET_USD", "1.0")))

    def __post_init__(self):
        # Fail fast: không cho chạy production khi quên đặt API key
        if self.environment == "production" and not self.agent_api_key:
            raise ValueError("AGENT_API_KEY phải được đặt khi ENVIRONMENT=production")


settings = Settings()
