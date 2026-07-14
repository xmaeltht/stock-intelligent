import json
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError

from sqlalchemy import func, or_, select

from app.analysis.etf import build_etf_analysis, build_technical_screen
from app.analysis.technicals import build_technical_indicators
from app.analysis.valuation import EMPTY_FINANCIALS, build_analysis
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis
from app.providers.nasdaq import NasdaqProvider
from app.providers.sec import SEC_FACTS_URL, SEC_TICKERS_URL, SecProvider, extract_financials

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("daily-pipeline")

# INN-PE, CFG-PH, and similar SEC tickers are preferred series, not common stock.
PREFERRED_PATTERN = re.compile(r"-P[A-Z]?$")


def log_event(event: str, **fields: object) -> None:
    logger.info(json.dumps({"event": event, "job": "daily-pipeline", **fields}))


def import_company_universe(provider: SecProvider) -> dict[str, Company]:
    companies = provider.company_universe()
    traded = provider.traded_instruments()
    asset_types = {item.symbol: item.asset_type for item in traded}
    tickers_by_cik: dict[str, set[str]] = {}
    for item in companies:
        tickers_by_cik.setdefault(item.cik, set()).add(item.ticker)
    with SessionLocal() as session:
        existing = {company.ticker: company for company in session.scalars(select(Company))}
        for item in companies:
            company = existing.get(item.ticker)
            if company is None:
                company = Company(
                    ticker=item.ticker,
                    name=item.name,
                    exchange=item.exchange,
                    cik=item.cik,
                )
                session.add(company)
                existing[item.ticker] = company
            else:
                company.name = item.name
                company.exchange = item.exchange
                company.cik = item.cik
                company.is_active = True
            company.asset_type = asset_types.get(item.ticker, "Stock")
            siblings = tickers_by_cik[item.cik]
            derivative_suffix = next(
                (
                    suffix
                    for suffix in ("WS", "W", "U", "R")
                    if item.ticker.endswith(suffix)
                    and item.ticker[: -len(suffix)] in siblings
                ),
                None,
            )
            if PREFERRED_PATTERN.search(item.ticker):
                company.is_research_eligible = False
                company.eligibility_reason = "Preferred share series, not common equity"
            else:
                company.is_research_eligible = derivative_suffix is None
                company.eligibility_reason = (
                    None
                    if derivative_suffix is None
                    else "Likely warrant, unit, or right with common-share sibling"
                )
        for item in traded:
            if item.asset_type != "ETF" or item.symbol in existing:
                continue
            company = Company(
                ticker=item.symbol,
                name=item.name,
                exchange=item.exchange,
                cik=None,
                asset_type="ETF",
                is_research_eligible=True,
            )
            session.add(company)
            existing[item.symbol] = company
        session.commit()
        result = {company.ticker: company for company in session.scalars(select(Company))}
    log_event("company_universe_imported", company_count=len(companies))
    return result


def analyze_symbol(symbol: str, sec: SecProvider, prices: NasdaqProvider) -> None:
    with SessionLocal() as session:
        company = session.scalar(select(Company).where(Company.ticker == symbol))
        if company is None or (company.cik is None and company.asset_type != "ETF"):
            raise ValueError(f"{symbol} is absent from the SEC company universe")

        quote = prices.latest_price(symbol, company.asset_type)
        indicators = build_technical_indicators(quote.history)
        if company.asset_type == "ETF":
            financials = dict(EMPTY_FINANCIALS)
            result = build_etf_analysis(
                quote.close, quote.volume, indicators, len(quote.history)
            )
            sources = [
                {"name": "Delayed ETF price history", "url": quote.source_url},
                {
                    "name": "Nasdaq Trader symbol directory",
                    "url": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt",
                },
            ]
        else:
            facts = None
            try:
                facts = sec.company_facts(company.cik)
            except HTTPError as error:
                if error.code != 404:
                    raise
                # Recently-public stocks (SPACs, new listings) and some trusts
                # have no XBRL facts yet. They still have price data, so screen
                # them technically instead of dropping them from the universe.
            if facts is None:
                financials = dict(EMPTY_FINANCIALS)
                result = build_technical_screen(
                    quote.close,
                    quote.volume,
                    indicators,
                    len(quote.history),
                    "Technical Screen Only",
                    extra_risks=[
                        {
                            "severity": "Moderate",
                            "title": "No SEC XBRL fundamentals published yet",
                        }
                    ],
                )
                sources = [
                    {"name": "Nasdaq delayed market price", "url": quote.source_url},
                    {"name": "SEC Company Universe", "url": SEC_TICKERS_URL},
                ]
            else:
                financials = extract_financials(facts)
                try:
                    result = build_analysis(financials, quote.close)
                except ValueError:
                    # Either no positive fundamental anchors a valuation
                    # (pre-revenue, unprofitable, non-USD filer) or the model
                    # produced an implausible result that failed the data-quality
                    # sanity check. Store a transparent technical-only screen.
                    result = build_technical_screen(
                        quote.close,
                        quote.volume,
                        indicators,
                        len(quote.history),
                        "Technical Screen Only",
                        extra_risks=[
                            {
                                "severity": "High",
                                "title": (
                                    "No reliable fundamental valuation "
                                    "(missing data or failed sanity check)"
                                ),
                            }
                        ],
                    )
                sources = [
                    {"name": "SEC Company Facts", "url": SEC_FACTS_URL.format(cik=company.cik)},
                    {"name": "Nasdaq delayed market price", "url": quote.source_url},
                    {"name": "SEC Company Universe", "url": SEC_TICKERS_URL},
                ]
        analysis = StockAnalysis(
            company_id=company.id,
            as_of=datetime.now(UTC),
            price_date=quote.date,
            current_price=quote.close,
            volume=quote.volume,
            price_history=quote.history,
            technical_indicators=indicators,
            revenue=financials["revenue"],
            previous_revenue=financials["previous_revenue"],
            net_income=financials["net_income"],
            free_cash_flow=financials["free_cash_flow"],
            cash=financials["cash"],
            debt=financials["debt"],
            shares_outstanding=financials["shares_outstanding"],
            eps=financials["eps"],
            sources=sources,
            **result,
        )
        session.add(analysis)
        company.analysis_attempted_at = datetime.now(UTC)
        company.analysis_error = None
        session.commit()
    log_event(
        "symbol_analyzed",
        symbol=symbol,
        price=float(quote.close),
        fair_value=float(result["fair_value"]),
        upside_pct=round(result["upside_pct"], 2),
        qualification=result["qualification"],
    )


def mark_analysis_failure(symbol: str, error: Exception) -> None:
    with SessionLocal() as session:
        company = session.scalar(select(Company).where(Company.ticker == symbol))
        if company is None:
            return
        company.analysis_attempted_at = datetime.now(UTC)
        company.analysis_error = str(error)[:1000]
        session.commit()


def eligible_filter(settings):
    return (
        Company.is_active.is_(True),
        Company.is_research_eligible.is_(True),
        or_(Company.cik.is_not(None), Company.asset_type == "ETF"),
        Company.exchange.in_(settings.exchange_list),
    )


def select_symbols(settings) -> list[str]:
    """Choose targeted symbols or the least-recently attempted eligible batch.

    Failed symbols cool down before retrying. Successful symbols naturally return
    to the front after every unattempted company has received its first analysis.
    """
    if settings.symbol_list:
        return settings.symbol_list

    retry_before = datetime.now(UTC) - timedelta(hours=settings.analysis_retry_hours)
    refresh_before = datetime.now(UTC) - timedelta(hours=settings.analysis_refresh_hours)
    with SessionLocal() as session:
        statement = (
            select(Company.ticker)
            .where(
                *eligible_filter(settings),
                (
                    (Company.analysis_attempted_at.is_(None))
                    | (
                        Company.analysis_error.is_(None)
                        & (Company.analysis_attempted_at <= refresh_before)
                    )
                    | (
                        Company.analysis_error.is_not(None)
                        & (Company.analysis_attempted_at <= retry_before)
                    )
                ),
            )
            .order_by(Company.analysis_attempted_at.asc().nullsfirst(), Company.ticker.asc())
            .limit(settings.analysis_batch_size)
        )
        return list(session.scalars(statement))


def validate_results() -> tuple[int, int]:
    with SessionLocal() as session:
        count = session.scalar(select(func.count()).select_from(StockAnalysis)) or 0
        qualified = session.scalar(
            select(func.count()).select_from(StockAnalysis).where(StockAnalysis.upside_pct >= 90)
        ) or 0
    if count == 0:
        raise RuntimeError("Pipeline produced no usable stock analyses")
    log_event("results_validated", analysis_count=count, qualified_count=qualified)
    return count, qualified


def analyze_batch(
    symbols: list[str], sec: SecProvider, prices: NasdaqProvider
) -> tuple[int, list[dict[str, str]]]:
    """Analyze a batch concurrently; shared provider rate limiters keep the
    combined request rate to each upstream source polite."""
    settings = get_settings()
    succeeded = 0
    failures: list[dict[str, str]] = []

    def run(symbol: str) -> tuple[str, Exception | None]:
        try:
            analyze_symbol(symbol, sec, prices)
            return symbol, None
        except Exception as exc:  # noqa: BLE001 - one symbol must not sink the batch
            return symbol, exc

    with ThreadPoolExecutor(max_workers=settings.analysis_workers) as pool:
        for symbol, error in pool.map(run, symbols):
            if error is None:
                succeeded += 1
            else:
                logger.error("symbol analysis failed: %s: %s", symbol, error)
                mark_analysis_failure(symbol, error)
                failures.append({"symbol": symbol, "error": str(error)})
    return succeeded, failures


def main() -> int:
    settings = get_settings()
    cache_dir = Path(settings.market_data_path)
    sec = SecProvider(settings.sec_user_agent, cache_dir)
    prices = NasdaqProvider()
    log_event(
        "pipeline_started",
        mode="targeted" if settings.symbol_list else "eligible-universe",
        batch_size=settings.analysis_batch_size,
    )
    try:
        import_company_universe(sec)
        symbols = select_symbols(settings)
        log_event("analysis_batch_selected", symbol_count=len(symbols), symbols=symbols[:25])
        if not symbols:
            log_event("pipeline_completed", succeeded=0, failed=0, failures=[])
            return 0
        succeeded, failures = analyze_batch(symbols, sec, prices)
        if succeeded:
            validate_results()
        elif failures:
            raise RuntimeError(f"All symbol analyses failed: {failures[:20]}")
    except Exception:
        logger.exception(json.dumps({"event": "pipeline_failed", "job": "daily-pipeline"}))
        return 1
    log_event(
        "pipeline_completed",
        attempted=len(symbols),
        succeeded=succeeded,
        failed=len(failures),
        failures=failures[:50],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
