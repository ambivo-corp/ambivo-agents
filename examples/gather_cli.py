"""
examples/gather_cli.py
Interactive CLI demo for the conversational GatherAgent.

Features
- Waits for user input after each question
- Shows available options in the prompt for yes-no, single-select, and multi-select
- Accepts a questionnaire from a file path (JSON/YAML) or uses a default sample
- Simulates submission by default (no network). Use --real-submit to perform a real HTTP call

Usage
  python examples/gather_cli.py                # Use default questionnaire, simulate submission
  python examples/gather_cli.py --path q.json  # Load questionnaire from file
  python examples/gather_cli.py --real-submit  # Do a real HTTP submission (configure endpoint)

Controls
  - Answer questions as prompted
  - For multi-select: provide a comma-separated list (e.g., "AWS, Azure")
  - Type "finish" to submit early
  - Type "cancel" to abort and submit collected-so-far

Note
  The GatherAgent already formats prompts to include available options for single-select/multi-select
  and adds (Yes/No) for yes-no. This demo simply prints the agent’s prompts and waits for input.
"""
import argparse
import asyncio
import json
import sys
from typing import Any, Dict, Optional

from ambivo_agents.agents.gather_agent import GatherAgent


class LocalMemory:
    """Minimal async in-memory context store (subset used by GatherAgent)."""

    def __init__(self):
        self._ctx: Dict[str, Any] = {}

    async def store_context(self, key: str, value: Any, conversation_id: Optional[str] = None):
        self._ctx[key] = value

    async def get_context(self, key: str, conversation_id: Optional[str] = None):
        return self._ctx.get(key)

    async def clear_memory(self, conversation_id: Optional[str] = None):
        self._ctx.clear()


DEFAULT_QUESTIONNAIRE = {
    "questions": [
        {
            "question_id": "q1",
            "text": "Do you use any cloud providers?",
            "type": "yes-no",
            "required": True,
            "answer_option_dict_list": [
                {"value": "Yes", "label": "Yes"},
                {"value": "No", "label": "No"},
            ],
        },
        {
            "question_id": "q1a",
            "text": "Which cloud providers do you use?",
            "type": "multi-select",
            "is_conditional": True,
            "parent_question_id": "q1",
            "required": False,
            "answer_option_dict_list": [
                {"value": "AWS", "label": "AWS"},
                {"value": "Azure", "label": "Azure"},
                {"value": "GCP", "label": "GCP"},
                {"value": "Other", "label": "Other"},
            ],
        },
        {
            "question_id": "q2",
            "text": "What is your company size?",
            "type": "single-select",
            "required": True,
            "answer_option_dict_list": [
                {"value": "1-50", "label": "1-50"},
                {"value": "51-200", "label": "51-200"},
                {"value": "201-1000", "label": "201-1000"},
                {"value": "1000+", "label": "1000+"},
            ],
        },
        {
            "question_id": "q3",
            "text": "What is the best email to reach you?",
            "type": "free-text",
            "required": True,
        },
    ]
}


async def _load_questionnaire_from_path(agent: GatherAgent, path: str) -> Dict[str, Any]:
    """Use agent's file utils to read and parse JSON/YAML questionnaire from a file/URL."""
    res = await agent.read_and_parse_file(path, auto_parse=True)
    if not res.get("success"):
        raise RuntimeError(f"Failed to load questionnaire from {path}: {res.get('error')}")
    content = res.get("content")
    if isinstance(content, (dict, list)):
        return content if isinstance(content, dict) else {"questions": content}
    # if text, try JSON
    return json.loads(content)


async def _simulate_submit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    print("\n[Simulated Submission] The agent would submit the following payload:")
    print(json.dumps(payload, indent=2))
    return {"success": True, "status": 200, "response": "ok"}


async def main():
    parser = argparse.ArgumentParser(description="Interactive CLI for GatherAgent")
    parser.add_argument("--path", help="Path or URL to questionnaire (JSON/YAML)", default=None)
    parser.add_argument(
        "--real-submit",
        action="store_true",
        help="Perform a real HTTP submission using configured endpoint instead of simulating",
    )
    args = parser.parse_args()

    # Create agent (no external memory/LLM required for the deterministic prompts)
    agent = GatherAgent.create_advanced(
        agent_id="gather_cli",
        memory_manager=LocalMemory(),
        llm_service=None,
        config={
            "gather": {
                # Provide a placeholder endpoint; real submission requires --real-submit
                "submission_endpoint": "http://localhost/void",
                "submission_method": "POST",
                "submission_headers": {"Content-Type": "application/json"},
                "memory_ttl_seconds": 3600,
            }
        },
    )

    # Simulate submission unless --real-submit is provided
    if not args.real_submit:
        # Bind the simulated submit as agent method
        import types

        agent._submit = types.MethodType(_simulate_submit, agent)  # type: ignore

    # Load questionnaire
    if args.path:
        try:
            questionnaire = await _load_questionnaire_from_path(agent, args.path)
        except Exception as e:
            print(f"Error loading questionnaire: {e}")
            sys.exit(1)
    else:
        questionnaire = DEFAULT_QUESTIONNAIRE

    print("\n=== GatherAgent Interactive Demo ===")
    print("Type your answers after each prompt.")
    print("Commands: 'finish' to submit, 'cancel' to abort.")
    print("For multi-select, enter comma-separated values, e.g., 'AWS, Azure'\n")

    # Start by sending the questionnaire JSON
    first_prompt = await agent.chat(json.dumps(questionnaire))
    print(first_prompt)

    # Interactive loop: after each answer, agent prompts next question or submits
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            user_input = "cancel"
            print("\nCancelling...")

        reply = await agent.chat(user_input)
        print(reply)

        # Stop once the agent indicates it submitted (covers auto-submit or explicit finish/cancel)
        lower = reply.lower()
        if ("submitting your responses now" in lower) or ("we have reached the end of the questionnaire" in lower) or ("thanks, that's all i needed" in lower) or ("aborting the gathering" in lower):
            break

    print("\nDone. Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
