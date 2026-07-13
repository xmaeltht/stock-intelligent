from decimal import Decimal
from statistics import median

CORE_FIELDS = (
    "revenue",
    "previous_revenue",
    "net_income",
    "free_cash_flow",
    "cash",
    "debt",
    "shares_outstanding",
    "eps",
)

EMPTY_FINANCIALS: dict[str, object] = {
    "revenue": None,
    "previous_revenue": None,
    "net_income": None,
    "free_cash_flow": None,
    "cash": None,
    "debt": None,
    "shares_outstanding": None,
    "eps": None,
    "equity": None,
    "operating_income": None,
    "gross_profit": None,
    "revenue_history": [],
    "net_income_history": [],
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def _ratio(numerator: Decimal | None, denominator: Decimal | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round(float(numerator / denominator), 2)


def _margin_pct(part: Decimal | None, revenue: Decimal | None) -> float | None:
    if part is None or revenue is None or revenue == 0:
        return None
    return round(float(part / revenue * 100), 1)


def _revenue_cagr(history: list[dict[str, object]]) -> float | None:
    """Compound annual growth from the oldest to the newest positive fiscal year."""
    values = [float(item["value"]) for item in history]  # type: ignore[arg-type]
    if len(values) < 3 or values[0] <= 0 or values[-1] <= 0:
        return None
    years = len(values) - 1
    return round(((values[-1] / values[0]) ** (1 / years) - 1) * 100, 1)


def build_fundamentals(financials: dict[str, object], price: Decimal) -> dict[str, object]:
    """Transparent multi-year evidence stored alongside the valuation."""
    revenue = financials.get("revenue")
    net_income = financials.get("net_income")
    free_cash_flow = financials.get("free_cash_flow")
    shares = financials.get("shares_outstanding")
    equity = financials.get("equity")
    operating_income = financials.get("operating_income")
    gross_profit = financials.get("gross_profit")
    eps = financials.get("eps")

    market_cap = price * shares if shares else None
    book_value_per_share = _money(equity / shares) if equity is not None and shares else None
    return {
        "revenue_history": financials.get("revenue_history") or [],
        "net_income_history": financials.get("net_income_history") or [],
        "operating_income": float(operating_income) if operating_income is not None else None,
        "gross_profit": float(gross_profit) if gross_profit is not None else None,
        "equity": float(equity) if equity is not None else None,
        "book_value_per_share": (
            float(book_value_per_share) if book_value_per_share is not None else None
        ),
        "market_cap": float(market_cap) if market_cap is not None else None,
        "revenue_cagr_pct": _revenue_cagr(financials.get("revenue_history") or []),
        "margins": {
            "gross_pct": _margin_pct(gross_profit, revenue),
            "operating_pct": _margin_pct(operating_income, revenue),
            "net_pct": _margin_pct(net_income, revenue),
            "fcf_pct": _margin_pct(free_cash_flow, revenue),
        },
        "ratios": {
            "price_to_sales": _ratio(market_cap, revenue),
            "price_to_earnings": _ratio(price, eps) if eps and eps > 0 else None,
            "price_to_fcf": (
                _ratio(market_cap, free_cash_flow)
                if free_cash_flow and free_cash_flow > 0
                else None
            ),
            "price_to_book": (
                _ratio(price, book_value_per_share)
                if book_value_per_share and book_value_per_share > 0
                else None
            ),
        },
    }


def build_analysis(financials: dict[str, object], price: Decimal) -> dict:
    revenue = financials["revenue"]
    previous_revenue = financials["previous_revenue"]
    net_income = financials["net_income"]
    free_cash_flow = financials["free_cash_flow"]
    cash = financials["cash"] or Decimal("0")
    debt = financials["debt"] or Decimal("0")
    shares = financials["shares_outstanding"]
    eps = financials["eps"]
    equity = financials.get("equity")
    operating_income = financials.get("operating_income")

    growth = None
    if revenue is not None and previous_revenue and previous_revenue != 0:
        growth = float((revenue / previous_revenue - 1) * 100)

    methods: list[dict[str, object]] = []
    net_cash_per_share = Decimal("0")
    if shares and shares > 0:
        net_cash_per_share = (cash - debt) / shares
        if revenue and revenue > 0:
            value = revenue * Decimal("2") / shares + net_cash_per_share
            if value > 0:
                methods.append(
                    {"model": "Revenue multiple", "value": float(_money(value)), "multiple": 2}
                )
        if free_cash_flow and free_cash_flow > 0:
            value = free_cash_flow * Decimal("15") / shares + net_cash_per_share
            if value > 0:
                methods.append(
                    {
                        "model": "Free cash flow multiple",
                        "value": float(_money(value)),
                        "multiple": 15,
                    }
                )
        if operating_income and operating_income > 0:
            value = operating_income * Decimal("12") / shares + net_cash_per_share
            if value > 0:
                methods.append(
                    {
                        "model": "Operating income multiple",
                        "value": float(_money(value)),
                        "multiple": 12,
                    }
                )
        if equity and equity > 0:
            value = equity * Decimal("1.5") / shares
            if value > 0:
                methods.append(
                    {
                        "model": "Book value multiple",
                        "value": float(_money(value)),
                        "multiple": 1.5,
                    }
                )
    if eps and eps > 0:
        value = eps * Decimal("18")
        methods.append(
            {"model": "Earnings multiple", "value": float(_money(value)), "multiple": 18}
        )
    if not methods:
        raise ValueError("Insufficient positive financial data for valuation")

    fair_value = _money(Decimal(str(median([item["value"] for item in methods]))))
    bear_value = _money(fair_value * Decimal("0.70"))
    bull_value = _money(fair_value * Decimal("1.35"))
    upside = float((fair_value / price - 1) * 100)

    fundamentals = build_fundamentals(financials, price)

    catalysts: list[dict[str, object]] = []
    if growth is not None and growth >= 15:
        catalysts.append(
            {
                "category": "Financial",
                "title": "Revenue growth",
                "detail": f"Latest annual revenue increased {growth:.1f}%.",
                "status": "Confirmed",
            }
        )
    cagr = fundamentals.get("revenue_cagr_pct")
    if isinstance(cagr, int | float) and cagr >= 10:
        catalysts.append(
            {
                "category": "Financial",
                "title": "Multi-year revenue compounding",
                "detail": f"Revenue compounded {cagr:.1f}% annually across recent fiscal years.",
                "status": "Confirmed",
            }
        )
    if free_cash_flow and free_cash_flow > 0:
        catalysts.append(
            {
                "category": "Financial",
                "title": "Positive free cash flow",
                "detail": "Latest annual operating cash flow exceeded capital expenditure.",
                "status": "Confirmed",
            }
        )
    if cash > debt:
        catalysts.append(
            {
                "category": "Balance sheet",
                "title": "Net cash position",
                "detail": "Reported cash exceeds reported current and long-term debt.",
                "status": "Confirmed",
            }
        )
    operating_margin = fundamentals["margins"].get("operating_pct")
    if isinstance(operating_margin, int | float) and operating_margin >= 15:
        catalysts.append(
            {
                "category": "Financial",
                "title": "Strong operating margin",
                "detail": f"Operating income is {operating_margin:.1f}% of revenue.",
                "status": "Confirmed",
            }
        )

    risks: list[dict[str, object]] = []
    if growth is not None and growth < 0:
        risks.append({"severity": "High", "title": "Revenue contraction"})
    if net_income is not None and net_income < 0:
        risks.append({"severity": "High", "title": "Unprofitable latest fiscal year"})
    if free_cash_flow is not None and free_cash_flow < 0:
        risks.append({"severity": "High", "title": "Negative free cash flow"})
    if equity is not None and equity < 0:
        risks.append({"severity": "High", "title": "Negative shareholder equity"})
    if debt > cash and cash > 0:
        risks.append({"severity": "Moderate", "title": "Debt exceeds cash"})
    if len(methods) == 1:
        risks.append({"severity": "Moderate", "title": "Single usable valuation method"})

    score = min(20, max(0, round((upside + 25) / 10)))
    score += min(15, max(0, round((growth or 0) / 2)))
    score += 15 if net_income and net_income > 0 else 3
    score += 10 if cash >= debt else 4
    score += min(20, len(catalysts) * 5)
    score += min(5, len(methods))
    score -= sum(6 if risk["severity"] == "High" else 3 for risk in risks)
    score = max(0, min(100, score))

    completeness = sum(financials.get(field) is not None for field in CORE_FIELDS)
    if len(methods) >= 3 and completeness >= 7:
        confidence = "A"
    elif len(methods) >= 2 and completeness >= 5:
        confidence = "B"
    elif len(methods) >= 1 and completeness >= 4:
        confidence = "C"
    else:
        confidence = "D"

    high_risks = sum(risk["severity"] == "High" for risk in risks)
    risk_level = "High" if high_risks >= 2 else "Moderate" if risks else "Low"
    bull_upside = float((bull_value / price - 1) * 100)
    if upside >= 90 and len(methods) >= 2:
        qualification = "Confirmed 90% Upside"
    elif upside >= 90:
        qualification = "Speculative 90% Upside"
    elif bull_upside >= 90:
        qualification = "Conditional 90% Upside"
    else:
        qualification = "Below 90% Threshold"

    return {
        "revenue_growth_pct": growth,
        "fair_value": fair_value,
        "bear_value": bear_value,
        "bull_value": bull_value,
        "upside_pct": upside,
        "opportunity_score": score,
        "confidence_grade": confidence,
        "risk_level": risk_level,
        "qualification": qualification,
        "valuation_methods": methods,
        "catalysts": catalysts,
        "risks": risks,
        "fundamentals": fundamentals,
        "thesis_breakers": [
            "Revenue declines in the next annual filing.",
            "Free cash flow turns negative or deteriorates materially.",
            "Debt rises above cash without corresponding earnings growth.",
        ],
    }
