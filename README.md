# NeedleAI-util

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.9+-blue?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/status-stable-success?style=flat-square)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey?style=flat-square&logo=windows)
![Model Size](https://img.shields.io/badge/model-14MB-orange?style=flat-square)
![Offline](https://img.shields.io/badge/offline-ready-brightgreen?style=flat-square)

**Tiny offline AI assistant · Two-stage router · Local-first**

[Quick Start](#run-it) · [Add Tools](#add-a-tool) · [Architecture](#how-it-decides) · [Comparison](#comparison-with-jev)

</div>

---

A tiny offline assistant that routes user requests to registered tools. It runs on the 14 MB [cactus-needle](https://pypi.org/project/cactus-needle/) foundation model and falls back to rule-based routing whenever a configured trigger or keyword match is strong enough to skip the model entirely.

## What it does

- Loads a catalog of tools from `brain/commands.json` and their routing metadata from `brain/routing.json`.
- For each user request it tries, in order:
  1. An exact trigger match (e.g. `"saudacao para Ana"`).
  2. A keyword + stopword scoring match against command descriptions.
  3. The local Needle model, which picks among the registered tools using a short system prompt.
- Multi-value requests ("greet Ana and Bruno") and multi-task requests ("search the weather and greet Ana") are split and executed in sequence.
- Knowledge stored in `brain/*.json` (anything that is not `commands.json` or `routing.json`) is searchable via the `search_knowledge` tool.

## Run it

### Windows (quick start)

Double-click `NeedleAI.bat`. If the virtual environment is missing, it shows setup instructions.

### Manual setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python Needle.py
```

Type `/exit` or `/quit` to leave. First launch downloads the Needle weights.

## Add a tool

Run the interactive registrar:

```bash
python tools/register.py
```

It prompts for the tool ID, description, parameter, triggers, keywords, and priority, then updates `brain/commands.json` and `brain/routing.json` automatically.

If the tool runs a Python script, write the function in `tools/` (e.g. `tools/hello.py`):

```python
def greet(name: str) -> dict[str, str]:
    return {"message": f"Hi, {name}!"}
```

The registrar will remind you to create the script if it does not exist yet.

### Manual configuration (advanced)

You can also edit the JSON files directly:

- `brain/commands.json`: tool catalog (id, description, action, parameter, script, function, examples)
- `brain/routing.json`: triggers, keywords, priority, multiple_values

`triggers` fire on exact prefix or word match and skip the model. `keywords` feed the scoring fallback. `priority` is an integer tie-breaker. `multiple_values: true` lets one request fan out over a comma/semicolon/`e`-separated list.

## How it decides

NeedleAI-util is a two-stage router, not a pure agent:

- **Stage 1 — deterministic routing.** Trigger and keyword matches run in microseconds, need no GPU, and never hallucinate. If they score above zero, the model is not called.
- **Stage 2 — small local model.** Only ambiguous requests reach Needle, which picks among the tools exposed to it. The model runs in a single process, weights live on disk, nothing leaves the machine.

This is the same shape as a "System One / System Two" split: fast pattern matching handles the common cases, slow reasoning handles the rest.

## Comparison with Jev

[Needle](https://github.com/cactus-compute/needle) (by Cactus Compute) and [Jev](https://jevmodel.org/) (by TypeSafe AI) are both small, fast models designed for structured decisions on edge devices, but they target different layers of the stack.

| | Needle | Jev |
|---|---|---|
| **Job** | Tool calling, structured extraction, embeddings, ASR | Typed decisions (choice / score / probability) |
| **Architecture** | Laddered Simple Attention Network, 2-bit quantization | Causal transformer, non-autoregressive parallel sampler |
| **Size** | 8–29 MB (single binary) | Not disclosed (hosted API) |
| **Deployment** | Fully local, runs on phones, wearables, MCUs, cars | Hosted API, $0.042 / M input tokens, output free |
| **Latency** | Sub-second on CPU (varies by device) | 70–500 ms per vendor |
| **Output** | Tool calls with arguments, typed JSON, vectors, transcripts | Enumerated answers with calibrated confidence scores |
| **Schema** | Defined in Python decorators or JSON, compiled into grammar | Defined per request in API call |
| **Fine-tuning** | Local LoRA or platform-managed, 4-bit or 2-bit | Not disclosed |
| **Speech** | Yes (Whistle: 16.9 MB, 7 languages) | No |
| **When to use** | You need tool execution, extraction, or embeddings on tiny devices | You need fast classification/scoring in a hot path with calibrated probabilities |
| **Prose generation** | No (not a chat model) | No (not a chat model) |

**Key difference:** Needle is a *foundation model for automation* — it picks tools, fills arguments, extracts structured data, and returns embeddings, all from a single 8–29 MB binary that runs on microcontrollers. Jev is a *decision model* — it returns typed choices with confidence scores, optimized for routing and gating in high-volume pipelines.

**NeedleAI-util** (this project) wraps Needle with a deterministic two-stage router: trigger/keyword matching for instant responses, then Needle for ambiguous requests. It adds a REPL, tool catalog, and interactive registrar on top of the base model.

**When to pair them:** Use Jev to classify and route (is this a refund request? is this action safe?), then hand the winning path to Needle (via NeedleAI-util) to execute the tool call and return results. Needle already implements the tool-calling half; swap its routing stage for Jev when you need calibrated probabilities at scale.

## Layout

```
Needle.py              entry point and REPL loop
brain/
  commands.json        tool catalog
  routing.json         triggers, keywords, stopwords, priorities
  clima.json           sample knowledge base
tools/
  __init__.py          catalog loader, router, tool factory
  example_greeting.py  sample script tool
```

## License

MIT.

---

<p align="center">
  If this project is useful to you, consider giving it a star.
  <br />
  <a href="https://github.com/tlipe/needleAI-util/stargazers">
    <img src="https://img.shields.io/badge/Star_this_Project-★-yellow?style=for-the-badge&logo=github" alt="Star this project" />
  </a>
</p>
