import csv
import io
import json
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.providers.http import RateLimiter

# Public data endpoints throttle aggressively when hit in bursts. Shared
# limiters keep the combined request rate polite even with concurrent workers;
# one backoff retry converts most transient empties into data.
RETRY_DELAY_SECONDS = 3.0
NASDAQ_LIMITER = RateLimiter(0.4)
YAHOO_LIMITER = RateLimiter(0.5)
STOOQ_LIMITER = RateLimiter(0.3)


@dataclass(frozen=True)
class PriceQuote:
    symbol: str
    date: date
    close: Decimal
    volume: int | None
    history: list[dict[str, object]]
    source_url: str


@dataclass(frozen=True)
class LiveQuote:
    """A lightweight intraday snapshot for the fast refresh loop."""

    symbol: str
    price: Decimal
    volume: int | None
    change_pct: float | None
    source: str


def _clean_number(raw: object) -> float | None:
    text = str(raw or "").replace("$", "").replace(",", "").strip()
    if not text or text in {"N/A", "--"}:
        return None
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def _quote_from_history(
    symbol: str, history: list[dict[str, object]], source_url: str
) -> PriceQuote:
    history.sort(key=lambda point: str(point["date"]))
    latest = history[-1]
    return PriceQuote(
        symbol=symbol,
        date=date.fromisoformat(str(latest["date"])),
        close=Decimal(str(latest["close"])),
        volume=int(latest["volume"]) if latest["volume"] is not None else None,
        history=history,
        source_url=source_url,
    )


def _stooq_batch_symbol(ticker: str) -> str:
    # Stooq uses dashes for share classes and a `.us` suffix (BRK-B -> brk-b.us).
    return f"{ticker.lower().replace('.', '-')}.us"


def parse_stooq_light(payload: str, symbol_map: dict[str, str]) -> list["LiveQuote"]:
    """Parse a Stooq light-quote CSV batch. `symbol_map` maps the request symbol
    (e.g. `aapl.us`) back to our canonical ticker."""
    quotes: list[LiveQuote] = []
    for row in csv.DictReader(io.StringIO(payload)):
        request_symbol = str(row.get("Symbol") or "").strip().lower()
        ticker = symbol_map.get(request_symbol)
        if ticker is None:
            continue
        close = _clean_number(row.get("Close"))
        if close is None or close <= 0:
            continue
        raw_volume = str(row.get("Volume") or "").split(".")[0]
        quotes.append(
            LiveQuote(
                symbol=ticker,
                price=Decimal(str(close)),
                volume=int(raw_volume) if raw_volume.isdigit() else None,
                change_pct=None,  # computed by the loop from stored prior close
                source="stooq",
            )
        )
    return quotes


def parse_yahoo_quote(payload: dict) -> list["LiveQuote"]:
    results = ((payload or {}).get("quoteResponse") or {}).get("result") or []
    quotes: list[LiveQuote] = []
    for item in results:
        symbol = str(item.get("symbol") or "").upper()
        price = item.get("regularMarketPrice")
        if not symbol or not isinstance(price, int | float) or price <= 0:
            continue
        change = item.get("regularMarketChangePercent")
        volume = item.get("regularMarketVolume")
        quotes.append(
            LiveQuote(
                symbol=symbol,
                price=Decimal(str(price)),
                volume=int(volume) if isinstance(volume, int | float) else None,
                change_pct=float(change) if isinstance(change, int | float) else None,
                source="yahoo",
            )
        )
    return quotes


class NasdaqProvider:
    def batch_quotes(self, symbols: list[str], chunk_size: int = 40) -> dict[str, "LiveQuote"]:
        """Fetch lightweight intraday snapshots for many symbols per request.

        Best-effort: tries a Stooq light-quote batch first (no auth, tolerant of
        bulk access), then Yahoo's batch quote endpoint as a fallback. Any symbol
        that can't be refreshed is simply omitted — the caller keeps its prior
        value. Never raises for individual failures so the loop keeps running.
        """
        found: dict[str, LiveQuote] = {}
        pending = [symbol.upper() for symbol in symbols if symbol]
        for start in range(0, len(pending), chunk_size):
            chunk = pending[start : start + chunk_size]
            for quote in self._stooq_batch(chunk):
                found.setdefault(quote.symbol, quote)
            missing = [symbol for symbol in chunk if symbol not in found]
            if missing:
                for quote in self._yahoo_batch(missing):
                    found.setdefault(quote.symbol, quote)
        return found

    def _stooq_batch(self, chunk: list[str]) -> list["LiveQuote"]:
        symbol_map = {_stooq_batch_symbol(ticker): ticker for ticker in chunk}
        joined = "+".join(symbol_map)
        url = f"https://stooq.com/q/l/?s={joined}&f=sd2t2ohlcvn&h&e=csv"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 StockIntelligence/0.2"})
        try:
            STOOQ_LIMITER.wait()
            with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed provider URL
                payload = response.read().decode("utf-8", errors="replace")
            return parse_stooq_light(payload, symbol_map)
        except Exception:  # noqa: BLE001 - batch refresh is best-effort
            return []

    def _yahoo_batch(self, chunk: list[str]) -> list["LiveQuote"]:
        joined = ",".join(chunk)
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={joined}"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 StockIntelligence/0.2"})
        try:
            YAHOO_LIMITER.wait()
            with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed provider URL
                payload = json.load(response)
            return parse_yahoo_quote(payload)
        except Exception:  # noqa: BLE001 - batch refresh is best-effort
            return []

    def latest_price(self, symbol: str, asset_type: str = "Stock") -> PriceQuote:
        ticker = symbol.upper()
        # Yahoo's chart endpoint is the most tolerant of concurrent/bulk access
        # and returns full OHLCV for both stocks and ETFs, so it leads the
        # fallback chain. api.nasdaq.com blocks datacenter/bulk traffic and
        # Stooq enforces a daily per-IP download cap, so both are last resorts.
        sources = (self._yahoo_price, self._nasdaq_price, self._stooq_price)
        if asset_type == "ETF":
            sources = (self._yahoo_price, self._stooq_price)
        errors: list[str] = []
        for source in sources:
            try:
                return source(ticker)
            except Exception as exc:  # noqa: BLE001 - try every source before failing
                errors.append(f"{source.__name__.lstrip('_')}: {exc}")
        raise ValueError(
            f"No daily price history available for {ticker} ({'; '.join(errors)})"
        )

    def _nasdaq_price(self, ticker: str) -> PriceQuote:
        # SEC tickers use dashes for share classes (BRK-B); Nasdaq expects dots.
        nasdaq_symbol = ticker.replace("-", ".")
        today = date.today()
        from_date = today - timedelta(days=370)
        url = (
            f"https://api.nasdaq.com/api/quote/{nasdaq_symbol}/historical"
            f"?assetclass=stocks&fromdate={from_date:%m/%d/%Y}"
            f"&todate={today:%m/%d/%Y}&limit=260"
        )
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 StockIntelligence/0.2",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://www.nasdaq.com",
                "Referer": (
                    f"https://www.nasdaq.com/market-activity/stocks/"
                    f"{nasdaq_symbol.lower()}/historical"
                ),
            },
        )
        history: list[dict[str, object]] = []
        for attempt in range(2):
            if attempt:
                time.sleep(RETRY_DELAY_SECONDS)
            NASDAQ_LIMITER.wait()
            with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed provider URL
                payload = json.load(response)
            rows = ((payload.get("data") or {}).get("tradesTable") or {}).get("rows") or []
            for row in rows:
                close = _clean_number(row.get("close"))
                raw_volume = str(row.get("volume") or "").replace(",", "")
                raw_date = str(row.get("date") or "")
                if close is None or not raw_date:
                    continue
                try:
                    point_date = datetime.strptime(raw_date, "%m/%d/%Y").date()
                except ValueError:
                    continue
                history.append(
                    {
                        "date": point_date.isoformat(),
                        "open": _clean_number(row.get("open")),
                        "high": _clean_number(row.get("high")),
                        "low": _clean_number(row.get("low")),
                        "close": close,
                        "volume": int(raw_volume) if raw_volume.isdigit() else None,
                    }
                )
            if history:
                break
        if not history:
            raise ValueError(f"No Nasdaq daily history available for {ticker}")
        return _quote_from_history(ticker, history, url)

    def _yahoo_price(self, ticker: str) -> PriceQuote:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            "?range=1y&interval=1d&events=history"
        )
        request = Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 StockIntelligence/0.2"},
        )
        payload = None
        attempts = 3
        for attempt in range(attempts):
            if attempt:
                time.sleep(RETRY_DELAY_SECONDS * attempt)
            YAHOO_LIMITER.wait()
            try:
                with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed provider URL
                    payload = json.load(response)
                break
            except HTTPError as error:
                if error.code not in (429, 503) or attempt == attempts - 1:
                    raise
        results = ((payload or {}).get("chart") or {}).get("result") or []
        if not results:
            raise ValueError(f"No ETF chart history available for {ticker}")
        result = results[0]
        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        history: list[dict[str, object]] = []
        for index, timestamp in enumerate(timestamps):
            close = closes[index] if index < len(closes) else None
            if close is None:
                continue
            volume = volumes[index] if index < len(volumes) else None
            point_date = datetime.fromtimestamp(int(timestamp), tz=UTC).date()
            history.append(
                {
                    "date": point_date.isoformat(),
                    "open": opens[index] if index < len(opens) else None,
                    "high": highs[index] if index < len(highs) else None,
                    "low": lows[index] if index < len(lows) else None,
                    "close": float(close),
                    "volume": int(volume) if volume is not None else None,
                }
            )
        if not history:
            raise ValueError(f"No usable ETF chart history available for {ticker}")
        return _quote_from_history(ticker, history, url)

    def _stooq_price(self, ticker: str) -> PriceQuote:
        """Full daily OHLCV history fallback from Stooq."""
        stooq_symbol = f"{ticker.lower().replace('.', '-')}.us"
        cutoff = (date.today() - timedelta(days=370)).isoformat()
        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 StockIntelligence/0.2"})
        STOOQ_LIMITER.wait()
        with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed provider URL
            payload = response.read().decode("utf-8", errors="replace")
        history: list[dict[str, object]] = []
        for row in csv.DictReader(io.StringIO(payload)):
            raw_date = str(row.get("Date") or "")
            close = _clean_number(row.get("Close"))
            if close is None or not raw_date or raw_date < cutoff:
                continue
            raw_volume = str(row.get("Volume") or "").split(".")[0]
            history.append(
                {
                    "date": raw_date,
                    "open": _clean_number(row.get("Open")),
                    "high": _clean_number(row.get("High")),
                    "low": _clean_number(row.get("Low")),
                    "close": close,
                    "volume": int(raw_volume) if raw_volume.isdigit() else None,
                }
            )
        if not history:
            raise ValueError(f"No daily price history available for {ticker}")
        return _quote_from_history(ticker, history, url)
