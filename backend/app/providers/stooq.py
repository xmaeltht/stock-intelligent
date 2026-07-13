import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.providers.http import fetch_bytes


@dataclass(frozen=True)
class PriceQuote:
    symbol: str
    date: date
    close: Decimal
    source_url: str


class StooqProvider:
    def __init__(self, user_agent: str, cache_dir: Path):
        self.user_agent = user_agent
        self.cache_dir = cache_dir

    def latest_price(self, symbol: str) -> PriceQuote:
        provider_symbol = f"{symbol.lower().replace('.', '-')}.us"
        url = f"https://stooq.com/q/l/?s={provider_symbol}&f=sd2t2ohlcv&h&e=csv"
        payload = fetch_bytes(url, self.user_agent)
        path = self.cache_dir / "stooq" / f"{symbol.upper()}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
        if not rows or rows[0].get("Close") in {None, "", "N/D"}:
            raise ValueError(f"No Stooq price available for {symbol}")
        row = rows[0]
        return PriceQuote(
            symbol=symbol.upper(),
            date=date.fromisoformat(row["Date"]),
            close=Decimal(row["Close"]),
            source_url=url,
        )
