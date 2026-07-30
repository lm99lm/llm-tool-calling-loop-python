"""Structured output through a tool you never execute.

Same mechanism as agent.py, one setting different: `tool_choice` names a function,
so the model is not allowed to answer in prose. Its only legal move is to emit
arguments matching the schema, and those arguments are the structured record you
wanted. Nothing calls `record_receipt`; it exists so the schema has a name.

    python extract.py
    python extract.py "TAXI 14.50 EUR 03/11 Berlin Hbf -> office"
"""

import json
import sys

from agent import make_client

SAMPLE = (
    "HETZNER ONLINE GMBH  invoice R0012934  billed 2024-03-15  "
    "server rental EX44 x2  EUR 39.20  paid by card ****4417"
)

RECORD_RECEIPT = {
    "type": "function",
    "function": {
        "name": "record_receipt",
        "description": "Store one parsed receipt line in the ledger.",
        "parameters": {
            "type": "object",
            "properties": {
                "vendor": {"type": "string", "description": "Merchant name, title case, no legal suffix."},
                "date": {"type": "string", "description": "Transaction date as YYYY-MM-DD."},
                "amount": {"type": "number", "description": "Numeric amount, no currency symbol."},
                "currency": {"type": "string", "description": "ISO 4217 code, e.g. EUR."},
                "category": {
                    "type": "string",
                    "enum": ["cloud", "saas", "travel", "hardware", "other"],
                    "description": "Best-fitting category from the fixed list.",
                },
            },
            "required": ["vendor", "date", "amount", "currency", "category"],
        },
    },
}


def parse_receipt(raw_text):
    ai = make_client()
    reply = ai.chat.completions.create(
        model="auto",
        messages=[
            {"role": "system", "content": "Turn messy receipt text into one record. Copy values, do not invent them."},
            {"role": "user", "content": raw_text},
        ],
        tools=[RECORD_RECEIPT],
        # Without this the model would happily write a sentence instead.
        tool_choice={"type": "function", "function": {"name": "record_receipt"}},
    ).choices[0].message

    if not reply.tool_calls:
        raise RuntimeError("model answered with text despite a forced tool_choice: %r" % reply.content)

    # `arguments` is a JSON string produced by the model. The schema constrains the
    # shape, so json.loads is safe; the values still deserve a look before you trust
    # them, which is why the enum above keeps `category` inside a known set.
    return json.loads(reply.tool_calls[0].function.arguments)


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or SAMPLE
    print(json.dumps(parse_receipt(text), indent=2, sort_keys=True))
