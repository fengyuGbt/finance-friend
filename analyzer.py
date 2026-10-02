"""
analyzer.py — parse bank statements / income-expense sheets into a compact
financial summary that a small local LLM can turn into plain-language insights.

Input: xlsx / xls / csv with date, description, income/expense (or signed amount)
and optionally balance columns. Column names are auto-detected for common
Chinese and English banking exports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------- column maps

DATE_KEYS = [
    "date", "交易日期", "日期", "记账日期", "时间", "交易时间",
    "transactiondate", "transactiondate", "posteddate",
]
DESC_KEYS = [
    "description", "摘要", "交易摘要", "备注", "用途", "说明",
    "memo", "particulars", "narrative", "counterparty", "对方户名", "交易对手", "商户名称", "名称", "item",
]
IN_KEYS = [
    "income", "收入", "存入", "贷方", "入账", "收款金额", "金额+",
    "deposit", "credit", "in", "moneyin", "进账", "收入金额",
]
OUT_KEYS = [
    "expense", "支出", "取出", "借方", "出账", "付款金额", "金额-",
    "withdrawal", "debit", "out", "moneyout", "出账金额", "支出金额",
]
BAL_KEYS = ["balance", "余额", "账户余额", "结余", "可用余额", "账面余额"]

CURRENCY_RE = re.compile(r"[¥￥$€£,，\s]")
AMOUNT_RE = re.compile(r"^[-+]?[\d.]+$")


def _norm(c: object) -> str:
    return str(c).strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def _pick_columns(df: pd.DataFrame, keys: list[str]) -> Optional[str]:
    """Exact-normalized match first, then substring match."""
    cols = {_norm(c): c for c in df.columns}
    for k in keys:
        nk = _norm(k)
        if nk in cols:
            return cols[nk]
    for k in keys:
        nk = _norm(k)
        for norm, orig in cols.items():
            if nk in norm:
                return orig
    return None


# ------------------------------------------------------------- cleaning utils

def _to_float(series: pd.Series) -> pd.Series:
    out = series.astype(str).str.replace(CURRENCY_RE, "", regex=True)
    out = out.str.extract(r"([-+]?[\d.]+)", expand=False)
    return pd.to_numeric(out, errors="coerce")


def _to_date(series: pd.Series) -> pd.Series:
    out = pd.to_datetime(series, errors="coerce")
    # some exports give 'YYYYMMDD' or 'YYYY/MM/DD HH:MM:SS'
    if out.isna().all():
        out = pd.to_datetime(series.astype(str).str.slice(0, 10), errors="coerce")
    return out


# ------------------------------------------------------------------ analysis

@dataclass
class FinancialSummary:
    rows: int
    start: Optional[str]
    end: Optional[str]
    months: int
    total_income: float
    total_expense: float
    net_flow: float
    monthly: pd.DataFrame
    top_income: pd.DataFrame
    top_expense: pd.DataFrame
    big_txns: pd.DataFrame
    counterparties: pd.DataFrame
    has_balance: bool = False
    balance_series: pd.Series = field(default_factory=pd.Series)
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        big = self.big_txns.copy()
        if "date" in big.columns:
            big["date"] = big["date"].astype(str)
        return {
            "rows": self.rows,
            "period": f"{self.start} ~ {self.end}",
            "months": self.months,
            "total_income": round(self.total_income, 2),
            "total_expense": round(self.total_expense, 2),
            "net_flow": round(self.net_flow, 2),
            "monthly": self.monthly.round(2).to_dict(orient="records"),
            "top_income": self.top_income.round(2).to_dict(orient="records"),
            "top_expense": self.top_expense.round(2).to_dict(orient="records"),
            "big_txns": big.round(2).to_dict(orient="records"),
            "counterparties": self.counterparties.round(2).to_dict(orient="records"),
            "has_balance": self.has_balance,
            "flags": self.flags,
        }


def analyze(file_path: str) -> FinancialSummary:
    """Main entry: read a statement file and produce a FinancialSummary."""
    if str(file_path).lower().endswith(".csv"):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)
    if df.empty:
        raise ValueError("File contains no rows.")

    date_col = _pick_columns(df, DATE_KEYS)
    desc_col = _pick_columns(df, DESC_KEYS)
    in_col = _pick_columns(df, IN_KEYS)
    out_col = _pick_columns(df, OUT_KEYS)
    bal_col = _pick_columns(df, BAL_KEYS)

    if date_col is None and desc_col is None:
        raise ValueError(
            "Could not find date/description columns. "
            "Expected columns like: 日期/摘要/收入/支出 or Date/Description/Amount."
        )

    work = df.copy()
    if date_col:
        work["_date"] = _to_date(work[date_col])
        work = work.dropna(subset=["_date"]).sort_values("_date")
    if desc_col:
        work["_desc"] = work[desc_col].astype(str)

    # amounts -----------------------------------------------------------
    if in_col and out_col:
        work["_income"] = _to_float(work[in_col]).fillna(0.0)
        work["_expense"] = _to_float(work[out_col]).fillna(0.0)
    else:
        amt_col = in_col or out_col
        if amt_col is None:
            raise ValueError("Could not find an amount column (income/expense).")
        amt = _to_float(work[amt_col])
        work["_income"] = amt.clip(lower=0).fillna(0.0)
        work["_expense"] = (-amt.clip(upper=0)).fillna(0.0)
        work = work[work["_income"] + work["_expense"] > 0]

    if bal_col:
        bal = _to_float(work[bal_col])
        bal = bal.loc[bal.notna()]
        if len(bal) > 1:
            work["_balance"] = bal
            has_balance = True
        else:
            has_balance = False
    else:
        has_balance = False

    # core numbers --------------------------------------------------------
    total_income = float(work["_income"].sum())
    total_expense = float(work["_expense"].sum())
    net_flow = total_income - total_expense

    # monthly ---------------------------------------------------------------
    monthly = (
        work.groupby(work["_date"].dt.to_period("M"))
        .agg(income=("_income", "sum"), expense=("_expense", "sum"))
        .reset_index()
    )
    monthly["month"] = monthly["_date"].astype(str)
    monthly["net"] = monthly["income"] - monthly["expense"]
    monthly = monthly[["month", "income", "expense", "net"]]

    # big & grouped ---------------------------------------------------------
    work["_net"] = work["_income"] - work["_expense"]
    big = work.reindex(work["_net"].abs().sort_values(ascending=False).index).head(8)
    big = big[["_date", "_desc", "_income", "_expense", "_net"]].rename(
        columns={"_date": "date", "_desc": "description",
                 "_income": "income", "_expense": "expense", "_net": "net"}
    )

    if desc_col:
        cparty = (
            work.groupby("_desc")
            .agg(times=("_net", "size"), amount=("_net", "sum"))
            .sort_values("amount", key=lambda s: s.abs(), ascending=False)
            .head(12)
            .reset_index()
            .rename(columns={"_desc": "counterparty"})
        )
        inc_by = (
            work[work["_income"] > 0]
            .groupby("_desc")["_income"].sum()
            .sort_values(ascending=False).head(6)
            .reset_index().rename(columns={"_desc": "source", "_income": "amount"})
        )
        exp_by = (
            work[work["_expense"] > 0]
            .groupby("_desc")["_expense"].sum()
            .sort_values(ascending=False).head(6)
            .reset_index().rename(columns={"_desc": "category", "_expense": "amount"})
        )
    else:
        cparty = pd.DataFrame(columns=["counterparty", "times", "amount"])
        inc_by = pd.DataFrame(columns=["source", "amount"])
        exp_by = pd.DataFrame(columns=["category", "amount"])

    # flags ------------------------------------------------------------------
    flags = []
    if len(monthly) >= 2:
        trend = monthly["net"].iloc[-1] - monthly["net"].iloc[0]
        flags.append(f"net flow changed by {trend:+.2f} from first to last month")
    if total_expense > 0 and total_expense / max(1, len(work)) > 500:
        flags.append("average transaction amount is high, check for lump payments")
    if net_flow < 0:
        flags.append("spending exceeds income over the period")

    start_s = work["_date"].min().strftime("%Y-%m-%d") if date_col else ""
    end_s = work["_date"].max().strftime("%Y-%m-%d") if date_col else ""
    months_n = int(monthly.shape[0]) if len(monthly) else 0

    return FinancialSummary(
        rows=int(len(work)),
        start=start_s,
        end=end_s,
        months=months_n,
        total_income=total_income,
        total_expense=total_expense,
        net_flow=net_flow,
        monthly=monthly,
        top_income=inc_by,
        top_expense=exp_by,
        big_txns=big,
        counterparties=cparty,
        has_balance=has_balance,
        balance_series=(work["_balance"] if has_balance else pd.Series()),
        flags=flags,
    )
