import json
import logging
import sys
from collections.abc import Callable

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.company import Company

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("daily-pipeline")


def log_event(event: str, **fields: object) -> None:
    logger.info(json.dumps({"event": event, "job": "daily-pipeline", **fields}))


def inspect_company_universe() -> None:
    with SessionLocal() as session:
        company_count = session.scalar(select(func.count()).select_from(Company)) or 0
    log_event("company_universe_inspected", company_count=company_count)


def placeholder_stage(stage: str) -> Callable[[], None]:
    def run() -> None:
        log_event("stage_skipped", stage=stage, reason="provider not configured")

    return run


def main() -> int:
    stages: list[tuple[str, Callable[[], None]]] = [
        ("inspect_company_universe", inspect_company_universe),
        ("update_prices", placeholder_stage("update_prices")),
        ("update_financials", placeholder_stage("update_financials")),
        ("update_filings", placeholder_stage("update_filings")),
        ("detect_catalysts_and_risks", placeholder_stage("detect_catalysts_and_risks")),
        ("calculate_valuations", placeholder_stage("calculate_valuations")),
        ("calculate_opportunity_scores", placeholder_stage("calculate_opportunity_scores")),
        ("validate_results", placeholder_stage("validate_results")),
    ]
    log_event("pipeline_started", stage_count=len(stages))
    try:
        for stage_name, stage in stages:
            log_event("stage_started", stage=stage_name)
            stage()
            log_event("stage_completed", stage=stage_name)
    except Exception:
        logger.exception(json.dumps({"event": "pipeline_failed", "job": "daily-pipeline"}))
        return 1
    log_event("pipeline_completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

