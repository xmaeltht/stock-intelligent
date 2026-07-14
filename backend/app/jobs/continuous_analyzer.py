import logging
import signal
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.jobs.daily_pipeline import (
    analyze_batch,
    import_company_universe,
    log_event,
    select_symbols,
    validate_results,
)
from app.jobs.live_quotes import is_market_open, run_live_cycle
from app.providers.nasdaq import NasdaqProvider
from app.providers.sec import SecProvider

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("continuous-analyzer")
stop_event = Event()


def request_stop(signum: int, _frame: object) -> None:
    log_event("continuous_analyzer_stopping", signal=signum)
    stop_event.set()


def deep_loop(sec: SecProvider, prices: NasdaqProvider, stop: Event = stop_event) -> None:
    """The heavy fundamental/technical analyzer — runs continuously, refreshing
    the least-recently analyzed securities and retrying cooled-down failures."""
    settings = get_settings()
    next_universe_refresh = datetime.min.replace(tzinfo=UTC)
    log_event("deep_loop_started", batch_size=settings.analysis_batch_size)
    while not stop.is_set():
        try:
            now = datetime.now(UTC)
            if now >= next_universe_refresh:
                import_company_universe(sec)
                next_universe_refresh = now + timedelta(hours=settings.universe_refresh_hours)

            symbols = select_symbols(settings)
            if not symbols:
                log_event("deep_loop_idle", sleep_seconds=settings.analysis_idle_seconds)
                stop.wait(settings.analysis_idle_seconds)
                continue

            log_event("deep_batch_selected", symbol_count=len(symbols), symbols=symbols[:25])
            succeeded, failures = analyze_batch(symbols, sec, prices)
            if succeeded:
                validate_results()
            log_event(
                "deep_batch_completed",
                attempted=len(symbols),
                succeeded=succeeded,
                failed=len(failures),
                failures=failures[:50],
            )
            stop.wait(settings.analysis_loop_delay_seconds)
        except Exception:
            logger.exception("deep analyzer batch failed")
            stop.wait(60)


def live_loop(prices: NasdaqProvider, stop: Event = stop_event) -> None:
    """The fast intraday price loop — cheaply refreshes current price / 1D move
    for already-analyzed securities so the screen updates near-live. Best-effort;
    it slows down outside regular market hours."""
    settings = get_settings()
    if not settings.live_quotes_enabled:
        log_event("live_loop_disabled")
        return
    log_event("live_loop_started", interval=settings.live_quote_interval_seconds)
    while not stop.is_set():
        try:
            open_now = is_market_open()
            with SessionLocal() as session:
                updated = run_live_cycle(session, settings, prices)
            log_event("live_cycle_completed", updated=updated, market_open=open_now)
            delay = (
                settings.live_quote_interval_seconds
                if open_now
                else settings.live_quote_offhours_seconds
            )
            stop.wait(delay)
        except Exception:
            logger.exception("live quote cycle failed")
            stop.wait(60)


def start_background_workers(
    stop: Event, run_deep: bool, run_live: bool
) -> list[threading.Thread]:
    """Start the analyzer loops as daemon threads (used to embed the analyzer in
    the always-on backend process so scanning is guaranteed to run non-stop)."""
    settings = get_settings()
    prices = NasdaqProvider()
    threads: list[threading.Thread] = []
    if run_live and settings.live_quotes_enabled:
        thread = threading.Thread(
            target=live_loop, args=(prices, stop), name="backend-live-loop", daemon=True
        )
        thread.start()
        threads.append(thread)
    if run_deep:
        sec = SecProvider(settings.sec_user_agent, Path(settings.market_data_path))
        thread = threading.Thread(
            target=deep_loop, args=(sec, prices, stop), name="backend-deep-loop", daemon=True
        )
        thread.start()
        threads.append(thread)
    log_event("background_workers_started", deep=run_deep, live=run_live, count=len(threads))
    return threads


def main() -> int:
    settings = get_settings()
    sec = SecProvider(settings.sec_user_agent, Path(settings.market_data_path))
    prices = NasdaqProvider()
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    log_event("continuous_analyzer_started", live_quotes=settings.live_quotes_enabled)
    live_thread = threading.Thread(
        target=live_loop, args=(prices,), name="live-loop", daemon=True
    )
    live_thread.start()
    # The deep loop runs on the main thread so signals stop the process cleanly.
    deep_loop(sec, prices)
    live_thread.join(timeout=10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
