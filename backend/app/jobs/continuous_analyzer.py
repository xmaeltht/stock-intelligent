import logging
import signal
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

from app.core.config import get_settings
from app.jobs.daily_pipeline import (
    analyze_batch,
    import_company_universe,
    log_event,
    select_symbols,
    validate_results,
)
from app.providers.nasdaq import NasdaqProvider
from app.providers.sec import SecProvider

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("continuous-analyzer")
stop_event = Event()


def request_stop(signum: int, _frame: object) -> None:
    log_event("continuous_analyzer_stopping", signal=signum)
    stop_event.set()


def main() -> int:
    settings = get_settings()
    sec = SecProvider(settings.sec_user_agent, Path(settings.market_data_path))
    prices = NasdaqProvider()
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    next_universe_refresh = datetime.min.replace(tzinfo=UTC)
    log_event("continuous_analyzer_started", batch_size=settings.analysis_batch_size)
    while not stop_event.is_set():
        try:
            now = datetime.now(UTC)
            if now >= next_universe_refresh:
                import_company_universe(sec)
                next_universe_refresh = now + timedelta(hours=settings.universe_refresh_hours)

            symbols = select_symbols(settings)
            if not symbols:
                log_event("continuous_analyzer_idle", sleep_seconds=settings.analysis_idle_seconds)
                stop_event.wait(settings.analysis_idle_seconds)
                continue

            log_event("continuous_batch_selected", symbol_count=len(symbols), symbols=symbols[:25])
            succeeded, failures = analyze_batch(symbols, sec, prices)
            if succeeded:
                validate_results()
            log_event(
                "continuous_batch_completed",
                attempted=len(symbols),
                succeeded=succeeded,
                failed=len(failures),
                failures=failures[:50],
            )
            stop_event.wait(settings.analysis_loop_delay_seconds)
        except Exception:
            logger.exception("continuous analyzer batch failed")
            stop_event.wait(60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
