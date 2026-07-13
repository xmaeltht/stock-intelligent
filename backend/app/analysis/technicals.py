from statistics import mean, pstdev


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append((value - result[-1]) * multiplier + result[-1])
    return result


def _wilder_rsi(closes: list[float], period: int = 14) -> float | None:
    """RSI with Wilder smoothing over the full series, not a single window."""
    if len(closes) <= period:
        return None
    changes = [current - previous for previous, current in zip(closes, closes[1:], strict=False)]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = mean(gains[:period])
    average_loss = mean(losses[:period])
    for gain, loss in zip(gains[period:], losses[period:], strict=True):
        average_gain = (average_gain * (period - 1) + gain) / period
        average_loss = (average_loss * (period - 1) + loss) / period
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return round(100 - (100 / (1 + relative_strength)), 2)


def _sma_series(values: list[float], period: int) -> list[float | None]:
    return [
        mean(values[index + 1 - period : index + 1]) if index + 1 >= period else None
        for index in range(len(values))
    ]


def _atr(history: list[dict[str, object]], period: int = 14) -> float | None:
    """Average True Range; falls back to close-to-close range without OHLC data."""
    if len(history) <= period:
        return None
    true_ranges: list[float] = []
    for previous, current in zip(history, history[1:], strict=False):
        previous_close = float(previous["close"])  # type: ignore[arg-type]
        close = float(current["close"])  # type: ignore[arg-type]
        high = float(current.get("high") or max(close, previous_close))  # type: ignore[arg-type]
        low = float(current.get("low") or min(close, previous_close))  # type: ignore[arg-type]
        true_ranges.append(
            max(high - low, abs(high - previous_close), abs(low - previous_close))
        )
    atr = mean(true_ranges[:period])
    for true_range in true_ranges[period:]:
        atr = (atr * (period - 1) + true_range) / period
    return atr


def _pct_change(closes: list[float], sessions: int) -> float | None:
    if len(closes) <= sessions or closes[-1 - sessions] == 0:
        return None
    return round((closes[-1] / closes[-1 - sessions] - 1) * 100, 2)


def _detect_cross(
    sma_fast: list[float | None], sma_slow: list[float | None], lookback: int = 15
) -> tuple[str | None, int | None]:
    """Detect a fast/slow SMA cross within the last `lookback` sessions."""
    pairs = [
        (fast, slow)
        for fast, slow in zip(sma_fast, sma_slow, strict=True)
        if fast is not None and slow is not None
    ]
    if len(pairs) < 2:
        return None, None
    recent = pairs[-(lookback + 1) :]
    steps = list(zip(recent, recent[1:], strict=False))
    for age, ((prev_fast, prev_slow), (fast, slow)) in enumerate(reversed(steps)):
        if prev_fast <= prev_slow and fast > slow:
            return "Golden cross", age
        if prev_fast >= prev_slow and fast < slow:
            return "Death cross", age
    return None, None


def build_technical_indicators(history: list[dict[str, object]]) -> dict[str, object]:
    if not history:
        return {}
    closes = [float(point["close"]) for point in history]  # type: ignore[arg-type]
    volumes = [float(point["volume"] or 0) for point in history]  # type: ignore[arg-type]
    latest = closes[-1]

    sma20 = mean(closes[-20:]) if len(closes) >= 20 else None
    sma50 = mean(closes[-50:]) if len(closes) >= 50 else None
    sma200 = mean(closes[-200:]) if len(closes) >= 200 else None
    high_52w = max(closes)
    low_52w = min(closes)
    rsi14 = _wilder_rsi(closes)

    ema13 = _ema(closes, 13)
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_series = [fast - slow for fast, slow in zip(ema12, ema26, strict=True)]
    macd_signal_series = _ema(macd_series, 9)
    histogram = [
        macd - signal
        for macd, signal in zip(macd_series, macd_signal_series, strict=True)
    ]
    price_rising = len(ema13) > 1 and ema13[-1] > ema13[-2]
    price_falling = len(ema13) > 1 and ema13[-1] < ema13[-2]
    momentum_rising = len(histogram) > 1 and histogram[-1] > histogram[-2]
    momentum_falling = len(histogram) > 1 and histogram[-1] < histogram[-2]
    impulse = (
        "Bullish"
        if price_rising and momentum_rising
        else "Bearish"
        if price_falling and momentum_falling
        else "Neutral"
    )

    # Bollinger Bands (20, 2)
    bb_upper = bb_lower = bb_percent_b = None
    if len(closes) >= 20:
        window = closes[-20:]
        deviation = pstdev(window)
        middle = mean(window)
        bb_upper = middle + 2 * deviation
        bb_lower = middle - 2 * deviation
        if bb_upper > bb_lower:
            bb_percent_b = (latest - bb_lower) / (bb_upper - bb_lower) * 100

    atr14 = _atr(history)
    atr_pct = (atr14 / latest * 100) if atr14 is not None and latest > 0 else None

    # Support and resistance from roughly the last quarter of trading
    recent = history[-63:]
    support = min(float(point.get("low") or point["close"]) for point in recent)  # type: ignore[arg-type]
    resistance = max(float(point.get("high") or point["close"]) for point in recent)  # type: ignore[arg-type]

    volume_avg20 = mean(volumes[-20:]) if len(volumes) >= 20 else None
    volume_avg50 = mean(volumes[-50:]) if len(volumes) >= 50 else None
    volume_trend = None
    if volume_avg20 is not None and volume_avg50 is not None and volume_avg50 > 0:
        ratio = volume_avg20 / volume_avg50
        volume_trend = "Rising" if ratio > 1.1 else "Falling" if ratio < 0.9 else "Flat"

    cross, cross_age = _detect_cross(_sma_series(closes, 50), _sma_series(closes, 200))

    checks = [
        {
            "name": "Price above SMA-20",
            "passed": bool(sma20 is not None and latest > sma20),
        },
        {
            "name": "Price above SMA-50",
            "passed": bool(sma50 is not None and latest > sma50),
        },
        {
            "name": "SMA-20 above SMA-50",
            "passed": bool(sma20 is not None and sma50 is not None and sma20 > sma50),
        },
        {
            "name": "RSI-14 between 45 and 70",
            "passed": bool(rsi14 is not None and 45 <= rsi14 <= 70),
        },
        {
            "name": "20-day volume above 50-day volume",
            "passed": bool(
                volume_avg20 is not None
                and volume_avg50 is not None
                and volume_avg20 > volume_avg50
            ),
        },
        {
            "name": "MACD above its signal line",
            "passed": bool(macd_series and macd_series[-1] > macd_signal_series[-1]),
        },
    ]
    confirmations = sum(bool(check["passed"]) for check in checks)
    signal = (
        "Bullish" if confirmations >= 5 else "Neutral" if confirmations >= 3 else "Bearish"
    )
    range_position = (
        (latest - low_52w) / (high_52w - low_52w) * 100 if high_52w > low_52w else 50
    )
    return {
        "sma20": round(sma20, 4) if sma20 is not None else None,
        "sma50": round(sma50, 4) if sma50 is not None else None,
        "sma200": round(sma200, 4) if sma200 is not None else None,
        "rsi14": rsi14,
        "high_52w": round(high_52w, 4),
        "low_52w": round(low_52w, 4),
        "range_position_pct": round(range_position, 1),
        "bb_upper": round(bb_upper, 4) if bb_upper is not None else None,
        "bb_lower": round(bb_lower, 4) if bb_lower is not None else None,
        "bb_percent_b": round(bb_percent_b, 1) if bb_percent_b is not None else None,
        "atr14": round(atr14, 4) if atr14 is not None else None,
        "atr_pct": round(atr_pct, 2) if atr_pct is not None else None,
        "support": round(support, 4),
        "resistance": round(resistance, 4),
        "volume_avg20": round(volume_avg20) if volume_avg20 is not None else None,
        "volume_avg50": round(volume_avg50) if volume_avg50 is not None else None,
        "volume_trend": volume_trend,
        "trend_cross": cross,
        "trend_cross_age_days": cross_age,
        "change_1d_pct": _pct_change(closes, 1),
        "change_5d_pct": _pct_change(closes, 5),
        "change_20d_pct": _pct_change(closes, 20),
        "confirmations": confirmations,
        "checks": checks,
        "signal": signal,
        "macd": round(macd_series[-1], 4),
        "macd_signal": round(macd_signal_series[-1], 4),
        "macd_histogram": round(histogram[-1], 4),
        "impulse_macd": impulse,
    }
