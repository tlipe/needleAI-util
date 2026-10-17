import logging
import os
import contextlib

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

import needle
from tools import (
    create_tools,
    is_multi_task_request,
    load_catalog,
    run_command_by_trigger,
    run_multi_value_command,
)

SYSTEM_PROMPT = (
    "Choose the registered tool that best matches the request. "
    "A request may contain multiple tasks; call every relevant tool in request order. "
    "Only use available tools; do not invent tool names or arguments."
)


def main() -> None:
    commands, routing = load_catalog()
    step_number = 0

    def report_tool_progress(tool_id: str, status: str) -> None:
        nonlocal step_number
        if status == "started":
            step_number += 1
            print(f"\n[Step {step_number}] Running {tool_id}...", flush=True)
        elif status == "completed":
            print(f"[Step {step_number}] Completed {tool_id}.", flush=True)
        else:
            print(f"[Step {step_number}] {tool_id} failed.", flush=True)

    tools = create_tools(commands, report_tool_progress)
    print("Needle Chat | Type /exit to quit.")
    print("Loading model. The first startup may take a moment...", flush=True)

    try:
        with open(os.devnull, "w") as quiet_output:
            with contextlib.redirect_stdout(quiet_output), contextlib.redirect_stderr(quiet_output):
                agent = needle.Needle(
                    tools=tools,
                    system=SYSTEM_PROMPT,
                    stateless=True,
                )
    except Exception as error:
        print(f"Model initialization failed: {error}")
        return

    print("Model ready.\n")

    while True:
        try:
            user_input = input("You > ").strip()

            if not user_input:
                continue

            if user_input.lower() in {"/exit", "/quit"}:
                break

            step_number = 0
            multi_value_result = run_multi_value_command(
                user_input,
                commands,
                report_tool_progress,
            )
            if multi_value_result is not None:
                for result in multi_value_result:
                    print(f"Needle > {result}")
                continue

            if not is_multi_task_request(user_input, routing):
                direct_result = run_command_by_trigger(
                    user_input,
                    commands,
                    routing,
                    report_tool_progress,
                )
                if direct_result is not None:
                    print(f"Needle > {direct_result}")
                    continue

            print("Needle > Selecting actions...", flush=True)
            response = agent.run(user_input)
            results = response.get("results", [])

            if results:
                for result in results:
                    print(f"Needle > {result}")
            else:
                function_calls = response.get("function_calls", [])
                if function_calls:
                    print(f"Needle > {function_calls}")
                else:
                    print("Needle > No tool was executed.")

        except KeyboardInterrupt:
            print("\nShutting down.")
            break
        except Exception as error:
            print(f"Error: {error}")


if __name__ == "__main__":
    main()
