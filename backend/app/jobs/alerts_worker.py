"""Background alert evaluation.

Runs in the always-on backend so a rule crosses and fires even when the owner
isn't in the app. Cheap (a couple of queries per cycle) and fully guarded — a
failed cycle logs and retries rather than killing the thread.
"""

import logging
import threading
from threading import Event

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.alerts import dispatch_alert_emails, evaluate_all_active

logger = logging.getLogger("stock-intelligence")


def run_alerts_loop(stop: Event, interval_seconds: int) -> None:
    stop.wait(15)  # let startup settle before the first pass
    while not stop.is_set():
        try:
            with SessionLocal() as session:
                created = evaluate_all_active(session)
                emailed = dispatch_alert_emails(session) if get_settings().email_enabled else 0
            if created or emailed:
                logger.info("alerts worker: %d event(s), %d email(s)", created, emailed)
        except Exception:  # noqa: BLE001 - never let one bad cycle end the loop
            logger.exception("alerts evaluation cycle failed")
        stop.wait(interval_seconds)


def start_alerts_worker(stop: Event, interval_seconds: int) -> threading.Thread:
    thread = threading.Thread(
        target=run_alerts_loop, args=(stop, interval_seconds), name="alerts-worker", daemon=True
    )
    thread.start()
    return thread
