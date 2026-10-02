"""
sample_data.py — generate a realistic 3-month bank statement for a small
bubble-tea shop, used for the demo / tests. All data is synthetic.
"""

from __future__ import annotations

import random

import pandas as pd

random.seed(42)

INCOME_SOURCES = [
    # (name, per-day min txns, per-day max txns, min amount, max amount)
    ("微信收款-堂食", 15, 25, 8.0, 45.0),
    ("支付宝收款-外卖", 8, 16, 10.0, 40.0),
    ("美团平台结算", 3, 6, 15.0, 60.0),
    ("饿了么平台结算", 2, 4, 15.0, 55.0),
    ("现金存入", 1, 3, 20.0, 120.0),
]
EXPENSE_CATS = [
    # (name, per-day min txns, per-day max txns, min amount, max amount)
    ("供应商-茶叶原料", 0, 1, 200.0, 800.0),
    ("供应商-鲜奶乳品", 1, 2, 100.0, 600.0),
    ("供应商-果糖包装", 0, 1, 80.0, 400.0),
    ("平台佣金", 3, 6, 3.0, 20.0),
    ("杂费/物料", 0, 2, 10.0, 100.0),
]


def generate_statement(months: int = 3, start: str = "2026-07-01") -> pd.DataFrame:
    start_dt = pd.Timestamp(start)
    rows: list[dict] = []
    for i in range(months):
        month_start = start_dt + pd.DateOffset(months=i)
        days = 30 if i < months - 1 else 28
        for d in range(days):
            day = month_start + pd.Timedelta(days=d)
            is_weekend = day.dayofweek >= 5
            growth = 1 + i * 0.08  # mild month-over-month growth

            for name, lo, hi, amin, amax in INCOME_SOURCES:
                n = random.randint(lo, hi)
                if is_weekend:
                    n = int(n * 1.3)
                for _ in range(n):
                    amt = round(random.uniform(amin, amax) * growth, 2)
                    rows.append({
                        "交易日期": day.strftime("%Y-%m-%d"),
                        "摘要": name,
                        "收入": amt,
                        "支出": 0.0,
                        "余额": 0.0,
                    })

            for name, lo, hi, amin, amax in EXPENSE_CATS:
                n = random.randint(lo, hi)
                for _ in range(n):
                    amt = round(random.uniform(amin, amax), 2)
                    rows.append({
                        "交易日期": day.strftime("%Y-%m-%d"),
                        "摘要": name,
                        "收入": 0.0,
                        "支出": amt,
                        "余额": 0.0,
                    })

            # monthly fixed costs on fixed days
            if d == 1:
                rows.append({
                    "交易日期": day.strftime("%Y-%m-%d"),
                    "摘要": "房租", "收入": 0.0,
                    "支出": round(random.uniform(3200.0, 3600.0), 2), "余额": 0.0,
                })
                rows.append({
                    "交易日期": day.strftime("%Y-%m-%d"),
                    "摘要": "水电费", "收入": 0.0,
                    "支出": round(random.uniform(800.0, 1300.0), 2), "余额": 0.0,
                })
            if d == 5:
                rows.append({
                    "交易日期": day.strftime("%Y-%m-%d"),
                    "摘要": "员工工资", "收入": 0.0,
                    "支出": 5600.0, "余额": 0.0,
                })
            if d == 20 and random.random() < 0.7:
                rows.append({
                    "交易日期": day.strftime("%Y-%m-%d"),
                    "摘要": "设备维护", "收入": 0.0,
                    "支出": round(random.uniform(200.0, 900.0), 2), "余额": 0.0,
                })

    df = pd.DataFrame(rows)
    df = df.sort_values("交易日期").reset_index(drop=True)
    bal = 15000.0
    balances = []
    for _, r in df.iterrows():
        bal += r["收入"] - r["支出"]
        balances.append(round(bal, 2))
    df["余额"] = balances
    return df


if __name__ == "__main__":
    out = generate_statement()
    out.to_excel("/home/erp/friend-finance/sample_statement.xlsx", index=False)
    print(f"generated {len(out)} rows -> sample_statement.xlsx")
    print(out.head(3).to_string())
    print(f"income={out['收入'].sum():.2f} expense={out['支出'].sum():.2f} "
          f"net={out['收入'].sum()-out['支出'].sum():.2f}")
