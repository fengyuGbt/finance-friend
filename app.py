"""
app.py — local finance insight app for a friend.

Upload a bank statement / income-expense Excel (or CSV). pandas extracts the
key numbers on this machine, then a LOCAL open-weight model (Ollama + qwen2.5)
writes a plain-language report. No data ever leaves the laptop.

Run:  .venv/bin/python app.py  →  http://127.0.0.1:7860
"""

from __future__ import annotations

import os

import gradio as gr
import pandas as pd

import analyzer
import reporter

BUSINESS_DEFAULT = "一家小型奶茶店"


def run(file_obj, business_context: str) -> tuple:
    if file_obj is None:
        raise gr.Error("请先上传银行流水或收支 Excel/CSV 文件。")
    path = getattr(file_obj, "name", file_obj)
    if not os.path.exists(path):
        # gradio may give a temp path; accept it directly
        path = str(file_obj)
    try:
        summary = analyzer.analyze(path)
    except Exception as e:  # noqa: BLE001 — surface friendly message
        raise gr.Error(f"解析失败：{e}") from e

    s = summary
    # human-readable stats table
    monthly_view = s.monthly.copy()
    monthly_view.columns = ["月份", "收入", "支出", "净额"]
    stats_rows = {
        "记录笔数": s.rows,
        "统计周期": f"{s.start} ~ {s.end}",
        "总收入": round(s.total_income, 2),
        "总支出": round(s.total_expense, 2),
        "净结余": round(s.net_flow, 2),
    }
    overview = pd.DataFrame(
        [{"指标": k, "数值": v} for k, v in stats_rows.items()]
    )

    # LLM report
    try:
        report = reporter.generate_report(s.to_dict(), business_context or BUSINESS_DEFAULT)
    except RuntimeError as e:
        report = f"⚠️ {e}"

    # key tables for the UI
    top_inc = s.top_income.rename(columns={"source": "收入来源", "amount": "金额"})
    top_exp = s.top_expense.rename(columns={"category": "支出类别", "amount": "金额"})
    big = s.big_txns.rename(
        columns={"date": "日期", "description": "摘要", "income": "收入",
                 "expense": "支出", "net": "净额"}
    )

    return (
        overview,
        monthly_view,
        top_inc,
        top_exp,
        big,
        report,
    )


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="本地财务解读助手") as demo:
        gr.Markdown(
            "# 🧾 本地财务解读助手\n"
            "上传银行流水或收支 Excel/CSV，统计与解读**全部在本机完成**"
            "（pandas + 本地开源模型 qwen2.5），数据不出这台电脑。"
        )
        with gr.Row():
            with gr.Column(scale=1):
                file = gr.File(
                    label="上传流水文件（xlsx / xls / csv）",
                    file_types=[".xlsx", ".xls", ".csv"],
                )
                ctx = gr.Textbox(
                    label="生意背景（可选，帮助解读更贴合）",
                    value=BUSINESS_DEFAULT,
                )
                btn = gr.Button("开始分析", variant="primary")
            with gr.Column(scale=2):
                report_out = gr.Markdown(label="AI 解读")
        with gr.Row():
            overview = gr.Dataframe(label="总览")
            monthly = gr.Dataframe(label="月度收支")
        with gr.Row():
            top_inc = gr.Dataframe(label="主要收入来源")
            top_exp = gr.Dataframe(label="主要支出")
            big = gr.Dataframe(label="大额交易")

        btn.click(
            run,
            inputs=[file, ctx],
            outputs=[overview, monthly, top_inc, top_exp, big, report_out],
        )
        gr.Markdown(
            "**开源说明**：本应用使用开源模型 [qwen2.5](https://ollama.com/library/qwen2.5) "
            "（通过 Ollama 本地运行）。可自由替换模型：`OLLAMA_MODEL=qwen2.5:7b python app.py`。"
        )
    return demo


if __name__ == "__main__":
    build_ui().launch(server_name="127.0.0.1", server_port=7860)
