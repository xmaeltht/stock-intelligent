from app.analysis.technicals import build_technical_indicators


def test_empty_history_has_no_technical_claims() -> None:
    assert build_technical_indicators([]) == {}


def test_rising_history_produces_a_complete_indicator_set() -> None:
    history = [{"close": float(index), "volume": index * 1000} for index in range(1, 61)]

    indicators = build_technical_indicators(history)

    assert indicators["sma20"] == 50.5
    assert indicators["sma50"] == 35.5
    assert indicators["rsi14"] == 100.0
    # Rising price, trend, volume, and momentum pass; the RSI band check fails at 100.
    assert indicators["confirmations"] == 5
    assert indicators["signal"] == "Bullish"
    assert len(indicators["checks"]) == 6
    assert indicators["impulse_macd"] in {"Bullish", "Neutral", "Bearish"}
    assert isinstance(indicators["macd_histogram"], float)
    assert indicators["bb_upper"] > indicators["bb_lower"]
    assert indicators["atr14"] is not None
    assert indicators["support"] > 0
    assert indicators["resistance"] == 60.0
    assert indicators["volume_trend"] == "Rising"
    assert indicators["change_1d_pct"] is not None


def test_ohlc_history_uses_true_range_and_extremes() -> None:
    history = [
        {
            "close": 100.0 + index,
            "open": 99.5 + index,
            "high": 101.0 + index,
            "low": 99.0 + index,
            "volume": 1_000_000,
        }
        for index in range(70)
    ]

    indicators = build_technical_indicators(history)

    assert indicators["resistance"] == 101.0 + 69
    assert indicators["support"] == 99.0 + 7  # last 63 sessions start at index 7
    assert indicators["atr14"] >= 2.0  # daily high-low span dominates the true range
