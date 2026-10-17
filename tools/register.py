"""Interactive tool registration.

Run: python tools/register.py

Prompts for tool details and updates brain/commands.json and brain/routing.json.
"""
import json
import sys
from pathlib import Path

BRAIN_DIR = Path(__file__).resolve().parent.parent / "brain"
COMMANDS_FILE = BRAIN_DIR / "commands.json"
ROUTING_FILE = BRAIN_DIR / "routing.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prompt(label: str, required: bool = True) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value or not required:
            return value
        print("  (required)")


def prompt_list(label: str) -> list[str]:
    raw = input(f"{label} (comma-separated): ").strip()
    return [item.strip() for item in raw.split(",") if item.strip()]


def prompt_bool(label: str, default: bool = False) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    value = input(f"{label}{suffix}: ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes", "sim")


def main() -> None:
    if not COMMANDS_FILE.exists() or not ROUTING_FILE.exists():
        print("Error: brain/commands.json and brain/routing.json must exist.", file=sys.stderr)
        sys.exit(1)

    commands = load_json(COMMANDS_FILE)
    routing = load_json(ROUTING_FILE)

    print("\n=== Register a new tool ===\n")

    tool_id = prompt("Tool ID (unique, e.g. 'greet')")
    if tool_id in {c["id"] for c in commands["commands"]}:
        print(f"Error: tool '{tool_id}' already exists.", file=sys.stderr)
        sys.exit(1)

    description = prompt("Description (what does it do?)")
    parameter = prompt("Parameter name (e.g. 'name', 'query')")

    action = "run_script" if prompt_bool("Will this run a Python script?") else "search_knowledge"

    script = function = ""
    if action == "run_script":
        script = prompt("Script filename (without .py, e.g. 'hello')")
        function = prompt("Function name in that script")

    examples = prompt_list("Example phrases (optional)", required=False) if action == "run_script" else []

    command = {
        "id": tool_id,
        "description": description,
        "action": action,
        "parameter": parameter,
    }
    if action == "run_script":
        command["script"] = script
        command["function"] = function
    if examples:
        command["examples"] = examples

    commands["commands"].append(command)
    save_json(COMMANDS_FILE, commands)
    print(f"\nAdded to {COMMANDS_FILE.name}")

    print("\n--- Routing metadata ---\n")
    triggers = prompt_list("Triggers (exact phrases, e.g. 'greet', 'say hi to')")
    keywords = prompt_list("Keywords (for scoring fallback)")
    priority = int(prompt("Priority (integer, higher = preferred)", required=False) or "0")
    multiple_values = prompt_bool("Accept multiple values in one request?")

    routing["commands"][tool_id] = {
        "triggers": triggers,
        "keywords": keywords,
        "priority": priority,
    }
    if multiple_values:
        routing["commands"][tool_id]["multiple_values"] = True

    save_json(ROUTING_FILE, routing)
    print(f"Added to {ROUTING_FILE.name}")

    if action == "run_script":
        script_path = Path(__file__).resolve().parent / f"{script}.py"
        if not script_path.exists():
            print(f"\nReminder: create {script_path.name} with a function '{function}({parameter}: str) -> ...'")

    print("\nDone. Restart Needle.py to use the new tool.")


if __name__ == "__main__":
    main()
