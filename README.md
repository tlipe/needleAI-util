# NeedleAI-util

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

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python Needle.py
```

Type `/exit` or `/quit` to leave. First launch downloads the Needle weights.

## Add a tool

1. Write the function in `tools/`, e.g. `tools/hello.py`:

   ```python
   def greet(name: str) -> dict[str, str]:
       return {"message": f"Hi, {name}!"}
   ```

2. Register it in `brain/commands.json`:

   ```json
   {
     "id": "greet",
     "description": "Say hi to someone.",
     "action": "run_script",
     "script": "hello",
     "function": "greet",
     "parameter": "name",
     "examples": ["greet Ana", "say hi to Bruno"]
   }
   ```

3. Add routing hints in `brain/routing.json` under `commands.greet`:

   ```json
   "greet": {
     "triggers": ["greet", "say hi to"],
     "keywords": ["greet", "hello", "hi"],
     "priority": 5,
     "multiple_values": true
   }
   ```

`triggers` fire on exact prefix or word match and skip the model. `keywords` feed the scoring fallback. `priority` is an integer tie-breaker. `multiple_values: true` lets one request fan out over a comma/semicolon/`e`-separated list.

## How it decides

NeedleAI-util is a two-stage router, not a pure agent:

- **Stage 1 — deterministic routing.** Trigger and keyword matches run in microseconds, need no GPU, and never hallucinate. If they score above zero, the model is not called.
- **Stage 2 — small local model.** Only ambiguous requests reach Needle, which picks among the tools exposed to it. The model runs in a single process, weights live on disk, nothing leaves the machine.

This is the same shape as a "System One / System Two" split: fast pattern matching handles the common cases, slow reasoning handles the rest.

## Comparison with Jev

[Jev](https://jevmodel.org/) is TypeSafe AI's proprietary "System One" decision model. It is a useful point of comparison because both projects target fast, structured decisions, but they sit at opposite ends of the stack.

| | NeedleAI-util | Jev |
|---|---|---|
| **Job** | Route a request and *execute* a tool | Return a typed decision (choice / score / probability) |
| **Output** | Tool result (string, dict, list) | One of the enumerated answers, with a calibrated confidence |
| **Deployment** | Local, 14 MB weights, CPU | Hosted API, $0.042 / M input tokens |
| **Latency** | Sub-second on a laptop | 70–500 ms per the vendor |
| **Schema** | Defined once in `commands.json` | Defined per request in the API call |
| **When to use** | You need to *do* something on a user's behalf | You need to *classify / score / gate* something in a hot path |
| **Prose** | Can hand off to an LLM for language | Cannot generate text |

A clean pairing: use a Jev-style decision model to classify and route (is this a refund request? is this action safe?), then hand the winning path to a tool-running agent like NeedleAI-util to actually perform the work. NeedleAI-util already implements the routing half locally; swap its scoring stage for Jev when you need calibrated probabilities at scale and are willing to pay for the API.

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
