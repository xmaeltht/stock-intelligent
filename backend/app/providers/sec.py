import csv
import io
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.providers.http import fetch_bytes, fetch_json

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
NASDAQ_TRADED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"


@dataclass(frozen=True)
class SecCompany:
    cik: str
    name: str
    ticker: str
    exchange: str | None


@dataclass(frozen=True)
class NasdaqInstrument:
    symbol: str
    name: str
    exchange: str | None
    asset_type: str


class SecProvider:
    def __init__(self, user_agent: str, cache_dir: Path):
        self.user_agent = user_agent
        self.cache_dir = cache_dir

    def company_universe(self) -> list[SecCompany]:
        payload = fetch_json(
            SEC_TICKERS_URL,
            self.user_agent,
            self.cache_dir / "sec" / "company_tickers_exchange.json",
        )
        fields = payload["fields"]
        companies = []
        for row in payload["data"]:
            record = dict(zip(fields, row, strict=True))
            ticker = str(record.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            companies.append(
                SecCompany(
                    cik=str(record["cik"]).zfill(10),
                    name=str(record["name"]),
                    ticker=ticker,
                    exchange=record.get("exchange") or None,
                )
            )
        return companies

    def traded_instruments(self) -> list[NasdaqInstrument]:
        """Load U.S.-traded symbols and Nasdaq Trader's explicit ETF flag."""
        cache_path = self.cache_dir / "nasdaq" / "nasdaqtraded.txt"
        try:
            payload = fetch_bytes(NASDAQ_TRADED_URL, self.user_agent)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(payload)
        except Exception:
            if not cache_path.exists():
                raise
            payload = cache_path.read_bytes()
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), delimiter="|")
        exchange_names = {
            "Q": "Nasdaq",
            "N": "NYSE",
            "A": "NYSE American",
            "P": "NYSE Arca",
            "Z": "Cboe BZX",
            "V": "IEX",
        }
        result: list[NasdaqInstrument] = []
        for row in reader:
            if row.get("Test Issue") == "Y":
                continue
            asset_type = "ETF" if row.get("ETF") == "Y" else "Stock"
            symbol = str(row.get("Symbol") or "").strip().upper()
            if not symbol:
                continue
            result.append(
                NasdaqInstrument(
                    symbol=symbol,
                    name=str(row.get("Security Name") or symbol).strip(),
                    exchange=exchange_names.get(str(row.get("Listing Exchange") or "")),
                    asset_type=asset_type,
                )
            )
        return result

    def asset_types(self) -> dict[str, str]:
        return {item.symbol: item.asset_type for item in self.traded_instruments()}

    def company_facts(self, cik: str) -> dict:
        time.sleep(0.12)
        return fetch_json(
            SEC_FACTS_URL.format(cik=cik.zfill(10)),
            self.user_agent,
            self.cache_dir / "sec" / "companyfacts" / f"CIK{cik.zfill(10)}.json",
        )


def _concept(facts: dict, names: tuple[str, ...]) -> dict | None:
    taxonomies = facts.get("facts", {})
    # ifrs-full covers foreign private issuers filing 20-F/40-F. Only USD units
    # are ever read (see callers), so non-USD IFRS filers stay excluded rather
    # than mixing currencies into the valuation.
    for taxonomy in ("us-gaap", "ifrs-full", "dei"):
        concepts = taxonomies.get(taxonomy, {})
        for name in names:
            if name in concepts:
                return concepts[name]
    return None


def _entries(facts: dict, names: tuple[str, ...], units: tuple[str, ...]) -> list[dict]:
    concept = _concept(facts, names)
    if not concept:
        return []
    for unit in units:
        if unit in concept.get("units", {}):
            return concept["units"][unit]
    return []


def annual_values(
    facts: dict, names: tuple[str, ...], units: tuple[str, ...] = ("USD",)
) -> list[dict]:
    allowed_forms = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
    by_end: dict[str, dict] = {}
    for entry in _entries(facts, names, units):
        if entry.get("form") not in allowed_forms or entry.get("fp") != "FY":
            continue
        if not entry.get("end") or entry.get("val") is None:
            continue
        previous = by_end.get(entry["end"])
        if previous is None or entry.get("filed", "") > previous.get("filed", ""):
            by_end[entry["end"]] = entry
    return sorted(by_end.values(), key=lambda item: item["end"], reverse=True)


def latest_value(
    facts: dict, names: tuple[str, ...], units: tuple[str, ...] = ("USD",)
) -> Decimal | None:
    allowed_forms = {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "40-F"}
    entries = [
        item
        for item in _entries(facts, names, units)
        if item.get("form") in allowed_forms and item.get("val") is not None
    ]
    if not entries:
        return None
    latest = max(entries, key=lambda item: (item.get("end", ""), item.get("filed", "")))
    return Decimal(str(latest["val"]))


def annual_pair(
    facts: dict, names: tuple[str, ...], units: tuple[str, ...] = ("USD",)
) -> tuple[Decimal | None, Decimal | None]:
    values = annual_values(facts, names, units)
    current = Decimal(str(values[0]["val"])) if values else None
    previous = Decimal(str(values[1]["val"])) if len(values) > 1 else None
    return current, previous


def annual_history(
    facts: dict,
    names: tuple[str, ...],
    units: tuple[str, ...] = ("USD",),
    years: int = 6,
) -> list[dict[str, object]]:
    """Chronological fiscal-year history [{fy_end, value}], oldest first."""
    values = annual_values(facts, names, units)[:years]
    return [
        {"fy_end": item["end"], "value": float(item["val"])} for item in reversed(values)
    ]


REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    # IFRS (foreign private issuers)
    "Revenue",
    "RevenueFromContractsWithCustomers",
)
NET_INCOME_TAGS = (
    "NetIncomeLoss",
    "ProfitLoss",
    "NetIncomeLossAvailableToCommonStockholdersBasic",
    "ProfitLossAttributableToOwnersOfParent",
)


def extract_financials(facts: dict) -> dict[str, object]:
    revenue, previous_revenue = annual_pair(facts, REVENUE_TAGS)
    net_income, _ = annual_pair(facts, NET_INCOME_TAGS)
    operating_cash_flow, _ = annual_pair(
        facts,
        (
            "NetCashProvidedByUsedInOperatingActivities",
            "CashFlowsFromUsedInOperatingActivities",
        ),
    )
    capex, _ = annual_pair(
        facts,
        (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsForProceedsFromProductiveAssets",
            "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
        ),
    )
    eps, _ = annual_pair(
        facts,
        (
            "EarningsPerShareDiluted",
            "EarningsPerShareBasicAndDiluted",
            "EarningsPerShareBasic",
            "DilutedEarningsLossPerShare",
            "BasicEarningsLossPerShare",
        ),
        ("USD/shares", "USD / shares"),
    )
    shares = latest_value(
        facts,
        ("EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding"),
        ("shares",),
    )
    cash = latest_value(
        facts,
        (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
            "CashAndCashEquivalents",
        ),
    )
    debt_current = latest_value(
        facts, ("LongTermDebtCurrent", "LongTermDebtAndFinanceLeaseObligationsCurrent")
    )
    debt_long = latest_value(
        facts, ("LongTermDebtNoncurrent", "LongTermDebtAndFinanceLeaseObligationsNoncurrent")
    )
    equity = latest_value(
        facts,
        (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            "Equity",
            "EquityAttributableToOwnersOfParent",
        ),
    )
    operating_income, _ = annual_pair(
        facts, ("OperatingIncomeLoss", "ProfitLossFromOperatingActivities")
    )
    gross_profit, _ = annual_pair(facts, ("GrossProfit",))
    free_cash_flow = None
    if operating_cash_flow is not None:
        free_cash_flow = operating_cash_flow - (capex or Decimal("0"))
    debt = (debt_current or Decimal("0")) + (debt_long or Decimal("0"))
    return {
        "revenue": revenue,
        "previous_revenue": previous_revenue,
        "net_income": net_income,
        "free_cash_flow": free_cash_flow,
        "cash": cash,
        "debt": debt,
        "shares_outstanding": shares,
        "eps": eps,
        "equity": equity,
        "operating_income": operating_income,
        "gross_profit": gross_profit,
        "revenue_history": annual_history(facts, REVENUE_TAGS),
        "net_income_history": annual_history(facts, NET_INCOME_TAGS),
    }
