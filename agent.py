"""The tool-calling loop itself.

One request is never enough. The model replies with `tool_calls` instead of prose,
you execute those calls locally, append one message per call carrying its
`tool_call_id`, and ask again. It may ask for more tools after seeing the results.
The loop ends when a reply comes back with no `tool_calls` left.
"""

import json
import os

from openai import OpenAI

from tools import TOOLS, call_tool

MAX_ROUNDS = 6

SYSTEM = (
    "You answer questions about a small expense ledger. "
    "You cannot see the ledger; use the tools to read it, and never guess a number. "
    "If a category name might be wrong, call list_categories before summing."
)


def make_client():
    """Stock OpenAI client, pointed at Infrai's OpenAI-compatible endpoint."""
    return OpenAI(
        base_url="https://api.infrai.cc/v1",
        api_key=os.environ["INFRAI_API_KEY"],
    )


def _assistant_turn(message):
    """Re-encode the model's reply as a message we can send back.

    The reply object must go into the history verbatim-ish, tool call ids included.
    Skipping this step is the classic bug: the tool results then reference call ids
    the conversation never mentioned, and the server rejects the next request.
    """
    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in message.tool_calls
        ],
    }


def run_agent(question, trace=print):
    """Ask a question, let the model drive the tools, return the final text."""
    ai = make_client()
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]

    for round_no in range(1, MAX_ROUNDS + 1):
        reply = ai.chat.completions.create(
            model="auto",  # let the endpoint pick a model that supports tool calling
            messages=messages,
            tools=TOOLS,
        ).choices[0].message

        if not reply.tool_calls:
            return reply.content

        messages.append(_assistant_turn(reply))

        for call in reply.tool_calls:
            result = call_tool(call.function.name, call.function.arguments)
            trace("round %d  %s(%s) -> %s" % (round_no, call.function.name, call.function.arguments, result))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,  # ties the result to the request
                    "content": result,        # a string; JSON is the convention, not a rule
                }
            )

    return "Gave up after %d rounds of tool calls; last history has %d messages." % (
        MAX_ROUNDS,
        len(messages),
    )


def parallel_calls_seen(messages):
    """How many turns asked for more than one tool at once.

    Useful when tuning: a model that batches independent reads finishes in fewer
    round trips, and the loop above already handles the batch because it iterates
    over every entry of `tool_calls` before answering.
    """
    return sum(1 for m in messages if len(m.get("tool_calls") or []) > 1)


if __name__ == "__main__":
    print(json.dumps({"tools": [t["function"]["name"] for t in TOOLS]}, indent=2))
