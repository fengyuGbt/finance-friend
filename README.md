# Finance Friend — 本地财务解读助手

Turn a raw bank statement into plain-language business insights, **entirely on your own machine**.

Upload an Excel/CSV export of your bank transactions. `pandas` extracts the key numbers, then a **local open-weight LLM** (Qwen2.5-3B-Instruct, running through llama.cpp) writes a plain-language report: where the money comes from, where it goes, and what to watch.

No cloud. No API keys. Your financial data never leaves the laptop.

## Why open-source AI is the point

- **Data stays home.** Bank statements are sensitive. With a closed API, every row of your friend's income and rent goes through someone else's server. Here, inference happens in a local process — the file, the statistics, and the model weights all live on the same machine.
- **It works offline.** No internet required after setup. Run it in a shop basement, on a farm, anywhere.
- **You own the model.** Qwen2.5 is Apache-2.0 licensed open weights. Swap in any GGUF you like — a bigger model, a finance-tuned one, one in another language — by changing one environment variable. No vendor lock-in.
- **It costs nothing to run.** Inference is free after the one-time model download.

## Quick start

```bash
# 1. Install dependencies (Python 3.10+)
python3 -m venv .venv && source .venv/bin/activate
pip install llama-cpp-python pandas openpyxl gradio

# 2. Download the open-weight model (Qwen2.5-3B-Instruct, Apache-2.0)
curl -L -o qwen2.5-3b-q4.gguf \
  https://hf-mirror.com/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf

# 3. Run the app
python app.py
# → open http://127.0.0.1:7860
```

Generate a synthetic demo statement if you have no file handy:

```bash
python sample_data.py
```

## How it works

```
Excel / CSV bank statement
        │
        ▼
analyzer.py  (pandas, on this machine)
  - auto-detects date / description / income / expense columns (中/EN)
  - monthly income & expenses, net flow
  - top income sources, top expense categories, biggest transactions
        │  compact JSON summary
        ▼
reporter.py  (llama-cpp, on this machine)
  - Qwen2.5-3B-Instruct (open weights, GGUF)
  - writes a 250–350 word plain-language business report
        ▼
Gradio UI — overview table, monthly table, AI report
```

## Optional: swap the model

```bash
# any GGUF file — bigger, smaller, different language, fine-tuned
MODEL_PATH=/path/to/your-model.gguf python app.py

# or use an Ollama backend if you prefer
BACKEND=ollama OLLAMA_MODEL=qwen2.5:3b python app.py
```

## Project layout

| File | Purpose |
| --- | --- |
| `app.py` | Gradio UI (upload → tables → AI report) |
| `analyzer.py` | pandas parsing & statistics |
| `reporter.py` | local LLM report generation (llama.cpp default, Ollama optional) |
| `sample_data.py` | synthetic 3-month bubble-tea-shop statement for demo/tests |

Built for the Hacktoberfest 2026 "Build for a Friend" challenge: open-source AI at its core, solving a real problem for a real person.
