"""Smoke check for the routing and catalog logic.

Run with: python _smoke.py
Exits non-zero on any assertion failure.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools import load_catalog, search_knowledge, run_command_by_trigger, is_multi_task_request


def test_load_catalog_returns_commands_and_routing():
    commands, routing = load_catalog()
    assert isinstance(commands, list) and commands, "commands must be non-empty"
    assert {c["id"] for c in commands} >= {"search_knowledge", "generate_greeting"}
    for key in ("stopwords", "parameter_markers", "multi_task_markers"):
        assert isinstance(routing[key], list) and routing[key]


def test_search_knowledge_finds_clima_record():
    results = search_knowledge("São Paulo temperatura")
    assert results, "expected at least one result for São Paulo"
    assert results[0]["file"] == "clima.json"
    assert results[0]["relevance"] >= 1


def test_search_knowledge_excludes_routing_and_commands():
    results = search_knowledge("stopwords triggers priority")
    files = {r["file"] for r in results}
    assert "commands.json" not in files
    assert "routing.json" not in files


def test_trigger_match_runs_greeting():
    commands, routing = load_catalog()
    result = run_command_by_trigger("saudacao para Ana", commands, routing)
    assert isinstance(result, dict)
    assert "Ana" in result["message"]


def test_keyword_match_routes_to_search():
    commands, routing = load_catalog()
    result = run_command_by_trigger("buscar clima de São Paulo", commands, routing)
    assert isinstance(result, list)


def test_multi_task_detection():
    _, routing = load_catalog()
    assert is_multi_task_request("buscar o clima e saudar Ana", routing)
    assert is_multi_task_request("buscar o clima; saudar Ana", routing)
    assert not is_multi_task_request("buscar o clima", routing)


def test_stopwords_normalized():
    commands, routing = load_catalog()
    # "uma" is a stopword; without normalization it would match with accent drift
    result = run_command_by_trigger("buscar uma informação", commands, routing)
    # Should still route to search_knowledge via keyword match
    assert isinstance(result, list)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\n{len(tests)} checks passed.")
