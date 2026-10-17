import importlib
import inspect
import json
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

import needle

BRAIN_DIR = Path(__file__).resolve().parent.parent / "brain"
COMMANDS_FILE = BRAIN_DIR / "commands.json"
ROUTING_FILE = BRAIN_DIR / "routing.json"
Command = dict[str, Any]
ProgressCallback = Callable[[str, str], None]


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _normalize_with_index_map(text: str) -> tuple[str, list[int]]:
    normalized_chars = []
    original_indices = []
    for index, char in enumerate(text):
        for normalized_char in unicodedata.normalize("NFKD", char.casefold()):
            if not unicodedata.combining(normalized_char):
                normalized_chars.append(normalized_char)
                original_indices.append(index)
    return "".join(normalized_chars), original_indices


def search_knowledge(query: str) -> list[dict[str, object]]:
    """Search brain JSON files and return matching records."""
    query_terms = set(re.findall(r"[a-z0-9]+", _normalize_text(query)))
    results = []

    for data_file in sorted(BRAIN_DIR.glob("*.json")):
        if data_file in (COMMANDS_FILE, ROUTING_FILE):
            continue

        try:
            content = json.loads(data_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON in {data_file.name}: {error}") from error

        records = content if isinstance(content, list) else [content]
        for record in records:
            record_text = json.dumps(record, ensure_ascii=False)
            record_terms = set(re.findall(r"[a-z0-9]+", _normalize_text(record_text)))
            matches = query_terms & record_terms
            if not query_terms or matches:
                results.append({
                    "file": data_file.name,
                    "relevance": len(matches),
                    "content": record,
                })

    return sorted(results, key=lambda result: result["relevance"], reverse=True)


def load_catalog() -> tuple[list[Command], dict[str, list[str]]]:
    """Load executable commands and separate routing metadata."""
    try:
        catalog = json.loads(COMMANDS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {COMMANDS_FILE.name}: {error}") from error

    if not isinstance(catalog, dict) or not isinstance(catalog.get("commands"), list):
        raise ValueError(f"{COMMANDS_FILE.name} must contain a 'commands' list.")

    try:
        routing = json.loads(ROUTING_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {ROUTING_FILE.name}: {error}") from error
    if not isinstance(routing, dict) or not isinstance(routing.get("commands"), dict):
        raise ValueError(f"{ROUTING_FILE.name} must contain a 'commands' object.")

    routing_data: dict[str, list[str]] = {}
    for key in ("stopwords", "parameter_markers", "multi_task_markers"):
        values = routing.get(key)
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value.strip() for value in values
        ):
            raise ValueError(f"Routing field {key!r} must be a list of non-empty strings.")
        routing_data[key] = values

    commands: list[Command] = []
    command_ids: set[str] = set()
    allowed_actions = {"search_knowledge", "run_script"}
    required_fields = ("id", "description", "action", "parameter")
    routing_commands = routing["commands"]

    for item in catalog["commands"]:
        if not isinstance(item, dict):
            raise ValueError("Each command must be a JSON object.")

        command = {key: item.get(key) for key in required_fields}
        if not all(isinstance(value, str) and value.strip() for value in command.values()):
            raise ValueError("Each command requires non-empty id, description, action, and parameter fields.")
        if command["action"] not in allowed_actions:
            raise ValueError(f"Unsupported action in {command['id']!r}: {command['action']!r}.")

        if command["action"] == "run_script":
            for key in ("script", "function"):
                value = item.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"Command {command['id']!r} must define {key!r}.")
                command[key] = value
            if not command["script"].isidentifier() or not command["function"].isidentifier():
                raise ValueError(f"Script and function names in {command['id']!r} must be Python identifiers.")

        examples = item.get("examples", [])
        if not isinstance(examples, list) or not all(
            isinstance(value, str) and value.strip() for value in examples
        ):
            raise ValueError(f"Routing field 'examples' for {command['id']!r} must be a list of non-empty strings.")
        command["examples"] = examples

        route = routing_commands.get(command["id"], {})
        if not isinstance(route, dict):
            raise ValueError(f"Routing metadata for {command['id']!r} must be an object.")
        for key in ("triggers", "keywords"):
            values = route.get(key, [])
            if not isinstance(values, list) or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                raise ValueError(f"Routing field {key!r} for {command['id']!r} must be a list of non-empty strings.")
            command[key] = values
        priority = route.get("priority", 0)
        if not isinstance(priority, int):
            raise ValueError(f"Routing priority for {command['id']!r} must be an integer.")
        command["priority"] = priority
        multiple_values = route.get("multiple_values", False)
        if not isinstance(multiple_values, bool):
            raise ValueError(f"Routing field 'multiple_values' for {command['id']!r} must be a boolean.")
        command["multiple_values"] = multiple_values

        if command["id"] in command_ids:
            raise ValueError(f"Duplicate command ID: {command['id']!r}.")
        command_ids.add(command["id"])
        commands.append(command)

    unknown_routes = routing_commands.keys() - command_ids
    if unknown_routes:
        raise ValueError(f"Routing metadata references unknown commands: {sorted(unknown_routes)}.")

    return commands, routing_data


_ACTIONS: dict[str, Callable[[str], object]] = {
    "search_knowledge": search_knowledge,
}


def _run_script(command: Command, parameter: str) -> object:
    module = importlib.import_module(f".{command['script']}", package=__package__)
    function = getattr(module, command["function"], None)
    if not callable(function):
        raise ValueError(f"Function {command['function']!r} was not found in script {command['script']!r}.")
    return function(parameter)


def run_command_by_trigger(
    text: str,
    commands: list[Command],
    routing: dict[str, list[str]],
    progress_callback: ProgressCallback | None = None,
) -> object | None:
    """Run a command when a configured trigger or routing match is found."""
    normalized_text, original_indices = _normalize_with_index_map(text)
    candidates: list[tuple[int, Command, str]] = []

    for command in commands:
        for trigger in command.get("triggers", []):
            normalized_trigger = _normalize_text(trigger.strip())
            if not normalized_text.startswith(normalized_trigger):
                continue

            trigger_end = len(normalized_trigger)
            if trigger_end < len(normalized_text) and normalized_text[trigger_end].isalnum():
                continue

            parameter_start = original_indices[trigger_end] if trigger_end < len(original_indices) else len(text)
            parameter = text[parameter_start:].lstrip(" \t:,-.!?")
            candidates.append((trigger_end, command, parameter))

    if not candidates:
        for command in commands:
            for trigger in command.get("triggers", []):
                normalized_trigger = _normalize_text(trigger.strip())
                trigger_match = re.search(r"\b" + re.escape(normalized_trigger) + r"\b", normalized_text)
                if not trigger_match:
                    continue
                trigger_end = trigger_match.end()
                parameter_start = original_indices[trigger_end] if trigger_end < len(original_indices) else len(text)
                parameter = text[parameter_start:].lstrip(" \t:,-.!?")
                candidates.append((len(normalized_trigger), command, parameter))

    if not candidates:
        stopwords = {_normalize_text(stopword) for stopword in routing["stopwords"]}

        def filtered_tokens(value: str) -> set[str]:
            return {
                token
                for token in re.findall(r"[a-z0-9]+", _normalize_text(value))
                if len(token) > 2 and token not in stopwords
            }

        text_tokens = filtered_tokens(text)
        best_matches: list[tuple[int, Command, str]] = []
        for command in commands:
            description_tokens = filtered_tokens(command.get("description", ""))
            keyword_tokens = set().union(
                *(filtered_tokens(value) for value in command.get("keywords", []))
            )
            example_tokens = set().union(
                *(filtered_tokens(value) for value in command.get("examples", []))
            )
            score = (
                3 * len(text_tokens & keyword_tokens)
                + 2 * len(text_tokens & description_tokens)
                + len(text_tokens & example_tokens)
                + command.get("priority", 0)
            )
            if score > 0:
                best_matches.append((score, command, ""))

        if best_matches:
            _, command, parameter = max(best_matches, key=lambda match: match[0])
            marker_pattern = "|".join(
                re.escape(marker)
                for marker in sorted(routing["parameter_markers"], key=len, reverse=True)
            )
            match = re.search(rf"\b(?:{marker_pattern})\b\s+(.+)$", text, flags=re.IGNORECASE)
            if match:
                parameter = match.group(1).strip().rstrip(" .,!? ")
            candidates.append((0, command, parameter))

    if not candidates:
        return None

    _, command, parameter = max(candidates, key=lambda candidate: candidate[0])
    return _execute_command(command, parameter, progress_callback)


def _execute_command(
    command: Command,
    parameter: str,
    progress_callback: ProgressCallback | None,
) -> object:
    if command.get("multiple_values"):
        values = [
            value.strip()
            for value in re.split(r"\s*(?:,|;|\be\b)\s*", parameter, flags=re.IGNORECASE)
            if value.strip()
        ]
        if len(values) > 1:
            single_value_command = {**command, "multiple_values": False}
            return [
                _execute_command(single_value_command, value, progress_callback)
                for value in values
            ]

    if progress_callback:
        progress_callback(command["id"], "started")

    try:
        result = (
            _run_script(command, parameter)
            if command["action"] == "run_script"
            else _ACTIONS[command["action"]](parameter)
        )
    except Exception:
        if progress_callback:
            progress_callback(command["id"], "failed")
        raise

    if progress_callback:
        progress_callback(command["id"], "completed")
    return result


def run_multi_value_command(
    text: str,
    commands: list[Command],
    progress_callback: ProgressCallback | None = None,
) -> list[object] | None:
    """Execute a multi-value command for each explicitly requested value."""
    normalized_text, original_indices = _normalize_with_index_map(text)

    for command in commands:
        if not command.get("multiple_values"):
            continue
        for trigger in command.get("triggers", []):
            normalized_trigger = _normalize_text(trigger.strip())
            match = re.search(r"\b" + re.escape(normalized_trigger) + r"\b", normalized_text)
            if not match:
                continue

            parameter_start = match.end()
            original_start = original_indices[parameter_start] if parameter_start < len(original_indices) else len(text)
            parameter = text[original_start:].lstrip(" \t:,-.!?")
            values = [
                value.strip()
                for value in re.split(r"\s*(?:,|;|\be\b)\s*", parameter, flags=re.IGNORECASE)
                if value.strip()
            ]
            if len(values) < 2:
                continue
            return [
                _execute_command(command, value, progress_callback)
                for value in values
            ]

    return None


def is_multi_task_request(text: str, routing: dict[str, list[str]]) -> bool:
    """Return whether a request contains a configured task separator."""
    normalized_text = _normalize_text(text)
    for marker in routing["multi_task_markers"]:
        normalized_marker = _normalize_text(marker.strip())
        if re.search(rf"\b{re.escape(normalized_marker)}\b", normalized_text):
            return True
    return ";" in text


def create_tool(
    command: Command,
    progress_callback: ProgressCallback | None = None,
) -> Callable[..., object]:
    """Create a tool with its configured name, description, and argument."""
    name = command["id"]
    parameter_name = command["parameter"]

    def tool_function(**arguments: str) -> object:
        value = arguments.get(parameter_name)
        if not isinstance(value, str):
            raise ValueError(f"Parameter {parameter_name!r} must be a string.")
        return _execute_command(command, value, progress_callback)

    tool_function.__name__ = name
    tool_function.__qualname__ = name
    doc = command["description"]
    if command.get("examples"):
        doc += "\n\nExamples:\n" + "\n".join(f"- {example}" for example in command["examples"])
    tool_function.__doc__ = doc
    tool_function.__annotations__ = {parameter_name: str, "return": object}
    tool_function.__signature__ = inspect.Signature(
        [inspect.Parameter(parameter_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str)],
        return_annotation=object,
    )
    return needle.tool(tool_function)


def create_tools(
    commands: list[Command],
    progress_callback: ProgressCallback | None = None,
) -> list[Callable[..., object]]:
    """Create all tools from the loaded catalog."""
    return [create_tool(command, progress_callback) for command in commands]
