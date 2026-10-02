"""
reporter.py — turn a FinancialSummary into plain-language insights using a
LOCAL open-weight model. Default backend: llama-cpp-python running a GGUF file
on this machine. Optional backend: Ollama (OLLAMA_URL env). Nothing leaves
the machine.
"""

from __future__ import annotations

import json
import os
import re

MODEL_PATH = os.environ.get(
    "MODEL_PATH", "/home/erp/friend-finance/qwen2.5-3b-q4.gguf"
)
BACKEND = os.environ.get("BACKEND", "llamacpp")  # llamacpp | ollama
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")

SYSTEM_PROMPT = (
    "你是一个小生意的财务帮手。你会收到一份银行流水/收支表的统计摘要，"
    "请用通俗易懂的中文写一份 250-350 字的财务解读。"
    "结构如下：\n"
    "1. **总体情况**：一句话概括收支与净结余。\n"
    "2. **收入分析**：主要收入来源是什么，趋势如何。\n"
    "3. **支出分析**：钱主要花在哪，有没有异常或大额支出。\n"
    "4. **风险与建议**：列出 1-3 条具体、可操作的建议。\n"
    "只依据给出的数据说话，不要编造数字，不要使用 Markdown 表格。"
)

# ------------------------------------------------------------------ helpers

def _fmt_json(x) -> str:
    return json.dumps(x, ensure_ascii=False, indent=1)


def build_prompt(summary: dict, business_context: str = "") -> str:
    ctx = f"这个账户的生意背景：{business_context}\n\n" if business_context else ""
    return (
        f"以下是某账户流水统计摘要：\n{_fmt_json(summary)}\n\n"
        f"{ctx}请按要求生成解读。"
    )


# ------------------------------------------------------------- llama-cpp backend

_llm = None
_llm_lock_holder = None


def _get_llm():
    global _llm
    if _llm is None:
        from llama_cpp import Llama
        _llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=8192,
            n_threads=8,
            verbose=False,
        )
    return _llm


def _generate_llamacpp(prompt: str, timeout: int = 600) -> str:
    llm = _get_llm()
    out = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=1200,
    )
    return out["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------- ollama backend

def _generate_ollama(prompt: str, timeout: int = 180) -> str:
    import requests
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_ctx": 8192},
    }
    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "").strip()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot reach Ollama at {OLLAMA_URL}. Is it running? "
            f"Start it with: ollama serve (detail: {e})"
        ) from e


# ------------------------------------------------------------------- public API

def generate_report(
    summary: dict,
    business_context: str = "",
    timeout: int = 600,
) -> str:
    prompt = build_prompt(summary, business_context)
    if BACKEND == "ollama":
        return _generate_ollama(prompt, timeout=180)
    return _generate_llamacpp(prompt, timeout=timeout)


def clean_markdown(text: str) -> str:
    """Keep light markdown (bold/headings) but drop tables and code fences."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"\|.*?\|", "", text)
    return text.strip()
