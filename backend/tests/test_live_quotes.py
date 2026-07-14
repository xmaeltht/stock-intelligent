from datetime import UTC, datetime
from decimal import Decimal

from app.jobs.live_quotes import apply_live_quote, is_market_open, market_session
from app.models.stock_analysis import StockAnalysis
from app.providers.nasdaq import LiveQuote, parse_stooq_light, parse_yahoo_quote


def test_market_open_weekday_midday() -> None:
    # 2026-07-14 is a Tuesday; 14:00 UTC == 10:00 ET (open).
    assert is_market_open(datetime(2026, 7, 14, 14, 0, tzinfo=UTC)) is True
    # 02:00 UTC == 22:00 ET prior day (overnight, not the regular session).
    assert is_market_open(datetime(2026, 7, 14, 2, 0, tzinfo=UTC)) is False


def test_market_closed_weekend() -> None:
    # 2026-07-18 is a Saturday.
    assert is_market_open(datetime(2026, 7, 18, 15, 0, tzinfo=UTC)) is False


def test_market_sessions() -> None:
    # Tuesday 2026-07-14, times in UTC (ET = UTC-4 in July).
    assert market_session(datetime(2026, 7, 14, 12, 0, tzinfo=UTC)) == "pre"  # 08:00 ET
    assert market_session(datetime(2026, 7, 14, 14, 0, tzinfo=UTC)) == "regular"  # 10:00 ET
    assert market_session(datetime(2026, 7, 14, 21, 0, tzinfo=UTC)) == "after"  # 17:00 ET
    assert market_session(datetime(2026, 7, 14, 2, 0, tzinfo=UTC)) == "overnight"  # Mon 22:00 ET
    assert market_session(datetime(2026, 7, 18, 15, 0, tzinfo=UTC)) == "closed"  # Saturday


def test_yahoo_quote_prefers_premarket_price() -> None:
    payload = {
        "quoteResponse": {
            "result": [
                {
                    "symbol": "AAPL",
                    "marketState": "PRE",
                    "regularMarketPrice": 200.0,
                    "regularMarketChangePercent": 0.0,
                    "preMarketPrice": 205.0,
                    "preMarketChangePercent": 2.5,
                    "regularMarketVolume": 1000,
                },
                {
                    "symbol": "MSFT",
                    "marketState": "POST",
                    "regularMarketPrice": 500.0,
                    "postMarketPrice": 495.0,
                    "postMarketChangePercent": -1.0,
                },
            ]
        }
    }
    quotes = {q.symbol: q for q in parse_yahoo_quote(payload)}
    assert quotes["AAPL"].price == Decimal("205.0")  # pre-market price wins
    assert quotes["AAPL"].change_pct == 2.5
    assert quotes["MSFT"].price == Decimal("495.0")  # after-hours price wins
    assert quotes["MSFT"].market_state == "POST"


def test_parse_stooq_light_maps_symbols() -> None:
    csv_text = (
        "Symbol,Date,Time,Open,High,Low,Close,Volume,Name\n"
        "AAPL.US,2026-07-14,21:00:00,210,215,209,214.5,50000000,Apple\n"
        "BRK-B.US,2026-07-14,21:00:00,400,405,399,404.2,1200000,Berkshire\n"
        "ZZZZ.US,N/D,N/D,N/D,N/D,N/D,N/D,N/D,N/D\n"
    )
    symbol_map = {"aapl.us": "AAPL", "brk-b.us": "BRK-B", "zzzz.us": "ZZZZ"}
    quotes = parse_stooq_light(csv_text, symbol_map)
    by_symbol = {q.symbol: q for q in quotes}
    assert by_symbol["AAPL"].price == Decimal("214.5")
    assert by_symbol["AAPL"].volume == 50000000
    assert by_symbol["BRK-B"].price == Decimal("404.2")
    assert "ZZZZ" not in by_symbol  # no usable close is dropped


def test_parse_yahoo_quote() -> None:
    payload = {
        "quoteResponse": {
            "result": [
                {"symbol": "MSFT", "regularMarketPrice": 500.1,
                 "regularMarketChangePercent": 1.2, "regularMarketVolume": 3000000},
                {"symbol": "BAD", "regularMarketPrice": 0},
            ]
        }
    }
    quotes = parse_yahoo_quote(payload)
    assert len(quotes) == 1
    assert quotes[0].symbol == "MSFT"
    assert quotes[0].change_pct == 1.2


def test_apply_live_quote_updates_price_upside_and_today_bar() -> None:
    analysis = StockAnalysis(
        as_of=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
        price_date=datetime(2026, 7, 13).date(),
        current_price=Decimal("100"),
        volume=1000,
        price_history=[
            {"date": "2026-07-10", "open": 95, "high": 99, "low": 94, "close": 98, "volume": 900},
            {"date": "2026-07-13", "open": 98, "high": 101, "low": 97, "close": 100,
             "volume": 1000},
        ],
        technical_indicators={"change_1d_pct": 0.0},
        fair_value=Decimal("150"),
        upside_pct=50.0,
    )
    now = datetime(2026, 7, 14, 17, 0, tzinfo=UTC)  # 13:00 ET, market open
    changed = apply_live_quote(analysis, LiveQuote("X", Decimal("110"), 2000, None, "stooq"), now)

    assert changed is True
    assert analysis.current_price == Decimal("110")
    # upside recomputed against the fixed fair value: 150/110 - 1 = 36.36%
    assert round(analysis.upside_pct, 1) == 36.4
    # a new bar for 2026-07-14 (ET) was appended and reflects the live price
    assert analysis.price_history[-1]["date"] == "2026-07-14"
    assert analysis.price_history[-1]["close"] == 110.0
    # 1D change computed from the prior stored close (110/100 - 1 = 10%)
    assert analysis.technical_indicators["change_1d_pct"] == 10.0
    assert analysis.price_as_of == now


def test_apply_live_quote_patches_same_day_bar() -> None:
    analysis = StockAnalysis(
        as_of=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
        price_date=datetime(2026, 7, 14).date(),
        current_price=Decimal("100"),
        volume=1000,
        price_history=[
            {"date": "2026-07-13", "open": 98, "high": 101, "low": 97, "close": 99, "volume": 900},
            {"date": "2026-07-14", "open": 100, "high": 102, "low": 98, "close": 100,
             "volume": 1000},
        ],
        technical_indicators={},
        fair_value=Decimal("120"),
        upside_pct=20.0,
    )
    now = datetime(2026, 7, 14, 18, 0, tzinfo=UTC)
    apply_live_quote(analysis, LiveQuote("X", Decimal("105"), 1500, None, "stooq"), now)

    # same-day bar is patched, not duplicated
    assert len(analysis.price_history) == 2
    assert analysis.price_history[-1]["close"] == 105.0
    assert analysis.price_history[-1]["high"] == 105.0  # new high
    # change computed vs prior day close (105/99 - 1 = 6.06%)
    assert analysis.technical_indicators["change_1d_pct"] == 6.06
