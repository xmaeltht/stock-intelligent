from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Stock Intelligence API"
    app_env: str = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    sec_user_agent: str = "StockIntelligence/0.2 research@example.com"
    market_data_path: str = "/data/market"
    # Leave empty to analyze the complete eligible SEC universe in resumable batches.
    # A comma-separated value remains available for targeted/manual runs.
    analysis_symbols: str = ""
    analysis_batch_size: int = Field(default=500, ge=1, le=10000)
    analysis_workers: int = Field(default=4, ge=1, le=16)
    analysis_retry_hours: int = Field(default=6, ge=1, le=720)
    analysis_refresh_hours: int = Field(default=24, ge=1, le=720)
    analysis_loop_delay_seconds: int = Field(default=5, ge=0, le=300)
    analysis_idle_seconds: int = Field(default=300, ge=10, le=3600)
    universe_refresh_hours: int = Field(default=24, ge=1, le=168)
    # Snapshot retention: cap analyses kept per company so the table can't grow
    # without bound. Older-than-latest snapshots also drop their heavy price
    # history (only the latest row needs it for the chart).
    snapshot_retention: int = Field(default=60, ge=2, le=2000)
    analysis_exchanges: str = "Nasdaq,NYSE,NYSE American"
    # Fast live-quote loop: refreshes current price / 1D move for already-analyzed
    # securities far more often than the heavy fundamental loop can, so the screen
    # feels live. Best-effort — failures never stop the deep analyzer.
    live_quotes_enabled: bool = True
    live_quote_interval_seconds: int = Field(default=45, ge=10, le=3600)
    # Overnight (20:00-04:00 ET): quotes barely move, so refresh less often.
    live_quote_overnight_seconds: int = Field(default=180, ge=30, le=7200)
    # Weekend / fully closed.
    live_quote_offhours_seconds: int = Field(default=900, ge=30, le=7200)
    live_quote_batch_size: int = Field(default=240, ge=10, le=2000)
    live_quote_chunk_size: int = Field(default=40, ge=1, le=200)
    # A security is considered "live/fresh" if its price was refreshed within
    # this many seconds; drives the freshness badges in the UI.
    live_fresh_seconds: int = Field(default=180, ge=30, le=3600)
    # Run the analyzer loops inside the always-on backend process so scanning is
    # guaranteed to run non-stop even without a dedicated analyzer deployment.
    # If a separate continuous-analyzer pod is running, set the deep flag false
    # to avoid duplicate work.
    backend_run_live_loop: bool = True
    backend_run_deep_loop: bool = True
    # Auth: HMAC secret for signing session cookies (override in production via the
    # SESSION_SECRET env/secret), whether the cookie requires HTTPS, and its lifetime.
    session_secret: str = Field(default="dev-insecure-session-secret-change-me", repr=False)
    session_cookie_secure: bool = True
    session_ttl_hours: int = Field(default=720, ge=1, le=8760)
    # Background alert evaluation: fire crossings even when no one is in the app.
    alerts_worker_enabled: bool = True
    alert_eval_interval_seconds: int = Field(default=300, ge=30, le=3600)
    # Billing (Stripe). Empty keys leave billing disabled — checkout returns 503
    # and everyone stays on the free plan. app_base_url is used for redirect URLs.
    stripe_secret_key: str = Field(default="", repr=False)
    stripe_webhook_secret: str = Field(default="", repr=False)
    stripe_price_id: str = ""
    app_base_url: str = "https://stock-intelligence.maelkloud.com"

    @property
    def billing_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_price_id)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "stock_app"
    postgres_password: str = Field(default="change-me", repr=False)
    postgres_db: str = "stock_intelligence"
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")

    @computed_field
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            "postgresql+psycopg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def symbol_list(self) -> list[str]:
        return [symbol.strip().upper() for symbol in self.analysis_symbols.split(",") if symbol]

    @property
    def exchange_list(self) -> list[str]:
        return [exchange.strip() for exchange in self.analysis_exchanges.split(",") if exchange]


@lru_cache
def get_settings() -> Settings:
    return Settings()
