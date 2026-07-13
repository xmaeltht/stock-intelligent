import csv
import io
import json
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# Public data endpoints throttle aggressively when hit in tight loops. A small
# polite delay plus one backoff retry converts most transient empties into data.
REQUEST_DELAY_SECONDS = 0.35
RETRY_DELAY_SECONDS = 3.0


@dataclass(frozen=True)
class PriceQuote:
    symbol: str
    date: date
    close: Decimal
    volume: int | None
    history: list[dict[str, object]]
    source_url: str


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


class NasdaqProvider:
    def latest_price(self, symbol: str, asset_type: str = "Stock") -> PriceQuote:
        ticker = symbol.upper()
        if asset_type == "ETF":
            try:
                return self._yahoo_price(ticker)
            except Exception:
                return self._stooq_price(ticker)
        try:
            return self._nasdaq_price(ticker)
        except Exception:
            # Nasdaq throttles bursts; Stooq keeps full daily OHLC history.
            return self._stooq_price(ticker)

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
            time.sleep(REQUEST_DELAY_SECONDS if attempt == 0 else RETRY_DELAY_SECONDS)
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
        for attempt in range(2):
            time.sleep(REQUEST_DELAY_SECONDS if attempt == 0 else RETRY_DELAY_SECONDS)
            try:
                with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed provider URL
                    payload = json.load(response)
                break
            except HTTPError as error:
                if error.code not in (429, 503) or attempt == 1:
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
        time.sleep(REQUEST_DELAY_SECONDS)
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
